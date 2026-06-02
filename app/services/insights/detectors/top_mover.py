"""
TopMoverDetector — geçen döneme göre en çok yükselen/düşen 3 müşteri/şehir/ürün.

TrendChangeDetector "toplam" üzerinde çalışıyor, bu detector "belirli dim
değerleri" üzerinde çalışır. Örnek çıktı:
  📈 En çok büyüyen müşteri: BATUHAN SARI (12 → 47, +%291)
  📉 En çok daralan müşteri: AHMET YILMAZ (38 → 9, -%76)
"""

from __future__ import annotations

from app.services.insights.base    import AbstractInsightDetector
from app.services.insights.factory import InsightDetectorFactory
from app.services.insights.models  import InsightCard, Hypothesis, DetectorContext
from app.services.insights         import metric_calculator as mc


DIMENSIONS = [
    # (kolon_adı, gösterilecek_etiket, ikon)
    ("MUSTERI_ADI", "müşteri",  "👤"),
    ("CITY1",       "şehir",    "📍"),
    ("MATNR",       "ürün",     "📦"),
    ("VSART_TNM",   "taşıma tipi", "🚚"),
    ("ROUTE_TNM",   "rota",     "🛣️"),
]


@InsightDetectorFactory.register("top_mover")
class TopMoverDetector(AbstractInsightDetector):

    MIN_ABS_CHANGE = 5       # En az 5 kayıt değişim olsun
    MIN_PCT_CHANGE = 25.0    # En az %25 sapma

    def detect(self, context: DetectorContext) -> list[InsightCard]:
        cards = []
        integrations = mc.list_active_integrations()

        for integ in integrations:
            tbl = integ["target_table"]
            if not mc.table_exists(tbl):
                continue

            this_start, this_end = mc.last_n_days(7, context.today)
            prev_start, prev_end = mc.previous_period(this_start, this_end)

            # Her dimension için top mover bul
            for dim_col, dim_label, dim_icon in DIMENSIONS:
                if not mc.column_exists(tbl, dim_col):
                    continue

                cur  = mc.group_by_dimension(tbl, dim_col, this_start, this_end, top_n=50)
                prev = mc.group_by_dimension(tbl, dim_col, prev_start, prev_end, top_n=50)

                cur_map  = {r["dim"]: r["adet"] for r in cur  if r["dim"]}
                prev_map = {r["dim"]: r["adet"] for r in prev if r["dim"]}

                # En çok artan + en çok azalan
                deltas = []
                for k in set(cur_map) | set(prev_map):
                    c = cur_map.get(k, 0)
                    p = prev_map.get(k, 0)
                    if c == 0 and p == 0:
                        continue
                    delta = c - p
                    pct = (delta / p * 100) if p else 100.0
                    if abs(delta) < self.MIN_ABS_CHANGE:
                        continue
                    if abs(pct) < self.MIN_PCT_CHANGE:
                        continue
                    deltas.append((k, c, p, delta, pct))

                if not deltas:
                    continue

                # En büyük yükseliş
                up = max(deltas, key=lambda x: x[3])
                if up[3] > 0:
                    cards.append(self._make_card(
                        integ, dim_col, dim_label, dim_icon,
                        up, this_start, this_end, prev_start, prev_end,
                        direction="up"
                    ))

                # En büyük düşüş
                down = min(deltas, key=lambda x: x[3])
                if down[3] < 0:
                    cards.append(self._make_card(
                        integ, dim_col, dim_label, dim_icon,
                        down, this_start, this_end, prev_start, prev_end,
                        direction="down"
                    ))

                break  # Bu entegrasyon için ilk dimensiondan kart ürettik, diğerlerine geçme

        return cards

    # ─────────────────────────────────────────────────────────────────────
    def _make_card(self, integ, dim_col, dim_label, dim_icon, mover,
                   this_start, this_end, prev_start, prev_end, direction):
        name, cur, prev, delta, pct = mover
        is_up = direction == "up"
        verb  = "yükselen" if is_up else "düşen"
        icon  = "📈" if is_up else "📉"
        color = "green" if is_up else "red"
        sign  = "+" if delta >= 0 else ""

        title = f"En çok {verb} {dim_label}: {name} ({prev} → {cur}, {sign}{delta})"
        summary = (
            f"{integ['name']} entegrasyonunda {dim_label} '{name}' kayıtları "
            f"geçen haftaya göre {sign}%{abs(pct):.0f} {'arttı' if is_up else 'azaldı'} "
            f"({prev_start} → {prev_end} vs {this_start} → {this_end})."
        )

        card = InsightCard(
            type     = "top_mover",
            severity = "warning" if (not is_up and abs(pct) >= 50) else "info",
            title    = title,
            summary  = summary,
            metric   = f"top_mover:{dim_col}",
            current  = cur, previous = prev,
            delta_pct= round(pct, 1),
            timeframe  = f"{this_start} → {this_end}",
            comparison = f"{prev_start} → {prev_end}",
            tags     = [dim_label, "top_mover", integ["name"]],
            icon     = dim_icon, color = color,
            drill_down_question = (
                f"{integ['name']} verilerinde {dim_label} '{name}' için "
                f"{prev_start}–{prev_end} ve {this_start}–{this_end} "
                f"arasındaki sevkiyatları detaylı göster"
            ),
        )
        card.hypotheses.append(Hypothesis(
            text = f"{dim_label.title()} '{name}' aktivitesi {prev} → {cur} kayda değişti "
                   f"(%{abs(pct):.0f} {'artış' if is_up else 'azalış'}).",
            confidence = 0.85,
            metric_delta = delta,
            tags = [dim_label],
        ))
        return card
