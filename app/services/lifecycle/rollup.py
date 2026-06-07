"""
app/services/lifecycle/rollup.py — ham fact tablolarını günlük özet (rollup) tablolarına indirger.

Rollup tabloları KÜÇÜK ve hızlıdır; trend/aylık/eski-dönem sorguları bunları kullanır.
Ham satırlar retention ile silinse de rollup KORUNUR (özet kalıcıdır).

build_rollup(table, from_date, to_date):
  - Yalnız [from_date, to_date] penceresini yeniden hesaplar (idempotent: o pencereyi
    önce siler sonra ekler). Pencere DIŞINDAKİ rollup satırlarına DOKUNMAZ → birikimli.
  - Gruplama daima gun + integration_id + company → firma izolasyonu korunur
    (paylaşılan shipments tablosu güvenli).
"""

from __future__ import annotations

import datetime as _dt

from app.services.db                import get_connection
from app.services.lifecycle.config  import FACT_TABLES
from app.services.lifecycle.util    import table_exists, columns_of


def _measure_type(name: str, expr: str) -> str:
    e = expr.strip().upper()
    if "count" in name.lower() or e.startswith("COUNT"):
        return "BIGINT"
    return "FLOAT"


def ensure_rollup_table(cursor, fact_table: str) -> str:
    """Rollup tablosunu (yoksa) config'e göre oluşturur. Döner: rollup tablo adı."""
    cfg     = FACT_TABLES[fact_table]
    rollup  = cfg["rollup_table"]
    if table_exists(cursor, rollup):
        return rollup

    cols = [
        "gun DATE NOT NULL",
        "integration_id INT NULL",
        "company NVARCHAR(50) NULL",
    ]
    cols += [f"[{dest}] NVARCHAR(255) NULL" for _src, dest in cfg["group_dims"]]
    cols += [f"[{dest}] NVARCHAR(255) NULL" for _expr, dest in cfg["label_cols"]]
    cols += [f"[{name}] {_measure_type(name, expr)} NULL"
             for name, expr in cfg["measures"]]
    cols.append("rolled_at DATETIME2 DEFAULT SYSDATETIME()")

    cursor.execute(f"CREATE TABLE [{rollup}] (\n  " + ",\n  ".join(cols) + "\n)")
    cursor.execute(
        f"CREATE INDEX IX_{rollup}_gun ON [{rollup}] (gun, integration_id)"
    )
    return rollup


def _date_bounds(cursor, fact_table: str, date_col: str):
    cursor.execute(
        f"SELECT MIN(TRY_CAST([{date_col}] AS DATE)), MAX(TRY_CAST([{date_col}] AS DATE)) "
        f"FROM [{fact_table}]"
    )
    r = cursor.fetchone()
    return (r[0], r[1]) if r else (None, None)


def build_rollup(fact_table: str,
                 from_date: str | _dt.date | None = None,
                 to_date:   str | _dt.date | None = None) -> dict:
    """
    fact_table'ın [from_date, to_date] penceresini rollup tablosuna (yeniden) yazar.
    Tarihler None ise tablodaki tüm dönem (min..max) işlenir (backfill).
    """
    if fact_table not in FACT_TABLES:
        return {"table": fact_table, "status": "skipped", "reason": "config yok"}

    cfg      = FACT_TABLES[fact_table]
    date_col = cfg["date_col"]

    conn = get_connection()
    cur  = conn.cursor()
    try:
        if not table_exists(cur, fact_table):
            return {"table": fact_table, "status": "skipped", "reason": "fact tablo yok"}

        # Gerekli kolonlar mevcut mu? (Press gibi şeması belirsiz tablolarda güvenlik)
        present = columns_of(cur, fact_table)
        if date_col.upper() not in present:
            return {"table": fact_table, "status": "skipped",
                    "reason": f"{date_col} kolonu yok"}

        rollup = ensure_rollup_table(cur, fact_table)
        conn.commit()

        # Pencere belirle
        if from_date is None or to_date is None:
            lo, hi = _date_bounds(cur, fact_table, date_col)
            from_date = from_date or lo
            to_date   = to_date   or hi
        if from_date is None or to_date is None:
            return {"table": fact_table, "status": "empty", "rows": 0}

        f = from_date.isoformat() if isinstance(from_date, _dt.date) else str(from_date)
        t = to_date.isoformat()   if isinstance(to_date,   _dt.date) else str(to_date)

        # group_dims yalnız mevcut kolonlarla (Press güvenliği)
        dims   = [(src, dest) for src, dest in cfg["group_dims"]
                  if src.upper() in present]
        labels = cfg["label_cols"]   # MAX(...) ifadeleri; eksik kolon olası → tabloya göre filtrele
        labels = [(expr, dest) for expr, dest in labels
                  if all(c in present for c in _cols_in_expr(expr, present))]

        # SELECT / GROUP BY parçalarını kur
        sel_dims   = [f"s.[{src}] AS [{dest}]" for src, dest in dims]
        grp_dims   = [f"s.[{src}]"             for src, _d  in dims]
        sel_labels = [f"{expr} AS [{dest}]"    for expr, dest in labels]
        sel_meas   = [f"{expr} AS [{name}]"    for name, expr in cfg["measures"]]

        insert_cols = (["gun", "integration_id", "company"]
                       + [d for _s, d in dims]
                       + [d for _e, d in labels]
                       + [n for n, _e in cfg["measures"]])
        insert_cols_sql = ", ".join(f"[{c}]" for c in insert_cols)

        select_sql = ",\n  ".join(
            [f"TRY_CAST(s.[{date_col}] AS DATE)", "s.integration_id", "i.company"]
            + sel_dims + sel_labels + sel_meas
        )
        group_sql = ", ".join(
            [f"TRY_CAST(s.[{date_col}] AS DATE)", "s.integration_id", "i.company"] + grp_dims
        )

        # 1) Pencereyi temizle (idempotent)
        cur.execute(f"DELETE FROM [{rollup}] WHERE gun BETWEEN ? AND ?", (f, t))
        # 2) Yeniden hesapla
        cur.execute(
            f"INSERT INTO [{rollup}] ({insert_cols_sql})\n"
            f"SELECT\n  {select_sql}\n"
            f"FROM [{fact_table}] s\n"
            f"LEFT JOIN integrations i ON i.id = s.integration_id\n"
            f"WHERE TRY_CAST(s.[{date_col}] AS DATE) BETWEEN ? AND ?\n"
            f"GROUP BY {group_sql}",
            (f, t),
        )
        written = cur.rowcount
        conn.commit()

        return {"table": fact_table, "rollup_table": rollup, "status": "ok",
                "window": [f, t], "rows": int(written) if written is not None else None}
    except Exception as e:
        conn.rollback()
        return {"table": fact_table, "status": "error", "error": str(e)}
    finally:
        conn.close()


