"""
app/services/gemini_enhancer.py

Gemini Flash — rapor ve görselleştirme zenginleştirici.
GPT pipeline'a dokunmaz, ek bir katman olarak çalışır.

İki ana görev:
  1. enhance_visualization(data) → Chat yanıtı için renk paleti + görsel öneri
  2. enhance_report(data)        → Rapor için zengin HTML infografik bölüm
"""

from __future__ import annotations

import json
import os

from dotenv import load_dotenv

load_dotenv()

_GEMINI_KEY   = os.getenv("GEMINI_API_KEY", "")
_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
_client       = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    if not _GEMINI_KEY:
        raise RuntimeError("GEMINI_API_KEY tanımlı değil.")
    import google.generativeai as genai
    genai.configure(api_key=_GEMINI_KEY)
    _client = genai.GenerativeModel(_GEMINI_MODEL)
    print(f"[GEMINI] Model: {_GEMINI_MODEL}")
    return _client


def is_available() -> bool:
    return bool(_GEMINI_KEY)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Görselleştirme Zenginleştirici — Chat yanıtı için
# ─────────────────────────────────────────────────────────────────────────────

def enhance_visualization(question: str, rows: list, summary: str,
                          chart_type: str, chart_data: dict) -> dict:
    """
    Chat yanıtındaki grafiği ve KPI'ları Gemini ile zenginleştirir.

    Döner:
    {
      "palette"       : ["#hex1", "#hex2", ...],   # 8 renk
      "chart_title"   : "Nisan Haftalık Sevkiyat Karşılaştırması",
      "chart_subtitle": "2026 yılı ilk iki haftası",
      "insights"      : ["💡 Insight 1", "💡 Insight 2", "💡 Insight 3"],
      "badge_html"    : "<div>...</div>",           # Hazır HTML badge satırı
      "recommended_type": "bar"                     # en uygun grafik tipi
    }
    """
    if not is_available():
        return {}

    sample = rows[:30] if rows else []
    col_names = list(rows[0].keys()) if rows else []

    prompt = f"""Sen bir veri görselleştirme uzmanısın ve marka tasarımcısısın.
SAP verisini analiz et ve görsel zenginleştirme önerileri üret. Grafiklerin zengin ve etkili olması için x ve y sütunları için optimum alanı bul.

Soru: "{question}"
Mevcut Özet: "{summary}"
Grafik Tipi: {chart_type}
Kolon Adları: {col_names}
Veri (ilk 30 kayıt): {json.dumps(sample, ensure_ascii=False, default=str)}

Aşağıdaki JSON formatında yanıt ver:
{{
  "palette": ["#1a56db", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4", "#f97316", "#ec4899"],
  "chart_title": "Kısa ve güçlü başlık (max 8 kelime)",
  "chart_subtitle": "Alt başlık (tarih aralığı veya bağlam)",
  "insights": [
    "💡 En önemli bulgu (sayısal)",
    "📈 Trend veya değişim yüzdesi",
    "⚠️ Dikkat çeken anomali veya öne çıkan değer"
  ],
  "badge_html": "<span style='background:#dbeafe;color:#1d4ed8;padding:3px 10px;border-radius:999px;font-size:11px;font-weight:700'>Etiket1</span> <span style='...'>Etiket2</span>",
  "recommended_type": "bar veya line veya pie veya doughnut",
  "color_theme": "blue veya green veya orange veya purple — verinin duygusuna uygun"
}}

Kurallar:
- palette: veri kategorilerine anlamlı renkler ata (karşılaştırma→mavi/yeşil, hata→kırmızı, dağılım→çeşitli)
- insights: GERÇEK sayılarla (veri içinden), boş veya genel cümleler yazma
- badge_html: 2-3 kısa etiket (örn: "47 Sevkiyat", "%23 Artış", "İstanbul #1")
- Sadece JSON döndür, açıklama yazma"""

    try:
        model = _get_client()
        resp  = model.generate_content(prompt)
        text  = resp.text.strip()
        # Markdown fence temizle
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except Exception as e:
        print(f"[GEMINI viz] Hata: {e}")
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# 2. Rapor Zenginleştirici — HTML Infografik Bölüm
# ─────────────────────────────────────────────────────────────────────────────

