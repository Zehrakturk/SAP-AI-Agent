"""
data/migrate_integrations_v2.py

integrations tablosuna Factory pattern için gereken 3 yeni kolonu ekler:
  - service_type   NVARCHAR(20)  DEFAULT 'SOAP'
  - auth_type      NVARCHAR(20)  DEFAULT 'BASIC'
  - extra_config   NVARCHAR(MAX)            -- JSON

Idempotent — birden fazla çalıştırılabilir. Mevcut kayıtlara default değerler atanır.

Kullanım:
    cd SAP-AI
    python data/migrate_integrations_v2.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.services.db import get_connection


COLUMNS_TO_ADD = [
    ("service_type", "NVARCHAR(20)",  "'SOAP'"),
    ("auth_type",    "NVARCHAR(20)",  "'BASIC'"),
    ("extra_config", "NVARCHAR(MAX)", "NULL"),
]


def column_exists(cursor, table_name: str, column_name: str) -> bool:
    cursor.execute("""
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = ? AND COLUMN_NAME = ?
    """, (table_name, column_name))
    return cursor.fetchone() is not None


def main():
    print("=" * 60)
    print("  Migration: integrations -> Factory v2")
    print("=" * 60)

    conn   = get_connection()
    cursor = conn.cursor()

    for col_name, col_type, default in COLUMNS_TO_ADD:
        if column_exists(cursor, "integrations", col_name):
            print(f"  [SKIP] {col_name} zaten mevcut.")
            continue

        # 1. Kolonu ekle
        cursor.execute(
            f"ALTER TABLE integrations ADD [{col_name}] {col_type}"
        )
        conn.commit()
        print(f"  [ADD]  {col_name} ({col_type}) eklendi.")

        # 2. Default değer ata (mevcut satırlara) — NULL hariç
        if default != "NULL":
            cursor.execute(
                f"UPDATE integrations SET [{col_name}] = {default} "
                f"WHERE [{col_name}] IS NULL"
            )
            conn.commit()
            print(f"         -> Mevcut satırlara default {default} atandı.")

    # Mevcut SOAP entegrasyonlarına service_type='SOAP', auth_type='BASIC'
    # zaten yukarıda atandı. WSDL'i olmayan ama REST/OData olabilecek
    # entegrasyonlar için manuel UPDATE yapılması gerekir.

    print("\n  Kontrol:")
    cursor.execute("""
        SELECT id, name, service_type, auth_type,
               CASE WHEN extra_config IS NULL THEN '(null)' ELSE LEFT(extra_config, 50) END AS extra
        FROM integrations
        ORDER BY id
    """)
    rows = cursor.fetchall()
    print(f"  {'id':<4}{'name':<30}{'service_type':<14}{'auth_type':<12}extra_config")
    print(f"  {'-'*4}{'-'*30}{'-'*14}{'-'*12}{'-'*20}")
    for r in rows:
        print(f"  {r[0]:<4}{(r[1] or '')[:28]:<30}{(r[2] or ''):<14}{(r[3] or ''):<12}{r[4] or ''}")

    conn.close()
    print("\n[OK] Migration tamamlandi.")


if __name__ == "__main__":
    main()
