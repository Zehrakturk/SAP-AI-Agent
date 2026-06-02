"""
DataWriter — kayıtları MSSQL hedef tablosuna yazar (bulk insert).
Aynı param_hash için eski kayıtları siler, sonra ekler (idempotent).
"""

from __future__ import annotations

from app.services.db                                import get_connection
from app.services.fetchers.persistence.schema_builder import SchemaBuilder


class DataWriter:

    def __init__(self, target_table: str):
        if not target_table:
            raise ValueError("target_table boş olamaz")
        self.target_table = target_table

    # ─────────────────────────────────────────────────────────────────────
    def write(self, records: list[dict], integration_id: int, param_hash: str) -> int:
        """
        Records'ı hedef tabloya bulk insert eder.
        Aynı (integration_id, param_hash) için eski satırlar silinir.
        Döner: yazılan satır sayısı.
        """
        if not records:
            return 0

        conn   = get_connection()
        cursor = conn.cursor()
        try:
            # 1. Tablo hazır mı?
            col_names = SchemaBuilder.ensure_table(cursor, self.target_table, records[0])
            conn.commit()

            # 2. Eski snapshot'ı temizle (re-fetch desteği)
            cursor.execute(
                f"DELETE FROM [{self.target_table}] "
                f"WHERE param_hash = ? AND integration_id = ?",
                (param_hash, integration_id),
            )

            # 3. Bulk INSERT
            placeholders = ",".join(["?"] * (len(col_names) + 2))
            insert_sql = (
                f"INSERT INTO [{self.target_table}] "
                f"(param_hash, integration_id, "
                f"{', '.join(f'[{c}]' for c in col_names)}) "
                f"VALUES ({placeholders})"
            )

            orig_keys = list(records[0].keys())
            rows_to_insert = []
            for rec in records:
                row_vals = [param_hash, integration_id]
                for key in orig_keys:
                    val = rec.get(key)
                    if val == "" or (isinstance(val, str) and val.strip() == ""):
                        val = None
                    row_vals.append(val)
                rows_to_insert.append(tuple(row_vals))

            cursor.fast_executemany = True
            cursor.executemany(insert_sql, rows_to_insert)
            conn.commit()
            return len(rows_to_insert)
        finally:
            conn.close()
