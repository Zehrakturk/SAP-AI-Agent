"""
data/index_schemas_to_qdrant.py

Standalone script — MSSQL'deki tum aktif entegrasyonlari Qdrant'a indexler.

Kullanim:
    cd SAP-AI
    python data/index_schemas_to_qdrant.py

    # Tek entegrasyon:
    python data/index_schemas_to_qdrant.py --id 1
"""

import sys
import os
import argparse

# Proje kokunu path'e ekle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.services.qdrant_indexer import index_integration, index_all_integrations


def main():
    parser = argparse.ArgumentParser(description="Integration semalarini Qdrant'a indexle")
    parser.add_argument("--id", type=int, default=None,
                        help="Indexlenecek integration_id (verilmezse tumu indexlenir)")
    args = parser.parse_args()

    if args.id:
        print(f"integration_id={args.id} indexleniyor...")
        try:
            count = index_integration(args.id)
            print(f"OK  {count} chunk indexlendi.")
        except Exception as e:
            print(f"HATA: {e}")
            sys.exit(1)
    else:
        print("Tum aktif entegrasyonlar indexleniyor...")
        results = index_all_integrations()
        ok  = sum(1 for v in results.values() if v.get("status") == "ok")
        err = sum(1 for v in results.values() if v.get("status") == "error")
        for name, info in results.items():
            if info.get("status") == "ok":
                print(f"  OK  {name}: {info['chunks']} chunk")
            else:
                print(f"  ERR {name}: {info.get('message', '?')}")
        print(f"\nSonuc: {ok} basarili, {err} hatali")


if __name__ == "__main__":
    main()
