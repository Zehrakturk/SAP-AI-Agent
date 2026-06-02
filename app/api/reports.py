"""
app/api/reports.py — Sprint 2.2

Rapor export & paylaşım endpoint'leri:
  POST /api/v1/reports/export   → PDF (veya HTML fallback) byte stream döner
  POST /api/v1/reports/email    → aynı raporu attachment olarak maille gönderir
  GET  /api/v1/reports/capabilities → PDF & SMTP yapılandırma durumunu döner
"""

from __future__ import annotations

import os
from flask import Blueprint, request, jsonify, Response

from app.services.report_renderer import render_pdf_bytes, pdf_available
from app.services.email_sender    import send_report_email, EmailNotConfigured

reports_bp = Blueprint("reports", __name__)


@reports_bp.route("/capabilities", methods=["GET"])
def capabilities():
    """UI'ın hangi butonları göstereceğine karar vermesi için."""
    return jsonify({
        "pdf"   : pdf_available(),
        "email" : bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_USER")),
    })


@reports_bp.route("/export", methods=["POST"])
def export_report():
    """
    Body: rapor payload'u (question, summary, rows, sql, kpis, highlights, ...)
    Döner: PDF veya HTML byte stream.
    """
    data = request.get_json(force=True) or {}
    if not data.get("question") and not data.get("summary") and not data.get("rows"):
        return jsonify({"error": "Boş rapor payload'u."}), 400

    pdf_bytes, mime, ext = render_pdf_bytes(data)
    fname = f"sap-ai-report.{ext}"
    return Response(
        pdf_bytes,
        mimetype=mime,
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@reports_bp.route("/email", methods=["POST"])
def email_report():
    """
    Body:
      {
        "to": ["a@b.com", ...],
        "subject": "...",          (opsiyonel)
        "message": "...",          (opsiyonel — mail metni)
        "report": { ...payload }   (export ile aynı şema)
      }
    """
    data    = request.get_json(force=True) or {}
    to      = data.get("to") or []
    if isinstance(to, str):
        to = [x.strip() for x in to.split(",") if x.strip()]
    if not to:
        return jsonify({"error": "En az bir alıcı gerekli."}), 400

    report  = data.get("report") or {}
    subject = data.get("subject") or f"SAP-AI Rapor — {report.get('question','')[:60]}"
    body    = data.get("message") or "SAP-AI tarafından üretilen rapor ektedir."

    pdf_bytes, mime, ext = render_pdf_bytes(report)
    fname = f"sap-ai-report.{ext}"

    try:
        result = send_report_email(
            to=to, subject=subject, body_text=body,
            attachment_bytes=pdf_bytes, attachment_name=fname,
            attachment_mime=mime,
        )
    except EmailNotConfigured as e:
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        return jsonify({"error": f"Gönderim hatası: {e}"}), 500

    return jsonify(result)
