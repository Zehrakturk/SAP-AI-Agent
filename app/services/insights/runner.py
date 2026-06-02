"""
Insights runner — tüm detector'ları çalıştırıp sonuçları MSSQL'e kaydeder.

Public:
    generate_insights(user_id=None) -> dict  (özet rapor)
    generate_for_user(user_id)      -> liste

APScheduler ile her gece çağrılır.
"""

from __future__ import annotations

import traceback
from datetime import datetime

from app.services.insights.factory     import InsightDetectorFactory
from app.services.insights.repository  import InsightsRepository
from app.services.insights.models      import DetectorContext, InsightCard


def generate_insights(user_id: str | None = None,
                      detector_names: list[str] | None = None) -> dict:
    """
    Kayıtlı tüm detector'ları (veya verilen listeyi) çalıştırır.
    Üretilen InsightCard'ları MSSQL'e yazar.

    Döner:
      {
        "total"       : N,
        "by_detector" : {"trend_change": 3, "top_mover": 2, ...},
        "saved_ids"   : [id1, id2, ...],
        "errors"      : ["..."],
      }
    """
    context = DetectorContext.now(user_id=user_id)
    repo    = InsightsRepository()
    # Tabloyu önceden hazırla — anomaly detector freshness check için gerekli
    from app.services.db import get_connection
    _c = get_connection()
    repo._ensure_table(_c.cursor())
    _c.commit(); _c.close()

    saved_ids = []
    by_detector = {}
    errors = []

    if detector_names:
        detectors = [InsightDetectorFactory.create(n) for n in detector_names]
    else:
        detectors = InsightDetectorFactory.all_instances()

    print(f"[INSIGHTS] {len(detectors)} detector çalıştırılıyor "
          f"(user={user_id or 'global'})...")

    for detector in detectors:
        try:
            cards = detector.detect(context)
            print(f"[INSIGHTS] {detector.DETECTOR_NAME} -> {len(cards)} kart")
            for card in cards:
                if user_id:
                    card.user_id = user_id
                new_id = repo.save(card)
                saved_ids.append(new_id)
            by_detector[detector.DETECTOR_NAME] = len(cards)
        except Exception as e:
            tb = traceback.format_exc()
            print(f"[INSIGHTS ERROR] {detector.DETECTOR_NAME}: {e}\n{tb}")
            # Stack trace'in son 5 satırını da hata mesajına ekle (debug için)
            tb_tail = " | ".join(tb.strip().split("\n")[-5:])
            errors.append(f"{detector.DETECTOR_NAME}: {e}  ::  {tb_tail[:400]}")

    summary = {
        "total"       : len(saved_ids),
        "by_detector" : by_detector,
        "saved_ids"   : saved_ids,
        "errors"      : errors,
        "ran_at"      : datetime.now().isoformat(),
    }
    print(f"[INSIGHTS] Toplam {len(saved_ids)} kart kaydedildi.")
    return summary


def generate_for_user(user_id: str) -> list[dict]:
    """Tek kullanıcı için içgörü üretip listeyi döner."""
    generate_insights(user_id=user_id)
    return InsightsRepository().list_active(user_id=user_id)
