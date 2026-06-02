"""
HypothesisEngine — bir metrik sapması için kök-sebep hipotezleri üretir.

İki kullanım:
  1. Detector'lardan: card.hypotheses listesi otomatik dolduruluyor
  2. Chat'ten: kullanıcı karşılaştırma sorusu sorunca chat ek bölüm gösteriyor

Pipeline:
  metric (current vs previous) + tablo
       ↓
  her dimension için alt-kırılım + en büyük katkı
       ↓
  bulguları GPT'ye gönder, 3 Türkçe hipotez üret
       ↓
  Hypothesis listesi döner
"""

from __future__ import annotations

import json

from app.services.insights         import metric_calculator as mc
from app.services.insights.models  import Hypothesis


# GPT'yi opsiyonel kullan — yoksa sadece raw breakdown ile devam et
def _try_openai_call(prompt: str, max_tokens: int = 600) -> str | None:
    try:
        from app.services.query_engine import _call_openai
        return _call_openai(prompt, max_tokens=max_tokens, json_mode=True)
    except Exception as e:
        print(f"[HYPOTHESIS] OpenAI çağrı hatası: {e}")
        return None


CANDIDATE_DIMENSIONS = [
    ("MUSTERI_ADI", "müşteri"),
    ("CITY1",       "şehir"),
    ("ROUTE_TNM",   "rota"),
    ("VSART_TNM",   "taşıma tipi"),
    ("TDURUM_TNM",  "durum"),
    ("MATNR",       "ürün"),
]


def analyze_change(table_name: str,
                   cur_start: str, cur_end: str,
                   prev_start: str, prev_end: str,
                   max_dimensions: int = 3) -> dict:
    """
    Bir metrik değişiminin alt-kırılımını hesaplar.

    Döner:
    {
      "cur": 494, "prev": 642, "delta": -148, "delta_pct": -23.05,
      "breakdowns": [
        { "dimension": "MUSTERI_ADI",
          "top_changes": [
              {"value": "BATUHAN SARI", "cur": 8, "prev": 47, "delta": -39, "pct": -83},
              ...
          ]
        }, ...
      ]
    }
    """
    if not mc.table_exists(table_name):
        return {}

    cur  = mc.count_records(table_name, cur_start, cur_end)
    prev = mc.count_records(table_name, prev_start, prev_end)
    delta = cur - prev
    delta_pct = (delta / prev * 100) if prev else (100.0 if cur else 0.0)

    breakdowns = []
    for dim_col, dim_label in CANDIDATE_DIMENSIONS:
        if not mc.column_exists(table_name, dim_col):
            continue

        cur_rows  = mc.group_by_dimension(table_name, dim_col, cur_start, cur_end, top_n=30)
        prev_rows = mc.group_by_dimension(table_name, dim_col, prev_start, prev_end, top_n=30)
        cur_map   = {r["dim"]: r["adet"] for r in cur_rows  if r["dim"]}
        prev_map  = {r["dim"]: r["adet"] for r in prev_rows if r["dim"]}

        keys = set(cur_map) | set(prev_map)
        diffs = []
        for k in keys:
            c = cur_map.get(k, 0)
            p = prev_map.get(k, 0)
            d = c - p
            if abs(d) < 2:
                continue
            pct = (d / p * 100) if p else (100.0 if c else 0.0)
            diffs.append({"value": k, "cur": c, "prev": p, "delta": d,
                          "pct": round(pct, 1)})

        if not diffs:
            continue

        # Genel trend yönüne en çok katkıda bulunanlar
        if delta < 0:
            diffs.sort(key=lambda x: x["delta"])         # en negatif başta
        else:
            diffs.sort(key=lambda x: -x["delta"])         # en pozitif başta

        breakdowns.append({
            "dimension"   : dim_col,
            "dimension_label": dim_label,
            "top_changes" : diffs[:5],
        })

        if len(breakdowns) >= max_dimensions:
            break

    return {
        "cur": cur, "prev": prev,
        "delta": delta, "delta_pct": round(delta_pct, 1),
        "cur_window":  f"{cur_start} → {cur_end}",
        "prev_window": f"{prev_start} → {prev_end}",
        "breakdowns":  breakdowns,
    }


