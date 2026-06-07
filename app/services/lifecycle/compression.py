"""
app/services/lifecycle/compression.py — fact tablolarına PAGE veri sıkıştırma.

PAGE sıkıştırma nvarchar-ağırlıklı SAP fact tablolarında genelde 3-5x yer kazandırır
ve okuma performansını artırır. İdempotenttir: zaten PAGE ise atlar.

columnstore index OLTP upsert'ü yavaşlatabileceği için varsayılan KAPALI; yalnız
okuma-ağırlıklı rollup/arşiv tablolarında flag ile açılabilir (v2).
"""

from __future__ import annotations

from app.services.db                  import get_connection
from app.services.lifecycle.config    import FACT_TABLES
from app.services.lifecycle.util      import (
    table_exists, compression_desc, size_kb,
)


def apply_page_compression(table: str) -> dict:
    """
    Tek tabloya PAGE sıkıştırma uygular (idempotent).
    Döner: {table, status, before_kb, after_kb, compression}
    """
    conn = get_connection()
    cur  = conn.cursor()
    try:
        if not table_exists(cur, table):
            return {"table": table, "status": "skipped", "reason": "tablo yok"}

        current = compression_desc(cur, table)
        if current == "PAGE":
            return {"table": table, "status": "already", "compression": "PAGE"}

        before = size_kb(cur, table)
        # Heap veya clustered index — REBUILD her ikisini de sıkıştırır.
        cur.execute(f"ALTER TABLE [{table}] REBUILD WITH (DATA_COMPRESSION = PAGE)")
        conn.commit()
        after = size_kb(cur, table)

        return {
            "table": table, "status": "compressed",
            "before_kb": before, "after_kb": after,
            "saved_kb": max(before - after, 0),
            "compression": compression_desc(cur, table),
        }
    except Exception as e:
        return {"table": table, "status": "error", "error": str(e)}
    finally:
        conn.close()


def compress_fact_tables(include_rollups: bool = True) -> list[dict]:
    """
    Bilinen tüm fact (ve opsiyonel rollup) tablolarına PAGE sıkıştırma uygular.
    Var olmayan tablolar zarifçe atlanır.
    """
    targets: list[str] = list(FACT_TABLES.keys())
    if include_rollups:
        targets += [cfg["rollup_table"] for cfg in FACT_TABLES.values()]

    return [apply_page_compression(t) for t in targets]
