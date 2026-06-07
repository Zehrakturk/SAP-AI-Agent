"""
data/optimize_storage.py — Veri Yaşam Döngüsü tek seferlik kurulum / bakım script'i.

Yapar:
  1. ÖNCE durum raporu (satır / boyut / sıkıştırma) basar.
  2. Rollup tablolarını oluşturur + mevcut ham veriden TAM backfill eder.
  3. Fact + rollup tablolarına PAGE sıkıştırma uygular.
  4. SONRA durum raporu basar (kazanç).
  5. (opsiyonel) --purge verilirse retention çalıştırır (eski ham satırları siler).
     UYARI: --purge VERİ SİLER. Önce rollup'ın dolduğunu doğrulayın.
  6. (opsiyonel) --attribute-orphans <integration_id> ile integration_id=NULL ham
     satırlarını bir entegrasyona atar (firma izolasyonu için).

Kullanım:
    cd SAP-AI
    python data/optimize_storage.py                       # güvenli: rollup + sıkıştırma
    python data/optimize_storage.py --attribute-orphans 1 # NULL satırları int=1'e ata
    python data/optimize_storage.py --purge               # + retention (VERİ SİLER)
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Windows konsolu için UTF-8
import io
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
except Exception:
    pass

from dotenv import load_dotenv
load_dotenv()

from app.services.db                     import get_connection
from app.services.lifecycle.config       import FACT_TABLES
from app.services.lifecycle.util         import table_stats
from app.services.lifecycle.rollup       import backfill_all_rollups
from app.services.lifecycle.compression  import compress_fact_tables
from app.services.lifecycle.retention    import enforce_retention


def _all_tables() -> list[str]:
    out = []
    for fact, cfg in FACT_TABLES.items():
        out += [fact, cfg["rollup_table"]]
    return out


def _print_status(title: str):
    print(f"\n=== {title} ===")
    print(f"{'Tablo':<22}{'Satır':>10}{'Boyut(KB)':>12}{'Sıkıştırma':>14}")
    for t in _all_tables():
        s = table_stats(t)
        if not s.get("exists"):
            print(f"{t:<22}{'(yok)':>10}")
        else:
            print(f"{t:<22}{s['rows']:>10}{s['size_kb']:>12}{s['compression']:>14}")


def _attribute_orphans(integration_id: int):
    """integration_id=NULL ham fact satırlarını verilen entegrasyona atar."""
    print(f"\n[ORPHAN] integration_id=NULL satırları → {integration_id}")
    conn = get_connection(); cur = conn.cursor()
    try:
        for fact in FACT_TABLES:
            cur.execute("SELECT 1 FROM sys.tables WHERE name = ?", (fact,))
            if not cur.fetchone():
                continue
            if cur.execute(
                "SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_NAME=? AND COLUMN_NAME='integration_id'", (fact,)
            ).fetchone() is None:
                continue
            cur.execute(
                f"UPDATE [{fact}] SET integration_id = ? WHERE integration_id IS NULL",
                (integration_id,),
            )
            print(f"  {fact}: {cur.rowcount} satır güncellendi")
        conn.commit()
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--purge", action="store_true",
                    help="retention çalıştır (ESKİ HAM SATIRLARI SİLER)")
    ap.add_argument("--attribute-orphans", type=int, metavar="INT_ID",
                    help="integration_id=NULL satırları bu entegrasyona ata")
    ap.add_argument("--no-compress", action="store_true", help="sıkıştırmayı atla")
    args = ap.parse_args()

    _print_status("ÖNCE")

    if args.attribute_orphans is not None:
        _attribute_orphans(args.attribute_orphans)

    print("\n[1] Rollup backfill...")
    for fact, res in backfill_all_rollups().items():
        print(f"  {fact}: {res.get('status')} "
              f"(window={res.get('window')}, rows={res.get('rows')})")

    if not args.no_compress:
        print("\n[2] PAGE sıkıştırma...")
        for r in compress_fact_tables():
            print(f"  {r.get('table')}: {r.get('status')} "
                  f"{'(' + str(r.get('saved_kb')) + ' KB kazanıldı)' if r.get('saved_kb') else ''}")

    if args.purge:
        print("\n[3] Retention (PURGE) — eski ham satırlar siliniyor...")
        rep = enforce_retention()
        print(f"  sıcak başlangıç: {rep['hot_start']} ({rep['months']} ay)")
        for fact, info in rep["tables"].items():
            print(f"  {fact}: {info}")
    else:
        print("\n[3] Retention ATLANDI (--purge verilmedi). Veri silinmedi.")

    _print_status("SONRA")
    print("\n✓ Tamamlandı.")


if __name__ == "__main__":
    main()
