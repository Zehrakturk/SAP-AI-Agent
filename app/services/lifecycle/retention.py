"""
app/services/lifecycle/retention.py — sıcak pencere dışı ham satırları temizler.

Mantık (GÜVENLİ sıra):
  1. Ham tablonun en eski tarihini bul (lo). lo >= hot_start ise → temizlenecek bir şey yok, ATLA.
     (Bu kontrol kritik: zaten silinmiş bir pencereyi rollup'lamaya çalışıp kalıcı
      özet satırlarını YOK ETMEYİ önler.)
  2. Silinecek pencereyi [lo, hot_start-1] rollup'a al (ham hâlâ dururken).
  3. (opsiyonel) Arşiv tablosuna kopyala.
  4. Ham satırları sil: date < hot_start.

Sonuç: ham fact tablosu son HOT_WINDOW_MONTHS ayla SINIRLI kalır; eski dönem rollup'ta yaşar.
Varsayılan KAPALI (RETENTION_ENABLED=0) — bkz. lifecycle.__init__.
"""

from __future__ import annotations

import calendar
import datetime as _dt
import os

from app.services.db                import get_connection
from app.services.lifecycle.config  import FACT_TABLES
from app.services.lifecycle.rollup  import build_rollup
from app.services.lifecycle.util    import table_exists, columns_of


def _months_ago(d: _dt.date, months: int) -> _dt.date:
    y, m = d.year, d.month - months
    while m <= 0:
        m += 12
        y -= 1
    day = min(d.day, calendar.monthrange(y, m)[1])
    return d.replace(year=y, month=m, day=day)


def _raw_min_date(cur, table: str, date_col: str):
    cur.execute(f"SELECT MIN(TRY_CAST([{date_col}] AS DATE)) FROM [{table}]")
    r = cur.fetchone()
    return r[0] if r and r[0] else None


def enforce_retention(hot_window_months: int | None = None) -> dict:
    """Tüm fact tabloları için sıcak pencere dışını rollup'layıp ham'dan temizler."""
    months = hot_window_months if hot_window_months is not None \
        else int(os.getenv("HOT_WINDOW_MONTHS", "6"))
    archive = os.getenv("ARCHIVE_BEFORE_PURGE", "0") == "1"
    hot_start = _months_ago(_dt.date.today(), months)

    report: dict = {"hot_start": hot_start.isoformat(), "months": months, "tables": {}}

    for fact, cfg in FACT_TABLES.items():
        report["tables"][fact] = _retain_one(fact, cfg, hot_start, archive)
    return report


def _retain_one(fact: str, cfg: dict, hot_start: _dt.date, archive: bool) -> dict:
    date_col = cfg["date_col"]
    conn = get_connection()
    cur  = conn.cursor()
    try:
        if not table_exists(cur, fact):
            return {"status": "skipped", "reason": "tablo yok"}
        if date_col.upper() not in columns_of(cur, fact):
            return {"status": "skipped", "reason": f"{date_col} kolonu yok"}

        lo = _raw_min_date(cur, fact, date_col)
        if lo is None:
            return {"status": "empty"}
        if lo >= hot_start:
            return {"status": "nothing_to_purge", "oldest": lo.isoformat()}

        purge_to = hot_start - _dt.timedelta(days=1)

        # 2) Silinecek pencereyi rollup'la (ham hâlâ dururken!)
        roll = build_rollup(fact, from_date=lo, to_date=purge_to)

        # 3) Opsiyonel arşiv
        archived = 0
        if archive:
            arch = f"{fact}_archive"
            if not table_exists(cur, arch):
                cur.execute(
                    f"SELECT * INTO [{arch}] FROM [{fact}] "
                    f"WHERE TRY_CAST([{date_col}] AS DATE) < ?", (hot_start.isoformat(),)
                )
                archived = cur.rowcount
            else:
                cur.execute(
                    f"INSERT INTO [{arch}] SELECT * FROM [{fact}] "
                    f"WHERE TRY_CAST([{date_col}] AS DATE) < ?", (hot_start.isoformat(),)
                )
                archived = cur.rowcount
            conn.commit()

        # 4) Ham satırları sil
        cur.execute(
            f"DELETE FROM [{fact}] WHERE TRY_CAST([{date_col}] AS DATE) < ?",
            (hot_start.isoformat(),),
        )
        purged = cur.rowcount
        conn.commit()

        return {"status": "ok", "purged_before": hot_start.isoformat(),
                "rolled_window": [lo.isoformat(), purge_to.isoformat()],
                "rollup": roll, "purged_rows": int(purged) if purged is not None else None,
                "archived_rows": archived if archive else None}
    except Exception as e:
        conn.rollback()
        return {"status": "error", "error": str(e)}
    finally:
        conn.close()