# ─────────────────────────────────────────────────────────────────────────────

def generate_hypotheses(table_name: str, integration_name: str,
                        cur_start: str, cur_end: str,
                        prev_start: str, prev_end: str,
                        max_hypotheses: int = 3) -> list[Hypothesis]:
    """
    Bir tarih aralığında metrik değişimi için Türkçe kök-sebep hipotezleri üretir.
    GPT yoksa raw dimension breakdown'dan basit hipotezler döner.
    """
    analysis = analyze_change(table_name, cur_start, cur_end, prev_start, prev_end)
    if not analysis or not analysis.get("breakdowns"):
        return []

    # Önce raw breakdown'dan kaba hipotezler
    raw_hypotheses = _raw_hypotheses_from_breakdown(analysis, max_hypotheses)

    # GPT ile cilala (opsiyonel)
    refined = _refine_with_gpt(integration_name, analysis)
    if refined:
        return refined[:max_hypotheses]

    return raw_hypotheses[:max_hypotheses]


# ─────────────────────────────────────────────────────────────────────────────

def _raw_hypotheses_from_breakdown(analysis: dict, max_count: int) -> list[Hypothesis]:
    out = []
    direction_word = "azalış" if analysis["delta"] < 0 else "artış"
    sign = "" if analysis["delta"] >= 0 else "-"

    for bd in analysis["breakdowns"]:
        dim_label = bd["dimension_label"]
        for change in bd["top_changes"][:2]:
            sign2 = "" if change["delta"] >= 0 else ""
            out.append(Hypothesis(
                text = (
                    f"{dim_label.title()} '{change['value']}' kayıtları "
                    f"{change['prev']} → {change['cur']} oldu "
                    f"({sign2}{change['delta']}, %{abs(change['pct']):.0f} {direction_word})"
                ),
                confidence = 0.6 if abs(change["delta"]) >= 5 else 0.45,
                metric_delta = change["delta"],
                tags = [bd["dimension"].lower()],
            ))
            if len(out) >= max_count:
                return out
    return out


# ─────────────────────────────────────────────────────────────────────────────

def _refine_with_gpt(integration_name: str, analysis: dict) -> list[Hypothesis] | None:
    """GPT'ye breakdown verilerini gönder, Türkçe kök-sebep hipotezleri üret."""
    prompt = f"""Sen bir SAP lojistik analistsin. Bir metrik değişiminin altındaki
kök sebepleri analiz et ve TÜRKÇE 3 hipotez üret. Sadece JSON döndür.

Entegrasyon: {integration_name}
Bu hafta ({analysis['cur_window']}): {analysis['cur']} kayıt
Geçen hafta ({analysis['prev_window']}): {analysis['prev']} kayıt
Değişim: {analysis['delta']} ({analysis['delta_pct']:+.1f}%)

Dimension Breakdown (genel trende en çok katkıda bulunanlar):
{json.dumps(analysis['breakdowns'], ensure_ascii=False, indent=2)}

Aşağıdaki JSON formatında 3 hipotez döndür (en olası ile başla):
{{
  "hypotheses": [
    {{
      "text": "Türkçe açıklayıcı cümle - belirli müşteri/şehir/durum ve sayı içersin",
      "confidence": 0.0-1.0,
      "tags": ["müşteri","şehir","operasyon" vb.]
    }},
    ...
  ]
}}

Sadece JSON. Markdown veya açıklama yazma."""

    try:
        raw = _try_openai_call(prompt, max_tokens=700)
        if not raw:
            return None
        data = json.loads(raw)
        hyp_list = data.get("hypotheses", [])
        return [
            Hypothesis(
                text = h.get("text", "")[:500],
                confidence = float(h.get("confidence", 0.6)),
                tags = h.get("tags", []),
            )
            for h in hyp_list if h.get("text")
        ]
    except Exception as e:
        print(f"[HYPOTHESIS GPT refine] {e}")
        return None
