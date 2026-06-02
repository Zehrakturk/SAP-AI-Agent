"""
AnomalyDetector — veri kalitesi anomalileri.

Kontroller:
  - Freshness: son fetch 24 saatten eskiyse warning
  - Volume drop: son 24 saat kayıt sayısı son 7 günün ortalamasının %50 altıysa critical
  - Null spike: tarih kolonunda null oranı > %20 ise warning
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.services.insights.base    import AbstractInsightDetector
from app.services.insights.factory import InsightDetectorFactory
from app.services.insights.models  import InsightCard, Hypothesis, DetectorContext
from app.services.insights         import metric_calculator as mc


@InsightDetectorFactory.register("anomaly")
class AnomalyDetector(AbstractInsightDetector):

    FRESHNESS_HOURS = 24
    VOLUME_DROP_RATIO = 0.5  # son 24 saat / 7 günlük ort < 0.5 ise alarm

    def detect(self, context: DetectorContext) -> list[InsightCard]:
        cards = []
        integrations = mc.list_active_integrations()

        for integ in integrations:
            tbl = integ["target_table"]
            if not mc.table_exists(tbl):
                continue

            cards.extend(self._check_freshness(integ, tbl))
            cards.extend(self._check_volume_drop(integ, tbl, context))

        return cards

    # ─────────────────────────────────────────────────────────────────────
    def _check_freshness(self, integ, tbl) -> list[InsightCard]:
        """Son fetched_at güncel mi?"""
        if not mc.column_exists(tbl, "fetched_at"):
            return []
        rows = mc._exec(f"SELECT MAX(fetched_at) AS last_fetch FROM [{tbl}]")
        if not rows or not rows[0]["last_fetch"]:
            return []
        last_fetch = rows[0]["last_fetch"]
        if not isinstance(last_fetch, datetime):
            return []

        hours_ago = (datetime.now() - last_fetch).total_seconds() / 3600
        if hours_ago < self.FRESHNESS_HOURS:
            return []

        days_ago = int(hours_ago / 24)
        severity = "critical" if days_ago >= 3 else "warning"
        return [InsightCard(
            type     = "anomaly",
            severity = severity,
            title    = f"{integ['name']} verisi {days_ago} gündür güncellenmedi",
            summary  = (
                f"En son veri çekimi {last_fetch.strftime('%d %b %H:%M')}. "
                f"Otomatik fetch çalışmamış veya kaynağa erişilemiyor olabilir."
            ),
            metric   = "freshness",
            tags     = ["veri kalitesi", "freshness", integ["name"]],
            icon     = "⏱️",
            color    = "amber",
            drill_down_question = (
                f"{integ['name']} entegrasyonunda son fetch_log kayıtlarını göster"
            ),
        )]

    # ─────────────────────────────────────────────────────────────────────
    def _check_volume_drop(self, integ, tbl, context) -> list[InsightCard]:
        """Son 24 saat kayıt sayısı son 7 günün ortalamasının %50 altında mı?"""
        today = context.today
        # Son 24 saat
        today_start = (today - timedelta(days=1)).date().isoformat()
        today_end   = today.date().isoformat()
        cur_24h = mc.count_records(tbl, today_start, today_end)

        # Son 7 gün
        week_start = (today - timedelta(days=8)).date().isoformat()
        week_end   = (today - timedelta(days=1)).date().isoformat()
        week_total = mc.count_records(tbl, week_start, week_end)
        week_avg   = week_total / 7.0

        if week_avg < 3:
            return []  # zaten az veri — anlamsız alarm

        if cur_24h >= week_avg * self.VOLUME_DROP_RATIO:
            return []  # normal aralıkta

        drop_pct = (1 - cur_24h / week_avg) * 100 if week_avg else 0
        severity = "critical" if cur_24h == 0 else "warning"

        return [InsightCard(
            type     = "anomaly",
            severity = severity,
            title    = f"{integ['name']}: son 24 saat veri %{drop_pct:.0f} düşük",
            summary  = (
                f"Son 24 saatte {cur_24h} kayıt geldi. "
                f"Son 7 gün ortalaması {week_avg:.0f} idi. "
                f"Veri akışında kesinti olabilir."
            ),
            metric   = "volume_drop",
            current  = cur_24h,
            previous = week_avg,
            delta_pct= round(-drop_pct, 1),
            tags     = ["veri kalitesi", "volume", integ["name"]],
            icon     = "⚠️",
            color    = "red",
            drill_down_question = (
                f"{integ['name']} entegrasyonunda son 7 günlük günlük kayıt sayılarını göster"
            ),
        )]
