"""
CorrelationDetector — iki entegrasyon arasındaki örüntüyü yakalar.

Senaryo: "Bu hafta satışlar düştü, sevkiyatlar da düştü — 0.78 korelasyon var,
sevkiyat gecikmesi satış kaybının sebebi olabilir."

Mantık:
  - En az 2 aktif entegrasyon olması gerekir (tek silo → korelasyon yok).
  - Her entegrasyon çifti için son N günün günlük kayıt serisini hizala.
  - Lag-aware Pearson korelasyonu hesapla.
  - |r| >= eşik VE her iki seri de son haftada aynı yönde hareket ettiyse
    birleşik bir "correlation" insight kartı üret.
"""

from __future__ import annotations

from itertools import combinations

from app.services.insights.base    import AbstractInsightDetector
from app.services.insights.factory import InsightDetectorFactory
from app.services.insights.models  import InsightCard, Hypothesis, DetectorContext
from app.services.insights         import metric_calculator     as mc
from app.services.insights         import correlation_calculator as cc


@InsightDetectorFactory.register("correlation")
class CorrelationDetector(AbstractInsightDetector):
    """İki entegrasyon arası korelasyon tespiti."""

    WINDOW_DAYS  = 30      # korelasyon hesaplanan pencere
    MIN_ABS_R    = 0.6     # bu eşiğin altı kayda değer değil
    TREND_DAYS   = 7       # yön karşılaştırması (bu hafta vs geçen hafta)
    MIN_TREND_PCT = 10.0   # yön için en az %10 hareket

    def detect(self, context: DetectorContext) -> list[InsightCard]:
        integrations = mc.list_active_integrations()
        # Geçerli (tablosu var) entegrasyonlar
        valid = [i for i in integrations if mc.table_exists(i["target_table"])]
        if len(valid) < 2:
            return []   # korelasyon için en az 2 veri kaynağı gerek

        win_start, win_end = mc.last_n_days(self.WINDOW_DAYS, context.today)
        cards: list[InsightCard] = []

        for a, b in combinations(valid, 2):
            tbl_a, tbl_b = a["target_table"], b["target_table"]

            xs, ys, _days = cc.aligned_daily_series(tbl_a, tbl_b, win_start, win_end)
            # En az birkaç dolu gün olmalı
            if sum(1 for v in xs if v) < 3 or sum(1 for v in ys if v) < 3:
                continue

            r, lag = cc.best_lagged_correlation(xs, ys, max_lag=3)
            if r is None or abs(r) < self.MIN_ABS_R:
                continue

            # Her iki entegrasyonun son hafta trendini hesapla
            trend_a = self._week_trend(tbl_a, context)
            trend_b = self._week_trend(tbl_b, context)

            card = self._build_card(a, b, r, lag, trend_a, trend_b)
            if card:
                cards.append(card)

        return cards

    # ─────────────────────────────────────────────────────────────────────
    def _week_trend(self, tbl: str, context: DetectorContext) -> dict:
        """Bu hafta vs geçen hafta — (cur, prev, delta_pct)."""
        cur_start, cur_end   = mc.last_n_days(self.TREND_DAYS, context.today)
        prev_start, prev_end = mc.previous_period(cur_start, cur_end)
        cur  = mc.count_records(tbl, cur_start, cur_end)
        prev = mc.count_records(tbl, prev_start, prev_end)
        if prev == 0:
            delta = 100.0 if cur else 0.0
        else:
            delta = (cur - prev) / prev * 100.0
        return {"cur": cur, "prev": prev, "delta_pct": round(delta, 1)}

    # ─────────────────────────────────────────────────────────────────────
    def _build_card(self, a: dict, b: dict, r: float, lag: int,
                    trend_a: dict, trend_b: dict) -> InsightCard | None:
        name_a, name_b = a["name"], b["name"]
        sign  = "pozitif" if r > 0 else "negatif"
        da, db = trend_a["delta_pct"], trend_b["delta_pct"]

        # Yön açıklaması: ikisi de anlamlı hareket ettiyse "fırtına" hipotezi
        both_moved = abs(da) >= self.MIN_TREND_PCT and abs(db) >= self.MIN_TREND_PCT
        same_dir   = (da < 0 and db < 0) or (da > 0 and db > 0)

        if both_moved and same_dir:
            verb = "düştü" if da < 0 else "arttı"
            severity = "critical" if (da < 0 and abs(r) >= 0.75) else "warning"
            title = (
                f"{name_a} ve {name_b} birlikte {verb} "
                f"(korelasyon {r:+.2f})"
            )
            summary = (
                f"Son haftada {name_a} %{abs(da):.0f}, {name_b} %{abs(db):.0f} {verb}. "
                f"30 günlük veride aralarında {sign} {abs(r):.2f} korelasyon var. "
            )
            color, icon = ("red", "🔗") if da < 0 else ("green", "🔗")
        else:
            # Korelasyon var ama bu hafta birlikte hareket etmediler → bilgi amaçlı
            severity = "info"
            title = f"{name_a} ↔ {name_b}: {sign} korelasyon ({abs(r):.2f})"
            summary = (
                f"Son 30 günde {name_a} ile {name_b} arasında {sign} "
                f"{abs(r):.2f} korelasyon tespit edildi. "
            )
            color, icon = "blue", "🔗"

        # Lag yorumu
        if lag > 0:
            summary += (f"{name_a} hareketleri {name_b}'den ~{lag} gün önce "
                        f"geliyor — öncül gösterge olabilir.")
            lead = f"{name_a} → {name_b} ({lag} gün gecikmeli)"
        elif lag < 0:
            summary += (f"{name_b} hareketleri {name_a}'den ~{abs(lag)} gün önce "
                        f"geliyor.")
            lead = f"{name_b} → {name_a} ({abs(lag)} gün gecikmeli)"
        else:
            lead = "eşzamanlı"

        card = InsightCard(
            type     = "correlation",
            severity = severity,
            title    = title,
            summary  = summary,
            metric   = f"corr:{a['id']}x{b['id']}",
            current  = round(r, 3),
            timeframe= "son 30 gün",
            tags     = ["korelasyon", name_a, name_b],
            icon     = icon, color = color,
            drill_down_question = (
                f"{name_a} ve {name_b} verilerini son 30 günde "
                f"haftalık olarak karşılaştır"
            ),
        )
        card.hypotheses.append(Hypothesis(
            text = f"Öncül ilişki: {lead}",
            confidence = min(0.9, abs(r)),
            tags = ["korelasyon"],
        ))
        if both_moved and same_dir and r > 0:
            card.hypotheses.append(Hypothesis(
                text = (f"Olası kök sebep: {name_a} zincirindeki değişim "
                        f"{name_b}'yi de etkiliyor olabilir."),
                confidence = min(0.85, abs(r)),
                tags = ["kök-sebep"],
            ))
        return card
