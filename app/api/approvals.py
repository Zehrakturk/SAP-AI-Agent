"""
app/api/approvals.py — Human-in-the-loop onay süreci API'si.

Endpoint'ler (prefix /api/v1/approvals):
  GET    /                        — admin: onay talepleri listesi (?status=PENDING&limit=50)
  GET    /<int:id>                — admin: detay (talep + job + audit izi)
  POST   /<int:id>/approve        — admin: onayla → ingestion job enqueue
  POST   /<int:id>/reject         — admin: reddet
  GET    /status/<external_id>    — kullanıcı: poll (approval + job + sonuç)
  GET    /jobs/<int:job_id>       — admin: job ilerleme/hata
  POST   /run-worker              — admin: worker'ı manuel tetikle (test/debug)
"""

from __future__ import annotations

from flask import Blueprint, request, jsonify

from app.services.ingestion.approval_service     import ApprovalService
from app.services.ingestion.approval_repository  import ApprovalRepository
from app.services.ingestion.job_repository       import JobRepository
from app.services.ingestion.audit_repository     import AuditRepository
from app.services.ingestion.models               import GapResult
from app.services.ingestion                      import process_pending_jobs

approvals_bp = Blueprint("approvals", __name__)


# ─────────────────────────────────────────────────────────────────────────────
def _token_parts(req):
    token = req.headers.get("Authorization", "").replace("Bearer ", "")
    if token.startswith("demo-token-"):
        p = token.split("-")
        return (p[2] if len(p) > 2 else None, p[3] if len(p) > 3 else None)
    return (None, None)


def _user_id(req) -> str | None:
    return _token_parts(req)[0]


def _is_admin(req) -> bool:
    return (_token_parts(req)[1] or "").lower() == "admin"


def _require_admin():
    """Admin değilse (response, status) döner; adminse None."""
    if not _is_admin(request):
        return jsonify({"error": "Bu işlem için admin yetkisi gerekir."}), 403
    return None


# ─────────────────────────────────────────────────────────────────────────────
@approvals_bp.route("/request", methods=["POST"])
def create_request():
    """
    Kullanıcı 'Evet, onaya gönder' dediğinde çağrılır → PENDING onay talebi üretir.
    Admin onayı gerektirmez (kullanıcının kendi sorgusu); admin yalnızca approve eder.
    Body: { gap: {integration_id, integration_name, params, reason}, question, filters }
    """
    user_id = _user_id(request)
    d       = request.get_json(force=True) or {}
    gap_d   = d.get("gap") or {}
    if not gap_d.get("integration_id"):
        return jsonify({"error": "Eksik gap bilgisi (integration_id gerekli)."}), 400

    gap = GapResult(
        integration_id   = int(gap_d["integration_id"]),
        integration_name = gap_d.get("integration_name", ""),
        params           = gap_d.get("params") or {},
        reason           = gap_d.get("reason", ""),
    )
    res  = ApprovalService().create_from_gap(
        gap, user_id=user_id, question=d.get("question", ""),
        filters=d.get("filters") or {}, session_id=d.get("session_id"),
    )
    appr = res["approval"]
    return jsonify({
        "approval_external_id": appr["external_id"],
        "approval_id"         : appr["id"],
        "approval_status"     : appr["status"],
        "deduped"             : res["deduped"],
    }), 201


@approvals_bp.route("/", methods=["GET"])
def list_approvals():
    guard = _require_admin()
    if guard: return guard
    status = request.args.get("status")    # PENDING / APPROVED
    limit  = int(request.args.get("limit", 50))
    rows   = ApprovalRepository().list_by_status(status=status, limit=limit)
    return jsonify({"total": len(rows), "items": rows})


@approvals_bp.route("/<int:approval_id>", methods=["GET"])
def get_approval(approval_id):
    guard = _require_admin()
    if guard: return guard
    appr = ApprovalRepository().get_by_id(approval_id)
    if not appr:
        return jsonify({"error": "Bulunamadı"}), 404
    appr["job"]   = JobRepository().get_by_approval(approval_id)
    appr["audit"] = AuditRepository().list_for("approval_request", approval_id)
    return jsonify(appr)


@approvals_bp.route("/<int:approval_id>/approve", methods=["POST"])
def approve(approval_id):
    guard = _require_admin()
    if guard: return guard
    note = (request.get_json(silent=True) or {}).get("note")
    res  = ApprovalService().approve(approval_id, admin_id=_user_id(request) or "admin", note=note)
    if res.get("error"):
        return jsonify({"error": res["error"]}), res.get("code", 400)
    return jsonify(res)


@approvals_bp.route("/<int:approval_id>/reject", methods=["POST"])
def reject(approval_id):
    guard = _require_admin()
    if guard: return guard
    note = (request.get_json(silent=True) or {}).get("note")
    res  = ApprovalService().reject(approval_id, admin_id=_user_id(request) or "admin", note=note)
    if res.get("error"):
        return jsonify({"error": res["error"]}), res.get("code", 400)
    return jsonify(res)


# ─────────────────────────────────────────────────────────────────────────────
@approvals_bp.route("/status/<external_id>", methods=["GET"])
def poll_status(external_id):
    """Kullanıcı polling — sonuç yalnızca talebin sahibine döner (PII koruması)."""
    out = ApprovalService().status_for_external(external_id, requester_id=_user_id(request))
    if out is None:
        return jsonify({"error": "Bulunamadı"}), 404
    return jsonify(out)


@approvals_bp.route("/by-session/<session_id>", methods=["GET"])
def by_session(session_id):
    """Bir sohbete ait onay taleplerinin durumları — sohbete dönünce kart yeniden çizimi."""
    items = ApprovalService().list_for_session(session_id, requester_id=_user_id(request))
    return jsonify({"total": len(items), "items": items})


@approvals_bp.route("/jobs/<int:job_id>", methods=["GET"])
def get_job(job_id):
    guard = _require_admin()
    if guard: return guard
    job = JobRepository().get_by_id(job_id)
    if not job:
        return jsonify({"error": "Bulunamadı"}), 404
    job["audit"] = AuditRepository().list_for("ingestion_job", job_id)
    return jsonify(job)


@approvals_bp.route("/run-worker", methods=["POST"])
def run_worker():
    """Worker'ı manuel tetikle (test/debug). Admin gerekir."""
    guard = _require_admin()
    if guard: return guard
    return jsonify(process_pending_jobs())