def enhance_report(question: str, rows: list, summary: str,
                   kpis: list, highlights: list) -> str:
    """
    Rapor için Gemini'nin ürettiği zengin HTML bölümü döner.
    Rapor şablonlarına ek bir 'Gemini Analizi' kartı olarak eklenir.
    """
    if not is_available():
        return ""

    sample    = rows[:50] if rows else []
    col_names = list(rows[0].keys()) if rows else []

    prompt = f"""Sen bir kurumsal rapor tasarımcısı ve veri analistisin.
Aşağıdaki SAP lojistik verisini analiz ederek güzel bir HTML rapor bölümü üret.

Soru: "{question}"
Analiz: "{summary}"
KPI'lar: {json.dumps(kpis, ensure_ascii=False)}
Öne Çıkanlar: {json.dumps(highlights, ensure_ascii=False)}
Kolon Adları: {col_names}
Veri Örneği: {json.dumps(sample, ensure_ascii=False, default=str)}

Aşağıdaki HTML bölümünü üret. Inline CSS kullan, dış kaynak kullanma.
Stil: modern, kurumsal, mavi/yeşil tonlar, Inter font.

Üretilecek HTML bölümleri:
1. "Gemini Analizi" başlıklı bir kart
2. En az 3 satırlık detaylı Türkçe analiz metni (sayısal bulgularla)
3. Veri hakkında 4 adet metrik kutusu (renk kodlu, icon emoji ile)
4. "Öne Çıkan Bulgular" listesi (en az 3 madde, emoji + metin)
5. Veri kalite notu (eksik veri, anomali, önemsenmesi gereken nokta)

HTML çıktısı <div> ile başlamalı, tam anlamıyla kopyalanıp rapora eklenebilir olmalı.
Sadece HTML döndür, açıklama veya markdown kullanma."""

    try:
        model = _get_client()
        resp  = model.generate_content(prompt)
        text  = resp.text.strip()
        if text.startswith("```"):
            parts = text.split("```")
            text  = parts[1] if len(parts) > 1 else text
            if text.startswith("html"):
                text = text[4:]
        return text.strip()
    except Exception as e:
        print(f"[GEMINI report] Hata: {e}")
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# 3. Grafik Renk Paleti — Tek bir veri seti için hızlı
# ─────────────────────────────────────────────────────────────────────────────

def suggest_palette(labels: list, context: str = "") -> list[str]:
    """
    Etiket listesine ve bağlama göre en uygun renk paletini önerir.
    Hızlı endpoint için — enhance_visualization'ın daha hafif versiyonu.
    """
    if not is_available() or not labels:
        return ["#1a56db","#10b981","#f59e0b","#ef4444",
                "#8b5cf6","#06b6d4","#f97316","#ec4899"]

    prompt = f"""SAP lojistik dashboard için {len(labels)} etiketli grafik renk paleti öner.
Etiketler: {labels}
Bağlam: {context}

Kuralllar:
- Karşılaştırma → kontrast renkler (mavi/turuncu veya mavi/yeşil)
- Durum kodları → trafik ışığı (yeşil/sarı/kırmızı)
- Şehirler/kategoriler → çeşitli hoş renkler
- Zaman serisi → aynı rengin tonları

Sadece JSON array döndür: ["#hex1", "#hex2", ...]
{len(labels)} renk, açıklama yok."""

    try:
        resp = _get_client().generate_content(prompt)
        text = resp.text.strip().strip("`").replace("json","").strip()
        return json.loads(text)
    except Exception:
        return ["#1a56db","#10b981","#f59e0b","#ef4444",
                "#8b5cf6","#06b6d4","#f97316","#ec4899"]
