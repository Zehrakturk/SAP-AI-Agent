"""
app/api/enhance.py
Gemini tabanlı zenginleştirme endpoint'leri.
"""

from flask import Blueprint, request, jsonify
from app.services.gemini_enhancer import (
    enhance_visualization, enhance_report, suggest_palette, is_available
)

enhance_bp = Blueprint("enhance", __name__)


@enhance_bp.route("/status", methods=["GET"])
def gemini_status():
    return jsonify({"available": is_available()})


@enhance_bp.route("/visualization", methods=["POST"])
def viz_enhance():
    """
    Chat yanıtı için görsel zenginleştirme.
    Body: { question, rows, summary, chart_type, chart_data }
    """
    d = request.get_json(force=True)
    try:
        result = enhance_visualization(
            question   = d.get("question", ""),
            rows       = d.get("rows", []),
            summary    = d.get("summary", ""),
            chart_type = d.get("chart_type", "BAR"),
            chart_data = d.get("chart_data", {}),
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@enhance_bp.route("/report", methods=["POST"])
def report_enhance():
    """
    Rapor için Gemini HTML bölümü üretimi.
    Body: { question, rows, summary, kpis, highlights }
    """
    d = request.get_json(force=True)
    try:
        html = enhance_report(
            question   = d.get("question", ""),
            rows       = d.get("rows", []),
            summary    = d.get("summary", ""),
            kpis       = d.get("kpis", []),
            highlights = d.get("highlights", []),
        )
        return jsonify({"html": html})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@enhance_bp.route("/palette", methods=["POST"])
def palette_suggest():
    """
    Grafik etiketlerine uygun renk paleti öner.
    Body: { labels, context }
    """
    d       = request.get_json(force=True)
    palette = suggest_palette(d.get("labels", []), d.get("context", ""))
    return jsonify({"palette": palette})
