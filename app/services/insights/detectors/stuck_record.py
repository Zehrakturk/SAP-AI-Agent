"""
StuckRecordDetector — TDURUM (taşıma durumu) uzun süredir aynı kalan kayıtlar.

shipments tablosunda TDURUM_TNM kolonu varsa:
  - "YÜKLENDİ" durumunda 7+ gündür kalan kayıtları bul
  - Normalden 2× fazlaysa critical insight
"""

from __future__ import annotations

from app.services.insights.base    import AbstractInsightDetector
from app.services.insights.factory import InsightDetectorFactory
from app.services.insights.models  import InsightCard, Hypothesis, DetectorContext
from app.services.insights         import metric_calculator as mc


# Bu durumlar normalde geçici olmalı — uzun süre kalırsa operasyonel sorun
STUCK_STATUSES = ["YÜKLENDİ", "OLUŞTURULDU", "PLANLANDI", "MAL ÇIKIŞI YAPILDI"]


@InsightDetectorFactory.register("stuck_record")
class StuckRecordDetector(AbstractInsightDetector):

    STUCK_DAYS_THRESHOLD = 7
    MIN_COUNT            = 3  # En az 3 kayıt birikmişse insight üret

    def detect(self, context: DetectorContext) -> list[InsightCard]:
        cards = []
        integrations = mc.list_active_integrations()

        for integ in integrations:
            tbl = integ["target_table"]
            if not mc.table_exists(tbl):
                continue
            if not mc.column_exists(tbl, "TDURUM_TNM"):
                continue
            if not mc.column_exists(tbl, "ERDAT"):
                continue

            for status in STUCK_STATUSES:
                # ERDAT > 7 gün önce VE TDURUM_TNM = bu durum
                rows = mc._exec(f"""
                    SELECT COUNT(*) AS adet
                    FROM   [{tbl}]
                    WHERE  TDURUM_TNM = ?
                       AND TRY_CAST(ERDAT AS DATE) <= DATEADD(day, -{self.STUCK_DAYS_THRESHOLD}, GETDATE())
                """, (status,))
                count = int(rows[0].get("adet") or 0) if rows else 0

                if count < self.MIN_COUNT:
                    continue

                severity = "critical" if count >= 20 else "warning"
                card = InsightCard(
                    type     = "stuck_record",
                    severity = severity,
                    title    = f"{count} kayıt {self.STUCK_DAYS_THRESHOLD}+ gündür '{status}' durumunda",
                    summary  = (
                        f"{integ['name']} verilerinde {count} kayıt "
                        f"{self.STUCK_DAYS_THRESHOLD} günden uzun süredir '{status}' durumunda. "
                        f"Operasyonel bir darboğaz olabilir."
                    ),
                    metric   = f"stuck_record:{status}",
                    current  = count,
                    tags     = ["operasyon", "durum", integ["name"]],
                    icon     = "🔍",
                    color    = "amber",
                    drill_down_question = (
                        f"{integ['name']} verilerinde TDURUM_TNM='{status}' olan ve "
                        f"ERDAT'ı {self.STUCK_DAYS_THRESHOLD} günden eski olan kayıtları "
                        f"müşteri/şehir/rota bazlı listele"
                    ),
                )
                card.hypotheses.append(Hypothesis(
                    text = f"{count} adet kayıt '{status}' aşamasında takılı. "
                           f"Operasyonel akışta gecikme olabilir.",
                    confidence = 0.7,
                    tags = ["operasyon"],
                ))
                cards.append(card)

        return cards
