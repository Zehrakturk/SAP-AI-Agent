"""
app/api/insights.py — Insights motoru için REST API.

Endpoint'ler:
  GET    /api/v1/insights/                  — aktif insight'ları listele
  POST   /api/v1/insights/run               — manuel detector çalıştır (admin)
  POST   /api/v1/insights/<id>/view         — görüldü olarak işaretle
  POST   /api/v1/insights/<id>/dismiss      — kullanıcı kapattı
  POST   /api/v1/insights/explain           — bir karşılaştırma için hipotez üret
                                              (chat'in 'Olası Sebepler' bölümü buradan)
"""

from flask import Blueprint, request, jsonify

from app.services.insights              import generate_insights
from app.services.insights.repository    import InsightsRepository
from app.services.insights.hypothesis_engine import generate_hypotheses
from app.services.insights               import personalizer

insights_bp = Blueprint("insights", __name__)


def _current_user_id(req) -> str | None:
    """Demo token'dan user_id çıkar. Yoksa None döner (global insight'lar görünür)."""
    token = req.headers.get("Authorization", "").replace("Bearer ", "")
    if token.startswith("demo-token-"):
        parts = token.split("-")
        return parts[2] if len(parts) > 2 else None
    return None


# ─────────────────────────────────────────────────────────────────────────────
@insights_bp.route("/", methods=["GET"])
def list_insights():
    """
    Aktif insight'ları döner.
    Query: ?limit=20&include_dismissed=false
    """
    user_id  = _current_user_id(request)
    limit    = int(request.args.get("limit", 20))
    incl_dis = request.args.get("include_dismissed", "false").lower() == "true"

    rows = InsightsRepository().list_active(
        user_id=user_id, limit=limit, include_dismissed=incl_dis
    )
    # Kişiselleştirme — kullanıcının geçmiş sorgularına göre yeniden sırala
    if user_id:
        rows = personalizer.personalize(rows, user_id)
    return jsonify({"total": len(rows), "items": rows})


# ─────────────────────────────────────────────────────────────────────────────
@insights_bp.route("/interests", methods=["GET"])
def get_interests():
    """Kullanıcının ilgi profilini ve manuel seçimlerini döner (Settings UI için)."""
    user_id = _current_user_id(request)
    return jsonify({
        "available" : personalizer.available_interest_tags(),
        "manual"    : personalizer.get_manual_interests(user_id) if user_id else [],
        "computed"  : personalizer.compute_interest_profile(user_id) if user_id else {},
    })


@insights_bp.route("/interests", methods=["PUT"])
def set_interests():
    """Manuel ilgi alanlarını günceller. Body: {"interests": ["sevkiyat", "müşteri"]}"""
    user_id = _current_user_id(request)
    if not user_id:
        return jsonify({"error": "Kullanıcı kimliği yok."}), 401
    data = request.get_json(force=True) or {}
    saved = personalizer.set_manual_interests(user_id, data.get("interests") or [])
    return jsonify({"saved": saved})


# ─────────────────────────────────────────────────────────────────────────────
@insights_bp.route("/run", methods=["POST"])
def run_insights():
    """
    Manuel olarak detector'ları çalıştırır (test / admin).
    Body: {"detectors": ["trend_change", ...]} (opsiyonel)
    """
    user_id   = _current_user_id(request)
    data      = request.get_json(silent=True) or {}
    detectors = data.get("detectors") or None
    summary   = generate_insights(user_id=user_id, detector_names=detectors)
    return jsonify(summary)


# ─────────────────────────────────────────────────────────────────────────────
@insights_bp.route("/<int:insight_id>/view", methods=["POST"])
def mark_viewed(insight_id):
    InsightsRepository().mark_viewed(insight_id)
    return jsonify({"ok": True})


@insights_bp.route("/<int:insight_id>/dismiss", methods=["POST"])
def dismiss(insight_id):
    InsightsRepository().mark_dismissed(insight_id)
    return jsonify({"ok": True})


# ─────────────────────────────────────────────────────────────────────────────
@insights_bp.route("/explain", methods=["POST"])
def explain_change():
    """
    Karşılaştırma için 'Olası Sebepler' üretir.

    Body:
      {
        "table_name"     : "shipments",
        "integration_name": "Sevkiyat",
        "cur_start"  : "2026-04-08", "cur_end"  : "2026-04-15",
        "prev_start" : "2026-04-01", "prev_end" : "2026-04-07",
        "max"        : 3
      }
    """
    d = request.get_json(force=True) or {}
    tbl  = d.get("table_name")
    name = d.get("integration_name", tbl or "Veri")
    if not tbl or not d.get("cur_start") or not d.get("prev_start"):
        return jsonify({"error": "table_name + cur_start/end + prev_start/end gerekli"}), 400

    hyps = generate_hypotheses(
        table_name        = tbl,
        integration_name  = name,
        cur_start         = d["cur_start"],
        cur_end           = d["cur_end"],
        prev_start        = d["prev_start"],
        prev_end          = d["prev_end"],
        max_hypotheses    = int(d.get("max", 3)),
    )
    return jsonify({
        "hypotheses": [h.to_dict() for h in hyps],
        "count":      len(hyps),
    })
