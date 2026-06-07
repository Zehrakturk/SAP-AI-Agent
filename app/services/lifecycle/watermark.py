"""
app/services/lifecycle/watermark.py — artımlı (incremental) çekme.

Watermark ayrı tabloda tutulmaz; hedef fact tablosundaki o entegrasyona ait
EN BÜYÜK tarihten türetilir (kendini düzelten, ekstra durum yok).

incremental_params(config) → {"start_date", "end_date"} üretir; SapDateMapper bunları
ISTART_DATE / IFINISH_DATE gibi SAP parametrelerine eşler. Tarih parametresi olmayan
veya henüz verisi olmayan entegrasyonlarda boş dict döner → entegrasyon kendi
varsayılanlarıyla (ilk/tam yükleme) çalışır.
"""

from __future__ import annotations

import datetime as _dt

from app.services.db                import get_connection
from app.services.lifecycle.config  import FACT_TABLES
from app.services.lifecycle.util    import table_exists, columns_of


def _date_col_for(config) -> str | None:
    """Entegrasyonun hedef tablosundaki dönem kolonu (config'ten)."""
    target = config.effective_target_table()
    return (FACT_TABLES.get(target) or {}).get("date_col")


def _has_date_param(config) -> bool:
    for p in config.params:
        name = (p.param_name or "").upper()
        ptype = (p.param_type or "").upper()
        if "DATE" in name or "DATE" in ptype:
            return True
    return False


def get_watermark(integration_id: int, table: str, date_col: str):
    """Tabloda bu entegrasyona ait en büyük tarih (date) veya None."""
    conn = get_connection()
    cur  = conn.cursor()
    try:
        if not table_exists(cur, table):
            return None
        if date_col.upper() not in columns_of(cur, table):
            return None
        cur.execute(
            f"SELECT MAX(TRY_CAST([{date_col}] AS DATE)) "
            f"FROM [{table}] WHERE integration_id = ?",
            (integration_id,),
        )
        r = cur.fetchone()
        return r[0] if r and r[0] else None
    finally:
        conn.close()


def incremental_params(config) -> dict:
    """
    Artımlı çekme parametreleri. Watermark gününü DAHİL ederek başlatır
    (aynı güne geç gelen kayıtları yakalamak için; DataWriter MERGE ile dedup eder).
    """
    if not _has_date_param(config):
        return {}                      # tarih param yok → artımlı uygulanamaz

    date_col = _date_col_for(config)
    if not date_col:
        return {}                      # tablonun dönem kolonu bilinmiyor → defaults

    wm = get_watermark(config.id, config.effective_target_table(), date_col)
    if not wm:
        return {}                      # ilk yükleme → entegrasyon defaults'u

    start = wm.isoformat()             # overlap (aynı gün güncellemeleri için)
    end   = _dt.date.today().isoformat()
    return {"start_date": start, "end_date": end}
