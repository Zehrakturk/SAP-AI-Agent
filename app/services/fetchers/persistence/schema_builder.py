"""
SchemaBuilder — hedef tabloyu MSSQL'de oluşturur / eksik kolonları ekler.
Eski dynamic_fetcher._ensure_table buradan devraldı.
"""

from __future__ import annotations

import re
from typing import Any


# Sistem kolonları — her hedef tabloda mevcut olur
_SYSTEM_COLS = """
    id             INT IDENTITY(1,1) PRIMARY KEY,
    fetched_at     DATETIME DEFAULT GETDATE(),
    param_hash     NVARCHAR(20)  NOT NULL,
    integration_id INT NOT NULL
"""


def _safe_col_name(key: str) -> str:
    """SAP/REST alan adını geçerli MSSQL kolon adına çevirir."""
    return re.sub(r"[^A-Za-z0-9_]", "_", str(key))[:64]


def _infer_sql_type(value: Any) -> str:
    if value is None:
        return "NVARCHAR(500)"
    v = str(value).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        return "NVARCHAR(10)"
    try:
        int(v)
        return "INT"
    except ValueError:
        pass
    try:
        float(v)
        return "FLOAT"
    except ValueError:
        pass
    return "NVARCHAR(500)"


class SchemaBuilder:
    """
    Tek public API:
        ensure_table(cursor, table_name, sample_row) → list[str] (data column names)
    """

    @staticmethod
    def ensure_table(cursor, table_name: str, sample_row: dict) -> list[str]:
        col_defs  = []
        col_names = []
        for key, val in sample_row.items():
            col      = _safe_col_name(key)
            sql_type = _infer_sql_type(val)
            col_defs.append(f"[{col}] {sql_type}")
            col_names.append(col)

        create_sql = f"""
            IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = '{table_name}')
            CREATE TABLE [{table_name}] (
                {_SYSTEM_COLS},
                {', '.join(col_defs)}
            )
        """
        cursor.execute(create_sql)

        # Eksik kolonları tespit et + ekle
        cursor.execute(
            "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = ?",
            (table_name,),
        )
        existing = {r[0].upper() for r in cursor.fetchall()}

        # Sistem kolonlarını mevcut (eski) tablolara da garanti et.
        # Var olan satırlar için NULL eklenir (NOT NULL + default yok hatası önlenir).
        _system_alters = {
            "PARAM_HASH"    : "param_hash NVARCHAR(20) NULL",
            "INTEGRATION_ID": "integration_id INT NULL",
            "FETCHED_AT"    : "fetched_at DATETIME DEFAULT GETDATE()",
        }
        for up_name, ddl in _system_alters.items():
            if up_name not in existing:
                cursor.execute(f"ALTER TABLE [{table_name}] ADD {ddl}")
                print(f"[SCHEMA] {table_name}: sistem kolonu eklendi -> {ddl.split()[0]}")

        for col, (_, val) in zip(col_names, sample_row.items()):
            if col.upper() not in existing:
                sql_type = _infer_sql_type(val)
                cursor.execute(f"ALTER TABLE [{table_name}] ADD [{col}] {sql_type}")
                print(f"[SCHEMA] {table_name}: '{col}' kolonu eklendi.")

        return col_names
