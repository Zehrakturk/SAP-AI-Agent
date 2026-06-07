"""
data/seed_metrics.py — Semantic Layer için başlangıç metriklerini ekler (idempotent).

Kullanım:
    cd SAP-AI
    python data/seed_metrics.py

Kapsam (her iki firma):
  - shipments (Warmhaus int=1 & Beyçelik int=3, aynı tablo) → GLOBAL metrikler
    (company=NULL, integration_id=NULL). Ölçüler AKTİF; durum/gecikme filtreleri
    TASLAK (is_active=0) — kolon/kod semantiği admin tarafından doğrulanmalı.
  - Press (Beyçelik int=2) → günlük üretim kayıt sayısı.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import io
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
except Exception:
    pass

from dotenv import load_dotenv
load_dotenv()

from app.services.db import get_connection
from app.services import semantic_layer


SEED = [
    # ── shipments ölçüleri (GLOBAL, aktif) ────────────────────────────────────
    dict(table_name="shipments", metric_key="sevkiyat_sayisi", label="Sevkiyat Sayısı",
         metric_type="measure", expression="COUNT(DISTINCT TKNUM)", unit="adet",
         synonyms="sevkiyat sayısı,kaç sevkiyat,sevkiyat adedi,toplam sevkiyat",
         description="Benzersiz sevkiyat (TKNUM) sayısı.", is_active=True),
    dict(table_name="shipments", metric_key="kalem_sayisi", label="Kalem Sayısı",
         metric_type="measure", expression="COUNT(*)", unit="adet",
         synonyms="kalem sayısı,satır sayısı,kalem adedi",
         description="Toplam kalem/satır sayısı.", is_active=True),
    dict(table_name="shipments", metric_key="toplam_miktar", label="Toplam Miktar",
         metric_type="measure", expression="SUM(TRY_CAST(LFIMG AS FLOAT))", unit="adet",
         synonyms="toplam miktar,toplam teslim,toplam adet,toplam teslim miktarı",
         description="Teslim miktarı (LFIMG) toplamı.", is_active=True),
    dict(table_name="shipments", metric_key="ort_miktar", label="Ortalama Miktar",
         metric_type="measure", expression="AVG(TRY_CAST(LFIMG AS FLOAT))", unit="adet",
         synonyms="ortalama miktar,ort miktar,ortalama teslim",
         description="Teslim miktarı (LFIMG) ortalaması.", is_active=True),
    dict(table_name="shipments", metric_key="toplam_hacim", label="Toplam Hacim",
         metric_type="measure", expression="SUM(TRY_CAST(VOLUM AS FLOAT))", unit="m3",
         synonyms="toplam hacim,hacim",
         description="Hacim (VOLUM) toplamı.", is_active=True),

    # ── shipments durum/gecikme filtreleri (TASLAK — admin doğrulamalı) ───────
    dict(table_name="shipments", metric_key="gecikme", label="Gecikmeli Sevkiyat",
         metric_type="filter",
         expression="TRY_CAST(WADAT_IST AS DATE) > TRY_CAST(DPLBG AS DATE)", unit="",
         synonyms="gecikme,geciken,gecikmeli,geç sevkiyat,gecikmiş",
         description="Fiili mal çıkışı planlanan yüklemeden sonra (TASLAK — kolon doğrulanmalı).",
         is_active=False),
    dict(table_name="shipments", metric_key="aktif_sevkiyat", label="Aktif Sevkiyat",
         metric_type="filter", expression="TDURUM NOT IN ('C')", unit="",
         synonyms="aktif sevkiyat,devam eden,açık sevkiyat,tamamlanmamış",
         description="Tamamlanmamış sevkiyatlar (TASLAK — TDURUM kodları doğrulanmalı).",
         is_active=False),
    dict(table_name="shipments", metric_key="teslim_edildi", label="Teslim Edildi",
         metric_type="filter", expression="TDURUM = 'C'", unit="",
         synonyms="teslim edildi,tamamlandı,kapandı,teslim",
         description="Tamamlanan sevkiyatlar (TASLAK — TDURUM kodları doğrulanmalı).",
         is_active=False),

    # ── Press (Beyçelik) ──────────────────────────────────────────────────────
    dict(company="Beycelik", integration_id=2, table_name="Press",
         metric_key="uretim_kayit_sayisi", label="Üretim Kayıt Sayısı",
         metric_type="measure", expression="COUNT(*)", unit="adet",
         synonyms="üretim kaydı,kayıt sayısı,üretim adedi,üretim satırı",
         description="Press tablosundaki günlük kayıt sayısı.", is_active=True),
]


def _exists(cur, metric_key: str, table_name: str, integration_id) -> bool:
    if integration_id is None:
        cur.execute(
            "SELECT 1 FROM semantic_metrics WHERE metric_key=? AND table_name=? "
            "AND integration_id IS NULL", (metric_key, table_name))
    else:
        cur.execute(
            "SELECT 1 FROM semantic_metrics WHERE metric_key=? AND table_name=? "
            "AND integration_id=?", (metric_key, table_name, integration_id))
    return cur.fetchone() is not None


def seed():
    conn = get_connection(); cur = conn.cursor()
    inserted, skipped = 0, 0
    try:
        for m in SEED:
            if _exists(cur, m["metric_key"], m["table_name"], m.get("integration_id")):
                skipped += 1
                print(f"  = atlandı (var): {m['metric_key']} / {m['table_name']}")
                continue
            semantic_layer.create_metric(m)
            inserted += 1
            print(f"  + eklendi: {m['metric_key']} / {m['table_name']} "
                  f"({'aktif' if m.get('is_active', True) else 'TASLAK'})")
    finally:
        conn.close()
    print(f"\n✓ Seed tamamlandı: {inserted} eklendi, {skipped} atlandı.")


if __name__ == "__main__":
    seed()
