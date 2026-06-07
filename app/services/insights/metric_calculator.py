"""
metric_calculator — detector'ların ortak SQL yardımcıları.

Aktif entegrasyonların target_table'larını okuyup zaman bazlı agregasyon yapar.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing   import Any

from app.services.db import get_connection


def _exec(sql: str, params: tuple = ()) -> list[dict]:
    conn   = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql, params)
        cols = [c[0] for c in cursor.description] if cursor.description else []
        return [dict(zip(cols, r)) for r in cursor.fetchall()]
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# Entegrasyon listesi
# ─────────────────────────────────────────────────────────────────────────────

def list_active_integrations(company: str | None = None) -> list[dict]:
    """
    is_active=1 + target_table dolu olanları döner.
    company verilirse (ve 'ALL' değilse) yalnız o firmanınkiler.
    """
    where  = "WHERE i.is_active = 1"
    params : tuple = ()
    if company and company != "ALL":
        # company kolonu yoksa filtre atlanır (geriye uyum)
        chk = _exec("SELECT 1 AS x FROM INFORMATION_SCHEMA.COLUMNS "
                    "WHERE TABLE_NAME='integrations' AND COLUMN_NAME='company'")
        if chk:
            where += " AND i.company = ?"
            params = (company,)
    sql = f"""
        SELECT i.id, i.name,
               (SELECT TOP 1 target_table
                FROM integration_schemas
                WHERE integration_id = i.id) AS target_table
        FROM   integrations i
        {where}
    """
    rows = _exec(sql, params)
    return [r for r in rows if r.get("target_table")]


def table_exists(table_name: str) -> bool:
    rows = _exec(
        "SELECT 1 AS x FROM sys.tables WHERE name = ?", (table_name,)
    )
    return bool(rows)


def column_exists(table_name: str, column_name: str) -> bool:
    rows = _exec("""
        SELECT 1 AS x FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = ? AND COLUMN_NAME = ?
    """, (table_name, column_name))
    return bool(rows)


def _pick_date_column(table_name: str) -> str | None:
    """Yaygın tarih kolonu adlarından mevcut olanı döner."""
    candidates = ["ERDAT", "FIDATUM", "SDATUM", "WADAT_IST", "DPLBG",
                  "TARIH", "DATE", "CREATED_AT", "fetched_at"]
    for col in candidates:
        if column_exists(table_name, col):
            return col
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Sayım — tarih aralığı bazlı
# ─────────────────────────────────────────────────────────────────────────────

def count_records(table_name: str, start: str, end: str,
                  date_column: str | None = None) -> int:
    """
    İki tarih arası (her ikisi dahil) kayıt sayısı.
    Tarih kolonu otomatik tespit edilir veya parametre olarak geçilir.
    """
    if not table_exists(table_name):
        return 0
    date_col = date_column or _pick_date_column(table_name)
    if not date_col:
        # Tarih kolonu yoksa tüm tabloyu say
        rows = _exec(f"SELECT COUNT(*) AS c FROM [{table_name}]")
        return int(rows[0].get("c") or 0) if rows else 0

    # NVARCHAR 'YYYY-MM-DD' formatı varsayılır — TRY_CAST güvenli
    rows = _exec(
        f"SELECT COUNT(*) AS c FROM [{table_name}] "
        f"WHERE TRY_CAST([{date_col}] AS DATE) BETWEEN ? AND ?",
        (start, end)
    )
    return int(rows[0].get("c") or 0) if rows else 0


def sum_column(table_name: str, sum_col: str, start: str, end: str,
               date_column: str | None = None) -> float:
    if not table_exists(table_name) or not column_exists(table_name, sum_col):
        return 0.0
    date_col = date_column or _pick_date_column(table_name)
    where = (f"WHERE TRY_CAST([{date_col}] AS DATE) BETWEEN ? AND ?"
             if date_col else "")
    params = (start, end) if date_col else ()
    rows = _exec(
        f"SELECT SUM(TRY_CAST([{sum_col}] AS FLOAT)) AS s "
        f"FROM [{table_name}] {where}",
        params,
    )
    return float(rows[0]["s"] or 0) if rows else 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Dimension bazlı kırılım
# ─────────────────────────────────────────────────────────────────────────────

def group_by_dimension(table_name: str, dimension: str, start: str, end: str,
                       date_column: str | None = None,
                       top_n: int = 10) -> list[dict]:
    """
    Bir tarih aralığında dimension bazlı sayım (örn: MUSTERI_ADI → adet).
    En yüksek N tanesi döner.
    """
    if not table_exists(table_name) or not column_exists(table_name, dimension):
        return []
    date_col = date_column or _pick_date_column(table_name)
    where = (f"WHERE TRY_CAST([{date_col}] AS DATE) BETWEEN ? AND ?"
             if date_col else "")
    params = (start, end) if date_col else ()
    rows = _exec(
        f"SELECT TOP {int(top_n)} [{dimension}] AS dim, COUNT(*) AS adet "
        f"FROM [{table_name}] {where} "
        f"GROUP BY [{dimension}] "
        f"ORDER BY adet DESC",
        params,
    )
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Tarih yardımcıları
# ─────────────────────────────────────────────────────────────────────────────

def previous_period(start: str, end: str) -> tuple[str, str]:
    """Verilen aralığın önceki dönemini döner (aynı uzunlukta)."""
    s = datetime.fromisoformat(start)
    e = datetime.fromisoformat(end)
    length = (e - s).days + 1
    prev_end   = s - timedelta(days=1)
    prev_start = prev_end - timedelta(days=length - 1)
    return prev_start.date().isoformat(), prev_end.date().isoformat()


def last_n_days(n: int, today: datetime | None = None) -> tuple[str, str]:
    """Bugünden geriye N günlük aralık (bugün dahil)."""
    today = today or datetime.now()
    end   = today.date()
    start = end - timedelta(days=n - 1)
    return start.isoformat(), end.isoformat()


# ─────────────────────────────────────────────────────────────────────────────
# Günlük zaman serisi (korelasyon için)
# ─────────────────────────────────────────────────────────────────────────────

def daily_counts(table_name: str, start: str, end: str,
                 date_column: str | None = None) -> dict[str, int]:
    """
    Tarih aralığındaki günlük kayıt sayısını döner: {"2026-05-25": 42, ...}.
    Veri olmayan günler sözlükte yer almaz — caller 0 ile doldurur.
    """
    if not table_exists(table_name):
        return {}
    date_col = date_column or _pick_date_column(table_name)
    if not date_col:
        return {}
    rows = _exec(
        f"SELECT CONVERT(VARCHAR(10), TRY_CAST([{date_col}] AS DATE), 23) AS gun, "
        f"       COUNT(*) AS adet "
        f"FROM [{table_name}] "
        f"WHERE TRY_CAST([{date_col}] AS DATE) BETWEEN ? AND ? "
        f"GROUP BY CONVERT(VARCHAR(10), TRY_CAST([{date_col}] AS DATE), 23)",
        (start, end),
    )
    return {r["gun"]: int(r["adet"] or 0) for r in rows if r.get("gun")}


def date_series(start: str, end: str) -> list[str]:
    """start..end (dahil) arası tüm günlerin ISO listesini döner."""
    s = datetime.fromisoformat(start).date()
    e = datetime.fromisoformat(end).date()
    out = []
    cur = s
    while cur <= e:
        out.append(cur.isoformat())
        cur += timedelta(days=1)
    return out
