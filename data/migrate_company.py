"""
data/migrate_company.py — integrations tablosuna 'company' kolonu ekler ve seed eder.

Kullanım:
    cd SAP-AI
    python data/migrate_company.py

Eşleme (kullanıcı talebine göre):
    shipments (id=1)            -> Warmhaus
    diğer tüm entegrasyonlar    -> Beycelik
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.services.db import get_connection


def migrate():
    conn = get_connection()
    cur = conn.cursor()

    # 1. company kolonu yoksa ekle
    cur.execute("""
        IF COL_LENGTH('integrations', 'company') IS NULL
            ALTER TABLE integrations ADD company NVARCHAR(50) NULL
    """)
    conn.commit()
    print("[MIGRATE] company kolonu hazır.")

    # 2. Seed: shipments -> Warmhaus, diğerleri -> Beycelik (yalnız NULL olanlar)
    cur.execute("""
        UPDATE integrations SET company = 'Warmhaus'
        WHERE LOWER(name) = 'shipments' AND (company IS NULL OR company = '')
    """)
    cur.execute("""
        UPDATE integrations SET company = 'Beycelik'
        WHERE LOWER(name) <> 'shipments' AND (company IS NULL OR company = '')
    """)
    conn.commit()

    cur.execute("SELECT id, name, company FROM integrations ORDER BY id")
    print("[MIGRATE] Sonuç:")
    for r in cur.fetchall():
        print(f"   id={r[0]}  {r[1]:<20} -> {r[2]}")
    conn.close()
    print("[MIGRATE] Tamamlandı.")


if __name__ == "__main__":
    migrate()
