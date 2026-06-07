"""
DataWriter — kayıtları MSSQL hedef tablosuna yazar (bulk insert).
Aynı param_hash için eski kayıtları siler, sonra ekler (idempotent).

Değerler HEDEF KOLON TİPİNE göre dönüştürülür:
  - date/datetime  → SAP 'YYYYMMDD' / 'YYYY-MM-DD' normalize; geçersiz/0000 → NULL
  - int            → int(float(x)); olmazsa NULL
  - float/decimal  → float(x); olmazsa NULL
  - diğer (nvarchar)→ str; boş → NULL
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal  import Decimal

from app.services.db                                import get_connection
from app.services.fetchers.persistence.schema_builder import SchemaBuilder


def _norm_date(val):
    """SAP tarihini 'YYYY-MM-DD'e çevirir; geçersiz/sıfır tarih → None."""
    if val is None:
        return None
    if isinstance(val, (datetime, date)):
        return val.isoformat()[:10]
    s = str(val).strip()
    if not s or s.startswith("0000") or set(s) <= {"0"}:
        return None
    clean = s.replace("-", "").replace("/", "").replace(".", "")
    if len(clean) == 8 and clean.isdigit():
        return f"{clean[:4]}-{clean[4:6]}-{clean[6:8]}"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s
    return None   # tanınmayan tarih → NULL (cast hatası önlenir)


def _coerce_for_type(val, sql_type: str | None):
    """Değeri hedef kolon tipine uygun Python tipine çevirir."""
    if val is None:
        return None
    if isinstance(val, str) and val.strip() == "":
        return None

    t = (sql_type or "").lower()

    if t in ("date", "datetime", "datetime2", "smalldatetime"):
        return _norm_date(val)

    if t in ("int", "bigint", "smallint", "tinyint"):
        try:
            return int(float(str(val)))
        except (ValueError, TypeError):
            return None

    if t in ("float", "real", "decimal", "numeric", "money", "smallmoney"):
        try:
            return float(val) if isinstance(val, (int, float, Decimal)) else float(str(val))
        except (ValueError, TypeError):
            return None

    if t == "bit":
        return 1 if str(val).strip().lower() in ("1", "true", "x", "yes") else 0

    # nvarchar / varchar / text / diğer → string
    if isinstance(val, Decimal):
        return str(val)
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    return str(val)


class DataWriter:

    def __init__(self, target_table: str):
        if not target_table:
            raise ValueError("target_table boş olamaz")
        self.target_table = target_table

    # ─────────────────────────────────────────────────────────────────────
    @staticmethod
    def _column_types(cursor, table: str) -> dict[str, str]:
        cursor.execute(
            "SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = ?",
            (table,),
        )
        return {r[0].upper(): (r[1] or "").lower() for r in cursor.fetchall()}

    @staticmethod
    def _pk_columns(cursor, table: str) -> list[str]:
        """Tablonun PRIMARY KEY kolonlarını döner (yoksa boş liste)."""
        cursor.execute("""
            SELECT kcu.COLUMN_NAME
            FROM   INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
            JOIN   INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
                   ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
            WHERE  tc.TABLE_NAME = ? AND tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
            ORDER  BY kcu.ORDINAL_POSITION
        """, (table,))
        return [r[0] for r in cursor.fetchall()]

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
            # 1. Tablo hazır mı? (sistem + veri kolonları garanti)
            col_names = SchemaBuilder.ensure_table(cursor, self.target_table, records[0])
            conn.commit()

            # 1b. Kolon tipleri + PK kolonları
            type_map = self._column_types(cursor, self.target_table)
            pk_cols  = self._pk_columns(cursor, self.target_table)
            pk_upper = {p.upper() for p in pk_cols}

            # 2. Satır değerlerini hazırla — sıra: [param_hash, integration_id, *data]
            value_cols = ["param_hash", "integration_id"] + list(col_names)
            orig_keys  = list(records[0].keys())   # ham anahtarlar (col_names ile aynı sıra)
            rows_to_insert = []
            for rec in records:
                row_vals = [param_hash, integration_id]
                for raw_key, safe_col in zip(orig_keys, col_names):
                    row_vals.append(_coerce_for_type(rec.get(raw_key),
                                                     type_map.get(safe_col.upper())))
                rows_to_insert.append(tuple(row_vals))

            placeholders = ",".join(["?"] * len(value_cols))

            if pk_cols:
                # 3a. Doğal PK var → MERGE (upsert). Duplicate key hatası önlenir,
                #     mevcut kayıtlar güncellenir, yeniler eklenir.
                src_cols    = ", ".join(f"[{c}]" for c in value_cols)
                on_clause   = " AND ".join(f"t.[{pk}] = s.[{pk}]" for pk in pk_cols)
                update_cols = [c for c in value_cols if c.upper() not in pk_upper]
                update_set  = ", ".join(f"t.[{c}] = s.[{c}]" for c in update_cols)
                insert_cols = ", ".join(f"[{c}]" for c in value_cols)
                insert_vals = ", ".join(f"s.[{c}]" for c in value_cols)
                stmt = (
                    f"MERGE [{self.target_table}] AS t "
                    f"USING (VALUES ({placeholders})) AS s ({src_cols}) "
                    f"ON {on_clause} "
                    f"WHEN MATCHED THEN UPDATE SET {update_set} "
                    f"WHEN NOT MATCHED THEN INSERT ({insert_cols}) VALUES ({insert_vals});"
                )
            else:
                # 3b. PK yok → eski snapshot'ı param_hash'e göre sil + bulk insert
                cursor.execute(
                    f"DELETE FROM [{self.target_table}] "
                    f"WHERE param_hash = ? AND integration_id = ?",
                    (param_hash, integration_id),
                )
                insert_cols = ", ".join(f"[{c}]" for c in value_cols)
                stmt = (
                    f"INSERT INTO [{self.target_table}] ({insert_cols}) "
                    f"VALUES ({placeholders})"
                )

            cursor.fast_executemany = True
            cursor.executemany(stmt, rows_to_insert)
            conn.commit()
            return len(rows_to_insert)
        finally:
            conn.close()
