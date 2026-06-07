"""
app/services/lifecycle/util.py — lifecycle modüllerinin ortak MSSQL yardımcıları.
"""

from __future__ import annotations

from app.services.db import get_connection


def table_exists(cursor, table: str) -> bool:
    cursor.execute("SELECT 1 FROM sys.tables WHERE name = ?", (table,))
    return cursor.fetchone() is not None


def columns_of(cursor, table: str) -> set[str]:
    """Tablonun kolon adları (UPPER)."""
    cursor.execute(
        "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = ?",
        (table,),
    )
    return {r[0].upper() for r in cursor.fetchall()}


def row_count(cursor, table: str) -> int:
    cursor.execute(
        "SELECT SUM(p.rows) FROM sys.partitions p "
        "JOIN sys.tables t ON t.object_id = p.object_id "
        "WHERE t.name = ? AND p.index_id IN (0, 1)",
        (table,),
    )
    r = cursor.fetchone()
    return int(r[0]) if r and r[0] is not None else 0


def size_kb(cursor, table: str) -> int:
    """Tablonun toplam ayrılmış alanı (KB)."""
    cursor.execute(
        "SELECT SUM(a.total_pages) * 8 "
        "FROM sys.allocation_units a "
        "JOIN sys.partitions p ON p.partition_id = a.container_id "
        "JOIN sys.tables t ON t.object_id = p.object_id "
        "WHERE t.name = ?",
        (table,),
    )
    r = cursor.fetchone()
    return int(r[0]) if r and r[0] is not None else 0


def compression_desc(cursor, table: str) -> str:
    """Tablonun veri sıkıştırma durumu (NONE / PAGE / ROW)."""
    cursor.execute(
        "SELECT TOP 1 p.data_compression_desc "
        "FROM sys.partitions p JOIN sys.tables t ON t.object_id = p.object_id "
        "WHERE t.name = ? AND p.index_id IN (0, 1)",
        (table,),
    )
    r = cursor.fetchone()
    return (r[0] if r and r[0] else "NONE")


def table_stats(table: str) -> dict:
    """Tek seferde satır + boyut + sıkıştırma özeti (yoksa exists=False)."""
    conn = get_connection()
    cur  = conn.cursor()
    try:
        if not table_exists(cur, table):
            return {"table": table, "exists": False}
        return {
            "table":       table,
            "exists":      True,
            "rows":        row_count(cur, table),
            "size_kb":     size_kb(cur, table),
            "compression": compression_desc(cur, table),
        }
    finally:
        conn.close()
