"""
TrendChangeDetector — hafta/ay karşılaştırması yapar.

Her aktif entegrasyon için:
  - Bu hafta vs geçen hafta kayıt sayısı
  - Δ% > %10 ise insight üret
  - HypothesisEngine ile dimension breakdown
"""

from __future__ import annotations

from app.services.insights.base   import AbstractInsightDetector
from app.services.insights.factory import InsightDetectorFactory
from app.services.insights.models  import InsightCard, Hypothesis, DetectorContext
from app.services.insights         import metric_calculator as mc


@InsightDetectorFactory.register("trend_change")
class TrendChangeDetector(AbstractInsightDetector):
    """Hafta/ay bazlı volume karşılaştırması."""

    MIN_DELTA_PCT = 10.0   # %10 altı sapma → insight üretme
    MIN_ABS_DELTA = 5      # En az 5 kayıt farkı olsun

    def detect(self, context: DetectorContext) -> list[InsightCard]:
        cards = []
        integrations = mc.list_active_integrations()

        for integ in integrations:
            tbl = integ["target_table"]
            if not mc.table_exists(tbl):
                continue

            # 7 günlük pencere — bu hafta vs geçen hafta
            this_start, this_end = mc.last_n_days(7, context.today)
            prev_start, prev_end = mc.previous_period(this_start, this_end)

            cur  = mc.count_records(tbl, this_start, this_end)
            prev = mc.count_records(tbl, prev_start, prev_end)

            if prev == 0 and cur == 0:
                continue  # ölü entegrasyon — alarm verme

            if prev == 0:
                # Sıfırdan veriye geçiş → bilgi amaçlı
                delta_pct = 100.0
            else:
                delta_pct = (cur - prev) / prev * 100.0

            if abs(delta_pct) < self.MIN_DELTA_PCT and abs(cur - prev) < self.MIN_ABS_DELTA:
                continue  # önemsiz sapma

            direction = "düştü" if delta_pct < 0 else "arttı"
            icon      = "📉" if delta_pct < 0 else "📈"
            severity  = self._severity(delta_pct)
            color     = "red" if delta_pct < 0 else "green"

            title = f"{integ['name']} bu hafta %{abs(delta_pct):.0f} {direction}"
            summary = (
                f"Bu hafta ({this_start} → {this_end}) {cur} kayıt var. "
                f"Geçen hafta ({prev_start} → {prev_end}) {prev} kayıt vardı."
            )

            card = InsightCard(
                type     = "trend_change",
                severity = severity,
                title    = title,
                summary  = summary,
                metric   = f"weekly_count:{tbl}",
                current  = cur,
                previous = prev,
                delta_pct= round(delta_pct, 1),
                timeframe  = f"{this_start} → {this_end}",
                comparison = f"{prev_start} → {prev_end}",
                tags     = ["trend", integ["name"]],
                icon     = icon, color = color,
                drill_down_question = (
                    f"{integ['name']} entegrasyonunda bu hafta ({this_start}–{this_end}) "
                    f"ve geçen hafta ({prev_start}–{prev_end}) kayıt sayılarını karşılaştır"
                ),
            )

            # Top-3 dimension breakdown — değişimin en çok hangi dim'de olduğu
            self._add_dimension_hypotheses(card, tbl, this_start, this_end,
                                           prev_start, prev_end, delta_pct)

            cards.append(card)

        return cards

    # ─────────────────────────────────────────────────────────────────────
    def _severity(self, delta_pct: float) -> str:
        a = abs(delta_pct)
        if a >= 30: return "critical"
        if a >= 15: return "warning"
        return "info"

    # ─────────────────────────────────────────────────────────────────────
    def _add_dimension_hypotheses(self, card: InsightCard, tbl: str,
                                   cur_start, cur_end, prev_start, prev_end,
                                   delta_pct: float):
        """
        En çok değişen 3 dimension değerini bul (CITY1, MUSTERI_ADI, VSART_TNM).
        """
        for dim in ("CITY1", "MUSTERI_ADI", "VSART_TNM", "TDURUM_TNM"):
            if not mc.column_exists(tbl, dim):
                continue

            cur_groups  = mc.group_by_dimension(tbl, dim, cur_start, cur_end, top_n=20)
            prev_groups = mc.group_by_dimension(tbl, dim, prev_start, prev_end, top_n=20)

            cur_map  = {r["dim"]: r["adet"] for r in cur_groups if r["dim"]}
            prev_map = {r["dim"]: r["adet"] for r in prev_groups if r["dim"]}

            all_keys = set(cur_map) | set(prev_map)
            diffs = []
            for k in all_keys:
                c = cur_map.get(k, 0)
                p = prev_map.get(k, 0)
                diffs.append((k, c, p, c - p))

            # Trend yönüne uygun olanları al (düşüş varsa en çok düşen)
            if delta_pct < 0:
                diffs.sort(key=lambda x: x[3])         # en negatif
            else:
                diffs.sort(key=lambda x: -x[3])         # en pozitif

            for k, c, p, d in diffs[:2]:
                if abs(d) < 2:
                    continue
                pct = (d / p * 100) if p else 100.0
                card.hypotheses.append(Hypothesis(
                    text = f"{dim} = '{k}' → {p} kayıttan {c} kayda "
                           f"({'+' if d >= 0 else ''}{d}, %{pct:.0f})",
                    confidence = 0.65 if abs(d) >= 5 else 0.45,
                    metric_delta = d,
                    tags = [dim.lower()],
                ))

            # İlk doluyu bulunca yeter — fazla hipotez kalabalık yapar
            if card.hypotheses:
                break