def _cols_in_expr(expr: str, present: set[str]) -> list[str]:
    """İfadede geçen ve mevcut kolonlarla eşleşen sütun adları (label güvenliği)."""
    import re
    tokens = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", expr))
    return [tok for tok in tokens if tok.upper() in present]


def rollup_hint_for(fact_tables: list[str]) -> str:
    """
    Verilen ham tablolara karşılık gelen rollup tablolarının (varsa) prompt'a
    eklenecek tanım + kullanım kuralı metnini üretir. query_engine bunu NL→SQL
    prompt'una enjekte eder → LLM trend/eski-dönem sorularında rollup'ı seçer.
    """
    if not fact_tables:
        return ""
    conn = get_connection()
    cur  = conn.cursor()
    try:
        hints = []
        for fact in fact_tables:
            cfg = FACT_TABLES.get(fact)
            if not cfg:
                continue
            rt = cfg["rollup_table"]
            if not table_exists(cur, rt):
                continue
            dims = ", ".join(d for _s, d in cfg["group_dims"])
            meas = ", ".join(n for n, _e in cfg["measures"])
            hints.append(
                f"- [{rt}]: '{fact}' tablosunun GÜNLÜK ÖZETİ. "
                f"Kolonlar: gun (DATE), integration_id, company"
                + (f", {dims}" if dims else "")
                + (f", {meas}" if meas else "")
                + "."
            )
        if not hints:
            return ""
        return (
            "\n=== ROLLUP (ÖZET) TABLOLAR ===\n"
            + "\n".join(hints)
            + "\nKURAL: ÇOK DÖNEMLİ trend/zaman serisi (aylık/çeyreklik/yıllık karşılaştırma) "
              "veya 6 aydan eski dönem sorularında HAM tablo yerine ilgili ROLLUP tablosunu kullan "
              "(çok daha hızlı; eski veri yalnız burada olabilir). 'gun' kolonuyla filtrele/grupla "
              "ve SADECE rollup'ın kendi ölçü kolonlarını (shipment_count, item_count, total_qty...) "
              "kullan. NOT: shipment_count bir YAKLAŞIK tekil sayımdır. TEK bir dönem için KESİN "
              "rakam/tekil sayım (ör. 'Nisan'da kaç sevkiyat') veya satır-detayı gerekiyorsa HAM "
              "tabloyu ve metrik ifadelerini kullan."
        )
    finally:
        conn.close()


def build_all_rollups(window_days: int = 3) -> dict:
    """
    Gecelik kullanım: tüm fact tablolar için SON window_days günü (yeni/güncel veri)
    yeniden rollup'lar. Eski rollup'lar (backfill ile yapılmış) korunur.
    """
    today = _dt.date.today()
    start = today - _dt.timedelta(days=window_days)
    out = {}
    for fact in FACT_TABLES:
        out[fact] = build_rollup(fact, from_date=start, to_date=today)
    return out


def backfill_all_rollups() -> dict:
    """Tek seferlik tam backfill: her fact tablonun TÜM dönemi rollup'lanır."""
    return {fact: build_rollup(fact) for fact in FACT_TABLES}
