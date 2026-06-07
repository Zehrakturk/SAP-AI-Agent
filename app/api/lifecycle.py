"""
app/api/lifecycle.py — Veri Yaşam Döngüsü durum/yönetim API'si (admin).

Endpoint'ler (prefix /api/v1/lifecycle):
  GET  /status           — tablo satır/boyut/sıkıştırma + watermark + sıcak pencere özeti
  POST /run-maintenance  — gecelik bakımı (rollup + retention) elle tetikle
  POST /compress         — fact + rollup tablolarına PAGE sıkıştırma uygula
"""

from __future__ import annotations

import os

from flask import Blueprint, request, jsonify

from app.services.tenant            import is_admin
from app.services.lifecycle.config  import FACT_TABLES
from app.services.lifecycle.util    import table_stats

lifecycle_bp = Blueprint("lifecycle", __name__)


def _admin_guard():
    return None if is_admin(request) else (jsonify({"error": "Admin yetkisi gerekli"}), 403)


@lifecycle_bp.route("/status", methods=["GET"])
def status():
    g = _admin_guard()
    if g:
        return g

    tables = []
    for fact, cfg in FACT_TABLES.items():
        tables.append({"role": "raw",    **table_stats(fact)})
        tables.append({"role": "rollup", **table_stats(cfg["rollup_table"])})

    # Aktif entegrasyon başına watermark (en son yüklenen tarih)
    watermarks = []
    try:
        from app.repositories.integration_repository import IntegrationRepository
        from app.services.lifecycle.watermark        import _date_col_for, get_watermark
        for cfg in IntegrationRepository().list_active():
            dc = _date_col_for(cfg)
            wm = get_watermark(cfg.id, cfg.effective_target_table(), dc) if dc else None
            watermarks.append({
                "integration_id": cfg.id, "name": cfg.name,
                "table": cfg.effective_target_table(), "date_col": dc,
                "watermark": wm.isoformat() if wm else None,
            })
    except Exception as e:
        watermarks = [{"error": str(e)}]

    return jsonify({
        "hot_window_months": int(os.getenv("HOT_WINDOW_MONTHS", "6")),
        "rollup_enabled":    os.getenv("ROLLUP_ENABLED", "1") == "1",
        "retention_enabled": os.getenv("RETENTION_ENABLED", "0") == "1",
        "archive_before_purge": os.getenv("ARCHIVE_BEFORE_PURGE", "0") == "1",
        "tables":     tables,
        "watermarks": watermarks,
    })


@lifecycle_bp.route("/run-maintenance", methods=["POST"])
def run_maintenance():
    g = _admin_guard()
    if g:
        return g
    from app.services.lifecycle import run_nightly_maintenance
    return jsonify(run_nightly_maintenance())


@lifecycle_bp.route("/compress", methods=["POST"])
def compress():
    g = _admin_guard()
    if g:
        return g
    from app.services.lifecycle.compression import compress_fact_tables
    return jsonify({"results": compress_fact_tables()})
