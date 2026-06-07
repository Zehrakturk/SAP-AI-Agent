"""
app/services/lifecycle — Veri Yaşam Döngüsü Yönetimi.

MSSQL'in sınırsız büyümesini engeller:
  - compression : fact tablolarına PAGE sıkıştırma (idempotent)
  - watermark   : artımlı (incremental) çekme — sadece yeni veri
  - rollup      : eski veriyi günlük özet (shipments_daily / press_daily) tablolarına indirger
  - retention   : sıcak pencere (HOT_WINDOW_MONTHS) dışındaki ham satırları temizler

run_nightly_maintenance() APScheduler tarafından gece çağrılır (fetch + insights arasında).
"""

from __future__ import annotations

import os


def run_nightly_maintenance() -> dict:
    """
    Gecelik bakım: rollup → retention → (haftalık) sıkıştırma.
    Her adım kendi içinde hata yutar; tek bir adım patlarsa diğerleri çalışır.
    Döner: adım bazlı özet (debug/log).
    """
    report: dict = {}

    # 1) Rollup — eski/kapanmış dönemleri özet tablolara indir
    if os.getenv("ROLLUP_ENABLED", "1") == "1":
        try:
            from app.services.lifecycle.rollup import build_all_rollups
            report["rollup"] = build_all_rollups()
        except Exception as e:
            report["rollup"] = {"error": str(e)}

    # 2) Retention — sıcak pencere dışı ham satırları temizle (rollup garantili sonra)
    if os.getenv("RETENTION_ENABLED", "0") == "1":   # GÜVENLİK: varsayılan KAPALI
        try:
            from app.services.lifecycle.retention import enforce_retention
            report["retention"] = enforce_retention()
        except Exception as e:
            report["retention"] = {"error": str(e)}
    else:
        report["retention"] = {"skipped": "RETENTION_ENABLED=0"}

    return report
