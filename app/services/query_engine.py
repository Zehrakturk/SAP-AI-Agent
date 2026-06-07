"""
app/services/query_engine.py

RAG akisi:
  1. Kullanici sorusunu embed et  ->  Qdrant'ta ara
  2. Eslesen integration_id'leri bul  (MSSQL: integration_vectors)
  3. O entegrasyonlarin schema_text'ini cek  (MSSQL: integration_schemas)
  4. T-SQL uret  ->  calistir  ->  analiz + grafik oner

Tum islemler MSSQL uzerinde (env: DB_SERVER, DB_NAME, DB_USER, DB_PASSWORD).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time

from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import ScoredPoint

from app.services.db import get_connection, rows_as_dicts

load_dotenv(override=True)   # .env sistem ortam değişkenlerini ezsin (doğru API anahtarı)

openai_client = OpenAI()

qdrant = QdrantClient(
    url=os.getenv("QDRANT_URL", "http://localhost:6333"),
    api_key=os.getenv("QDRANT_API_KEY", None),
    prefer_grpc=False,
    check_compatibility=False,
)

QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "SAP-AI")
EMBED_MODEL       = "text-embedding-3-small"


# -----------------------------------------------------------------------------
# Gerçek token kullanımı sayacı (thread-local — istek başına)
# OpenAI yanıtlarındaki .usage toplanır; query.py logta GERÇEK token'ı yazar.
# -----------------------------------------------------------------------------
import threading
_usage = threading.local()


class OpenAIQuotaError(RuntimeError):
    """OpenAI kotası/bakiyesi bittiğinde (insufficient_quota) — kullanıcıya temiz mesaj için."""


def _is_quota_error(msg: str) -> bool:
    m = (msg or "").lower()
    return "insufficient_quota" in m or "exceeded your current quota" in m


def _usage_reset():
    _usage.total = 0
    _usage.prompt = 0
    _usage.completion = 0
    _usage.calls = 0


def _usage_add(resp):
    try:
        u = resp.usage
        _usage.total      = getattr(_usage, "total", 0)      + int(u.total_tokens or 0)
        _usage.prompt     = getattr(_usage, "prompt", 0)     + int(u.prompt_tokens or 0)
        _usage.completion = getattr(_usage, "completion", 0) + int(getattr(u, "completion_tokens", 0) or 0)
        _usage.calls      = getattr(_usage, "calls", 0)      + 1
    except Exception:
        pass


def _usage_get() -> dict:
    return {
        "total_tokens":      getattr(_usage, "total", 0),
        "prompt_tokens":     getattr(_usage, "prompt", 0),
        "completion_tokens": getattr(_usage, "completion", 0),
        "llm_calls":         getattr(_usage, "calls", 0),
    }


# -----------------------------------------------------------------------------
# Yardimcilar
# -----------------------------------------------------------------------------

def _embed(text: str) -> list[float]:
    try:
        resp = openai_client.embeddings.create(model=EMBED_MODEL, input=text)
    except Exception as e:
        if _is_quota_error(str(e)):
            raise OpenAIQuotaError(
                "OpenAI kotası/bakiyesi dolmuş (insufficient_quota). "
                "Lütfen OpenAI faturalandırmasını kontrol edin."
            ) from e
        raise
    _usage_add(resp)
    return resp.data[0].embedding


_SQL_MODEL      = os.getenv("SQL_MODEL",      "gpt-4o")      # SQL üretimi için
_ANALYSIS_MODEL = os.getenv("ANALYSIS_MODEL", "gpt-4o")      # Analiz için
# İpucu: SQL_MODEL=o4-mini veya o3-mini ayarlarsanız çok daha güçlü SQL üretir


def _call_openai(prompt: str, max_tokens: int = 500, json_mode: bool = False,
                 model: str | None = None) -> str:
    use_model = model or _SQL_MODEL
    kwargs: dict = dict(
        model=use_model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
        kwargs["messages"].insert(0, {
            "role": "system",
            "content": "Sen yalnızca geçerli JSON döndüren bir asistan/API'sin.",
        })
    for attempt in range(5):
        try:
            resp = openai_client.chat.completions.create(**kwargs)
            _usage_add(resp)
            return resp.choices[0].message.content.strip()
        except Exception as e:
            msg = str(e)
            # Kota/billing bitmişse RETRY ETME — kalıcı hata, boşuna bekleme + spam yapma
            if _is_quota_error(msg):
                raise OpenAIQuotaError(
                    "OpenAI kotası/bakiyesi dolmuş (insufficient_quota). "
                    "Lütfen OpenAI faturalandırmasını kontrol edin."
                ) from e
            if "429" in msg:   # geçici hız limiti → kısa backoff ile tekrar dene
                wait = 2 ** attempt
                print(f"[RATE LIMIT] {wait}s bekleniyor...")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("OpenAI API: max retry aşıldı")


def _load_recent_context(session_id: str, n: int = 3) -> list[dict]:
    """
    Son N (user, assistant) çiftini chat_messages'tan getirir.
    Sprint 2.4 — multi-turn dialog için pronoun/eliptik referans çözümleme.

    Döner: [{"role": "user"|"assistant", "content": "...", "data_json": "..."}, ...]
    En eski en başta, en yeni en sonda.
    """
    if not session_id:
        return []
    try:
        conn   = get_connection()
        cursor = conn.cursor()
        # Son 2N satır (N kullanıcı + N asistan tahmini)
        cursor.execute(
            "SELECT TOP (?) role, content, data_json "
            "FROM chat_messages WHERE session_id = ? "
            "ORDER BY id DESC",
            (n * 2, session_id)
        )
        rows = cursor.fetchall()
        conn.close()
        # Eski → yeni
        return [
            {"role": r[0], "content": r[1] or "", "data_json": r[2] or ""}
            for r in reversed(rows)
        ]
    except Exception as e:
        print(f"[CONTEXT LOAD] Hata: {e}")
        return []


def _format_history_for_prompt(history: list[dict]) -> str:
    """Geçmiş mesajları LLM prompt'una uygun kısa metne dönüştürür."""
    if not history:
        return ""
    lines = []
    for h in history:
        role = "Kullanıcı" if h["role"] == "user" else "Asistan"
        text = (h["content"] or "").strip().replace("\n", " ")
        if len(text) > 300:
            text = text[:300] + "..."
        lines.append(f"  {role}: {text}")
    return "\n=== ÖNCEKİ KONUŞMA (en eski → en yeni) ===\n" + "\n".join(lines)


def _parse_intent(question: str, today_str: str,
                  history: list[dict] | None = None) -> dict:
    """
    Adım 1 — Niyet Ayrıştırma (Intent Parsing)
    Kullanıcı sorusunu yapısal hale getirir. Bu adım SQL üretmez,
    sadece 'ne istendiğini' anlar. Hata ayıklamayı ve SQL kalitesini artırır.

    Sprint 2.4: history verilirse pronoun/elision ("aynısını Mart için",
    "daha detaylı göster") önceki sorulardan çözümlenir.
    """
    history_block = _format_history_for_prompt(history or [])
    prompt = f"""Bugün: {today_str}
SAP sevkiyat sistemine yönelik bir kullanıcı sorusu analiz et ve JSON döndür.
{history_block}

Mevcut Soru: "{question}"

ÖNEMLİ — Çok turlu sohbet kuralı:
- Soru kısa/eliptikse ("aynısını Mart için", "daha detay", "bunu grafikle"),
  önceki konuşmadaki bağlama (tarih/metrik/grup/filtreler) BU SORUYA TAŞI.
- Pronouns/zarflar ("bu", "şunu", "aynısını", "öncekini") önceki son kullanıcı
  sorusuna refere eder — orada hangi varlık varsa onu kullan.
- Yeni soru bağımsız bir tarih/ay/dönem belirtiyorsa, önceki tarihi EZME.

Tarih kuralları:
- Yıl belirtilmemişse {today_str[:4]} kullan
- "ilk hafta" = ayın 1–7, "ikinci hafta" = 8–15, "üçüncü hafta" = 16–23, "son hafta" = 24-son
- Ay adları: Ocak=01 Şubat=02 Mart=03 Nisan=04 Mayıs=05 Haziran=06 Temmuz=07 Ağustos=08 Eylül=09 Ekim=10 Kasım=11 Aralık=12

JSON formatı:
{{
  "sorgu_tipi": "karşılaştırma | filtreleme | gruplama | liste | tekil_sayı",
  "donemler": [
    {{"etiket": "1. Hafta", "baslangic": "YYYY-MM-DD", "bitis": "YYYY-MM-DD"}},
    {{"etiket": "2. Hafta", "baslangic": "YYYY-MM-DD", "bitis": "YYYY-MM-DD"}}
  ],
  "metrikler": ["sevkiyat_sayisi", "toplam_miktar", "ortalama_miktar"],
  "grupla": ["CITY1"],
  "filtreler": {{"MUSTERI_ADI": "aranan", "TDURUM": "05"}},
  "aciklama": "Kullanıcının tam olarak ne istediği tek cümleyle"
}}

Sadece JSON döndür."""

    try:
        raw = _call_openai(prompt, max_tokens=400, json_mode=True)
        return json.loads(raw)
    except Exception:
        return {"sorgu_tipi": "bilinmiyor", "donemler": [], "metrikler": [], "aciklama": question}


def _clean_sql(sql_text: str) -> str:
    # 1. Markdown code fence'leri sil
    sql = re.sub(r"```sql|```", "", sql_text, flags=re.IGNORECASE)
    # 2. İlk SELECT veya WITH anahtar kelimesinden itibaren al
    #    (GPT bazen başa açıklama ekler: "İşte sorgu:\nSELECT ...")
    m = re.search(r"\b(SELECT|WITH)\b", sql, re.IGNORECASE)
    if m:
        sql = sql[m.start():]
    return sql.strip()


def _is_safe_sql(sql: str) -> bool:
    """
    Güvenli SELECT/WITH sorgusu mu kontrol eder.
    - SQL yorumlarını (-- ...) incelemeden önce siler
    - Kelime sınırı (word boundary) ile kontrol eder: LAST_UPDATE gibi sütun adlarını yakalamaz
    """
    # Tek satırlı yorumları sil
    stripped = re.sub(r"--[^\n]*", "", sql)
    # Çok satırlı yorumları sil
    stripped = re.sub(r"/\*.*?\*/", "", stripped, flags=re.DOTALL)

    upper = stripped.upper().strip()
    if not upper.startswith(("SELECT", "WITH")):
        return False

    # Sadece gerçek DML/DDL anahtar kelimeleri yakala
    forbidden = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER",
                 "TRUNCATE", "EXEC", "EXECUTE", "MERGE", "GRANT", "REVOKE"]
    for word in forbidden:
        if re.search(r"\b" + word + r"\b", upper):
            return False

    return True


# -----------------------------------------------------------------------------
# ADIM 1 — RAG: Qdrant'tan ilgili chunk'lari getir
# -----------------------------------------------------------------------------

def _retrieve_chunks(question: str, top_k: int = 5, threshold: float = 0.35) -> list[dict]:
    """
    Soruyu embed eder, Qdrant'ta arar.
    MSSQL integration_vectors tablosuyla eslestirerek integration_id dondurir.

    Donus: [{"integration_id": 1, "chunk_text": "...", "score": 0.87}, ...]
    """
    vector = _embed(question)

    try:
        # qdrant-client 1.12+ → query_points (eski .search kaldırıldı)
        _resp = qdrant.query_points(
            collection_name=QDRANT_COLLECTION,
            query=vector,
            limit=top_k,
            score_threshold=threshold,
            with_payload=False,
        )
        hits: list[ScoredPoint] = _resp.points
    except Exception as e:
        print(f"[QDRANT] Arama hatasi: {e}")
        return []

    if not hits:
        print("[RAG] Qdrant eslesmesi yok -> tum semalar kullanilacak (fallback).")
        return []

    # MSSQL'de point_id -> integration_id eslestir
    point_ids   = [str(h.id) for h in hits]
    score_map   = {str(h.id): h.score for h in hits}
    placeholders = ",".join("?" * len(point_ids))

    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT integration_id, chunk_text, qdrant_point_id "
        f"FROM integration_vectors WHERE qdrant_point_id IN ({placeholders})",
        point_ids,
    )
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "integration_id": r[0],
            "chunk_text"    : r[1],
            "score"         : score_map.get(str(r[2]), 0.0),
        }
        for r in rows
    ]


# -----------------------------------------------------------------------------
# ADIM 2 — Eslesen integration_id'lerin semalarini cek
# -----------------------------------------------------------------------------

def _fetch_schemas(integration_ids: list[int], company: str | None = None) -> list[dict]:
    """
    integration_schemas + integrations tablosundan schema_text getirir.
    integration_ids bossa tum aktif entegrasyonlar gelir (fallback).
    company verilirse (ve 'ALL' degilse) yalniz o firmanin entegrasyonlari.
    """
    conn   = get_connection()
    cursor = conn.cursor()

    # company kolonu var mı? (geriye uyum)
    cursor.execute(
        "SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_NAME='integrations' AND COLUMN_NAME='company'"
    )
    has_company = cursor.fetchone() is not None
    comp_filter = has_company and company and company != "ALL"

    where  = ["i.is_active = 1"]
    params : list = []
    if integration_ids:
        placeholders = ",".join("?" * len(integration_ids))
        where.append(f"s.integration_id IN ({placeholders})")
        params.extend(integration_ids)
    if comp_filter:
        where.append("i.company = ?")
        params.append(company)

    cursor.execute(
        f"""
        SELECT s.integration_id, s.target_table, s.schema_text, i.name
        FROM   integration_schemas s
        JOIN   integrations i ON i.id = s.integration_id
        WHERE  {' AND '.join(where)}
        """,
        params,
    )

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "integration_id"  : r[0],
            "table"           : r[1],
            "schema_text"     : r[2] or "",
            "integration_name": r[3],
        }
        for r in rows
    ]


# -----------------------------------------------------------------------------
# On-demand SAP fetch yardımcısı
# -----------------------------------------------------------------------------

def _try_on_demand_fetch(integration_ids: list[int], intent: dict,
                          original_sql: str, tables_used: list) -> list[dict]:
    """
    Eşleşen entegrasyonlar için SOAP kabiliyeti varsa SAP'tan çeker,
    veriyi MSSQL'e yazar, ardından aynı SQL'i tekrar çalıştırır.
    Döner: yeni rows listesi (boş olabilir)
    """
    # ★ Yeni Factory-tabanlı fetcher modülü
    from app.services.fetchers import fetch_integration

    # İlk tarihi al (tek dönem veya ilk dönem)
    donemler = intent.get("donemler", [])
    if donemler:
        extracted = {
            "start_date": donemler[0].get("baslangic"),
            "end_date"  : donemler[-1].get("bitis"),   # son dönemin bitişi
        }
    else:
        # Tarih bilgisi yoksa bugünden 30 gün geriye
        import datetime as _dt
        today = _dt.date.today()
        extracted = {
            "start_date": (today - _dt.timedelta(days=30)).isoformat(),
            "end_date"  : today.isoformat(),
        }

    fetched_any = False
    for int_id in integration_ids:
        conn   = get_connection()
        cursor = conn.cursor()
        # Endpoint sahibi entegrasyonları dene — service_type varsa onunla, yoksa wsdl_url ile
        # (geriye uyumluluk: service_type kolonu yoksa wsdl_url'e bak)
        try:
            cursor.execute(
                "SELECT wsdl_url FROM integrations WHERE id=? AND is_active=1",
                (int_id,)
            )
        except Exception:
            cursor.execute(
                "SELECT NULL FROM integrations WHERE id=? AND is_active=1",
                (int_id,)
            )
        row = cursor.fetchone()
        conn.close()

        if not row:
            continue  # entegrasyon yok/pasif

        # WSDL yok ama REST entegrasyonu olabilir → orchestrator zaten kontrol eder
        print(f"[ON-DEMAND] integration_id={int_id} (factory fetcher) başlatılıyor...")
        result = fetch_integration(int_id, extracted, force=False)
        print(f"[ON-DEMAND] Sonuç: {result}")

        if result["status"] in ("fetched", "cached") and result.get("rows_written", 0) > 0:
            fetched_any = True

    if not fetched_any:
        return []

    # Aynı SQL'i tekrar çalıştır
    try:
        conn   = get_connection()
        cursor = conn.cursor()
        cursor.execute(original_sql)
        columns = [col[0] for col in cursor.description]
        new_rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()
        print(f"[ON-DEMAND] Re-query: {len(new_rows)} satır bulundu.")
        return new_rows
    except Exception as e:
        print(f"[ON-DEMAND] Re-query hatası: {e}")
        return []


# -----------------------------------------------------------------------------
# Ana fonksiyon
# -----------------------------------------------------------------------------

_CACHE: dict[str, dict] = {}   # sorgu → zengin sonuç (process restart'ta sıfırlanır)


def _analyze_rows(user_question: str, rows: list, tables_used: list,
                  context_hint: str = "") -> dict:
    """
    Satır verisinden zengin analiz + görselleştirme paketi üretir
    (summary / chart / kpis / highlights / follow_ups). Hem SQL hem CANLI sorgu kullanır.
    context_hint: opsiyonel kolon/şema açıklaması — LLM'in kolonları (AMOUNT, PRICE vb.)
    doğru yorumlaması için (özellikle canlı SAP verisinde önemli).
    """
    if not rows:
        return {
            "text_summary": "Belirtilen kriterlere uygun veri bulunamadı.",
            "chart_type": "NONE", "chart_data": {}, "kpis": [],
            "secondary_chart": None, "highlights": [], "follow_ups": [],
        }
    _hint = (f"\n\nKOLON AÇIKLAMALARI (doğru yorumla, uydurma hesap yapma; metin/etiketlerde "
             f"TEKNİK KOLON ADLARINI değil TÜRKÇE İŞ TERİMLERİNİ kullan — "
             f"ör. VENDOR→satıcı, ZTERM→ödeme koşulu, FISCPER→mali yıl):\n{context_hint}"
             ) if context_hint else ""
    report_prompt = f"""Sen bir kıdemli iş analistisin ve Power BI uzmanısın.
Kullanıcının sorusuna karşılık aşağıdaki veri geldi. Bu veriyi analiz edip zengin bir
görselleştirme paketi üret.

Kullanıcı Sorusu: "{user_question}"
Kaynak: {', '.join(tables_used)}{_hint}
Veri ({len(rows)} kayıt, ilk 200 gösteriliyor):
{json.dumps(rows[:200], ensure_ascii=False, default=str)}

KURALLAR:
- Karşılaştırma sorusuysa PRIMARY chart GROUPED BAR, secondary LINE.
- Dağılım sorusuysa PRIMARY PIE, secondary BAR.
- Zaman serisi / trend sorusuysa PRIMARY LINE (fill:true), secondary BAR.
- Tekil liste sorusuysa PRIMARY yatay BAR (type: "bar", indexAxis: "y"), secondary TABLE.
- datasets içinde birden fazla veri seti olabilir.
- kpis: Her zaman 3-4 KPI üret (toplam, ortalama, maksimum, değişim%).
- change: "+%12.3" / "-%5.1"; trend: "up" / "down".
- highlights: 3 kısa Türkçe bulgu (emoji ile).
- secondary_chart null olabilir ama mümkünse doldur.
- follow_ups: bu veriye özel 3 KISA takip sorusu (Türkçe, max 8 kelime).

Sadece geçerli JSON döndür:
{{
  "text_summary": "Kapsamlı Türkçe analiz (en az 3 cümle).",
  "chart_type": "BAR veya LINE veya PIE",
  "chart_data": {{"labels": ["E1","E2"], "datasets": [{{"label":"V1","data":[100,200]}}]}},
  "kpis": [{{"label":"Toplam","value":"247","change":"+12.3%","trend":"up","color":"blue"}}],
  "secondary_chart": {{"type":"LINE","title":"Detay","data":{{"labels":["1","2"],"datasets":[{{"label":"Ort.","data":[8.8,13.1]}}]}}}},
  "highlights": ["📦 ...","🏆 ...","📍 ..."],
  "follow_ups": ["...","...","..."]
}}"""
    try:
        return json.loads(_call_openai(report_prompt, max_tokens=1800, json_mode=True,
                                       model=_ANALYSIS_MODEL))
    except Exception:
        return {
            "text_summary": "Analiz edilemedi.", "chart_type": "BAR", "chart_data": {},
            "kpis": [], "secondary_chart": None, "highlights": [], "follow_ups": [],
        }


_TR_FOLD_QE = str.maketrans("ıİşŞğĞüÜöÖçÇ", "iissgguuoocc")


def _norm_q(s: str) -> str:
    return (s or "").lower().translate(_TR_FOLD_QE)


_REPORT_KW = [
    "rapor", "raporla", "grafik", "grafikle", "gorsel", "gorselle", "gorsellestir",
    "cizdir", "pano", "dashboard", "pasta", "bar grafik", "infografik", "chart",
    "kpi", "gosterge", "diyagram", "trend grafik",
]
_TABLE_KW = [
    "listele", "liste", "tablo", "dokum", "satir satir", "kayitlari goster",
    "hepsini goster", "tum kayitlar", "sirala", "goster",
]


def _output_mode(question: str) -> str:
    """
    Çıktı modu:
      'report' → kullanıcı GÖRSEL/RAPOR istedi (grafik + KPI + tablo)
      'table'  → kullanıcı LİSTE/TABLO istedi (sadece veri tablosu)
      'text'   → (varsayılan) sadece analiz edip metinle cevap ver
    """
    qn = _norm_q(question)
    if any(k in qn for k in _REPORT_KW):
        return "report"
    if any(k in qn for k in _TABLE_KW):
        return "table"
    return "text"


def _answer_text(question: str, rows: list, context_hint: str = "") -> dict:
    """Soruyu veriye dayanarak KISA ve NET metinle yanıtlar (grafik/KPI üretmez)."""
    if not rows:
        return {"text_summary": "Belirtilen kriterlere uygun veri bulunamadı.", "follow_ups": []}
    hint = (f"\nKOLON AÇIKLAMALARI (sadık kal, uydurma hesap yapma; cevapta TEKNİK KOLON "
            f"ADLARINI değil bu açıklamalardaki TÜRKÇE İŞ TERİMLERİNİ kullan — "
            f"ör. VENDOR→satıcı, ZTERM→ödeme koşulu, FISCPER→mali yıl):\n{context_hint}"
            ) if context_hint else ""
    prompt = f"""Kullanıcının sorusunu, verilen veriye dayanarak DOĞRUDAN ve NET yanıtla (Türkçe).
Kısa ve sohbet havasında ol; tablo/teknik döküm YAPMA. Sayısal cevabı net ver (örn. "80 TRY").
Cevapta teknik kolon adı (VENDOR, ZTERM, FISCPER, PLANT...) KULLANMA; Türkçe iş terimi kullan.
Birden çok kayıt varsa soruya uygun şekilde özetle/topla.{hint}

Soru: "{question}"
Veri ({len(rows)} kayıt, ilk 100):
{json.dumps(rows[:100], ensure_ascii=False, default=str)}

Yalnız geçerli JSON döndür:
{{"text_summary": "net Türkçe cevap (1-4 cümle)", "follow_ups": ["kısa takip sorusu", "...", "..."]}}"""
    try:
        out = json.loads(_call_openai(prompt, max_tokens=600, json_mode=True, model=_ANALYSIS_MODEL))
        return {"text_summary": out.get("text_summary", ""),
                "follow_ups": (out.get("follow_ups") or [])[:3]}
    except Exception:
        return {"text_summary": "Veri alındı ancak özetlenemedi.", "follow_ups": []}


def _compose_report(question: str, rows: list, tables_used: list,
                    context_hint: str = "") -> tuple[dict, list]:
    """
    Çıktı moduna göre analiz paketini ve GÖSTERİLECEK satırları döndürür → (report, display_rows).
    text → sadece metin (tablo gizli) · table → metin + tablo · report → tam görselleştirme.
    """
    mode = _output_mode(question)
    if mode == "report":
        return _analyze_rows(question, rows, tables_used, context_hint), rows
    txt = _answer_text(question, rows, context_hint)
    report = {
        "text_summary": txt["text_summary"],
        "chart_type": "TABLE" if mode == "table" else "NONE",
        "chart_data": {}, "kpis": [], "secondary_chart": None,
        "highlights": [], "follow_ups": txt["follow_ups"],
    }
    return report, (rows if mode == "table" else [])


def _route_live(question: str, company: str | None, candidate_ids: list[int]) -> int | None:
    """
    CANLI (anlık) sorgu entegrasyonu yönlendirmesi — firma-kapsamlı + güvenilir.

    Yalnız KULLANICININ FİRMASINDAKİ (veya global) live_query=true entegrasyonları dikkate alır
    → canlı entegrasyonu olmayan firmalar (ör. Warmhaus) HİÇ etkilenmez.

    Bir canlı entegrasyona yönlendirme sinyalleri (RAG skorundan bağımsız, güvenilir):
      1. extra_config.keywords'ten biri soruda geçiyorsa (alan eşleşmesi), VEYA
      2. RAG'ın en iyi adayı (candidate_ids[0]) bu canlı entegrasyonsa.
    """
    try:
        conn = get_connection(); cur = conn.cursor()
        # extra_config + company kolonları (geriye uyum)
        has_company = cur.execute(
            "SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_NAME='integrations' AND COLUMN_NAME='company'").fetchone() is not None
        cur.execute("SELECT id, extra_config" + (", company" if has_company else "") +
                    " FROM integrations WHERE is_active = 1")
        rows = cur.fetchall(); conn.close()
    except Exception as e:
        print(f"[LIVE ROUTE] atlandı: {e}")
        return None

    from app.services.tenant import canonical_company
    comp = canonical_company(company)
    qn   = _norm_q(question)
    top  = candidate_ids[0] if candidate_ids else None

    live_list: list[tuple[int, list]] = []   # (iid, keywords) — firmanın canlı entegrasyonları
    for r in rows:
        iid = r[0]
        raw = r[1]
        icompany = r[2] if has_company and len(r) > 2 else None
        # Firma izolasyonu: global admin (ALL) hariç, yalnız aynı firma
        if comp not in (None, "", "ALL"):
            if icompany and canonical_company(icompany) not in (comp, "ALL"):
                continue
        try:
            cfg = json.loads(raw) if isinstance(raw, str) else (raw or {})
        except Exception:
            cfg = {}
        if cfg.get("live_query"):
            live_list.append((iid, cfg.get("keywords") or []))

    if not live_list:
        return None

    # 1) UCUZ sinyaller (LLM'siz): anahtar kelime alan eşleşmesi VEYA RAG en iyi adayı
    for iid, kws in live_list:
        if any(_norm_q(k) in qn for k in kws if k):
            return iid
        if top is not None and iid == top:
            return iid

    # 2) YEDEK sinyal: ucuz sinyaller tutmadı → sorudan canlı entegrasyon parametreleri
    #    çıkarılabiliyorsa (malzeme/plant/satıcı gibi) bu entegrasyona yönlendir.
    from app.repositories.integration_repository import IntegrationRepository
    for iid, _kws in live_list:
        try:
            cfg = IntegrationRepository().get_with_params(iid)
            if _extract_live_params(cfg, question):
                print(f"[LIVE ROUTE] param-çıkarımı eşleşti → id={iid}")
                return iid
        except Exception:
            continue
    return None


def _extract_live_params(config, question: str) -> dict:
    """Sorudan SAP fonksiyon parametre değerlerini çıkarır (sadece açıkça geçenler)."""
    plist = list(config.params or [])
    if not plist:
        return {}
    desc = "\n".join(
        f"- {p.param_name.lower()}: {p.description or p.param_name} (tip: {p.param_type})"
        for p in plist
    )
    prompt = (
        "Görevin: kullanıcı sorusundaki SOMUT değerleri ilgili SAP parametresine ata.\n"
        "KURALLAR:\n"
        "- Malzeme kodu, üretim yeri (plant), satıcı no gibi NET tanımlayıcılar soruda "
        "geçiyorsa MUTLAKA ilgili parametreye ekle.\n"
        "- Her parametrenin açıklamasındaki FORMAT/İSTİSNA kuralına uy; açıklama belirli bir "
        "durumda 'boş bırak' diyorsa o parametreyi EKLEME.\n"
        "- Soruda hiç geçmeyen parametreyi EKLEME.\n\n"
        "ÖRNEK:\n"
        "Parametreler: iv_material (malzeme kodu), iv_plant (üretim yeri), "
        "iv_fiscper (mali yıl/dönem; bir YIL belirtilirse 4 haneli yılı yaz), iv_vendor (satıcı no)\n"
        'Soru: "ABC-123 malzemesi 1000 üretim yerinde 2024 yılı alımları nedir"\n'
        'Cevap: {"iv_material":"ABC-123","iv_plant":"1000","iv_fiscper":"2024"}\n'
        'Soru: "2023 mali yılında en yüksek birim fiyatlı malzeme"\n'
        'Cevap: {"iv_fiscper":"2023"}\n\n'
        "ŞİMDİ:\n"
        f"Parametreler:\n{desc}\n"
        f'Soru: "{question}"\n\n'
        "Yalnız geçerli JSON döndür; anahtarlar parametre adının küçük harfli hali olsun."
    )
    try:
        out = json.loads(_call_openai(prompt, max_tokens=300, json_mode=True))
        valid = {p.param_name.lower() for p in plist}
        return {k: v for k, v in out.items() if k in valid and v not in (None, "")}
    except Exception as e:
        print(f"[LIVE] param çıkarımı atlandı: {e}")
        return {}


def _normalize_live_params(config, extracted: dict) -> dict:
    """
    Canlı parametre normalizasyonu. Mali dönem (FISCPER) alanına SADECE 4 haneli yıl
    geldiyse 7 haneli forma (YYYY001) çevirir — bu BW modelinde yıllık veri 001 döneminde
    tutulur ('2023' → 0 kayıt, '2023001' → tüm yıl). LLM ne üretirse üretsin garanti eder.
    """
    import re as _re
    out = dict(extracted)
    fisc_names = {(p.param_name or "").lower() for p in config.params
                  if "FISC" in (p.param_name or "").upper() or "PER" in (p.param_name or "").upper()}
    for k, v in list(out.items()):
        if k in fisc_names and _re.fullmatch(r"\d{4}", str(v or "").strip()):
            out[k] = f"{str(v).strip()}001"
    return out


def _sort_live_for_ranking(question: str, records: list) -> list:
    """
    Soru bir SIRALAMA sorusuysa (en yüksek/en düşük ...), kayıtları VERİDEKİ MEVCUT alana
    göre sıralar — böylece LLM'e giden ilk satırlar doğru cevabı içerir (binlerce kayıtta
    truncation sorununu çözer). Birim fiyat zaten PRICE alanında; hesaplama YAPILMAZ.
      - "tutar/harcama" geçiyorsa AMOUNT'a göre, aksi halde PRICE (birim fiyat) göre.
    """
    if not records:
        return records
    qn = _norm_q(question)
    is_ranking = any(k in qn for k in
                     ["en yuksek", "en pahali", "en dusuk", "en ucuz", "en buyuk",
                      "en kucuk", "siralama", "sirala", "en cok", "en az"])
    if not is_ranking:
        return records

    field = "AMOUNT" if any(k in qn for k in ["tutar", "harcama", "toplam"]) else "PRICE"
    if not any(field in r for r in records):
        return records

    def _num(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return None

    asc = any(k in qn for k in ["en dusuk", "en ucuz", "en kucuk", "en az"])
    return sorted(records,
                  key=lambda r: (_num(r.get(field)) is None, _num(r.get(field)) or 0),
                  reverse=not asc)


# ── Oturum-bazlı CANLI veri önbelleği (drill-down sorularında SAP'ı tekrar çağırma) ──
_LIVE_CACHE: dict = {}          # session_id -> {integration_id, params, records, last_material, ts}
_LIVE_CACHE_MAX = 50
_LIVE_COLMAP = {"iv_material": "MATERIAL", "iv_vendor": "VENDOR",
                "iv_plant": "PLANT", "iv_fiscper": "FISCPER"}


def _live_cache_get(session_id, integration_id):
    c = _LIVE_CACHE.get(session_id or "")
    return c if (c and c.get("integration_id") == integration_id) else None


def _live_cache_put(session_id, integration_id, params, records):
    if not session_id:
        return
    if len(_LIVE_CACHE) >= _LIVE_CACHE_MAX:
        oldest = min(_LIVE_CACHE, key=lambda k: _LIVE_CACHE[k].get("ts", 0))
        _LIVE_CACHE.pop(oldest, None)
    _LIVE_CACHE[session_id] = {
        "integration_id": integration_id, "params": dict(params),
        "records": records, "last_material": params.get("iv_material"),
        "ts": time.time(),
    }


def _no_conflict(cached_params: dict, new_params: dict) -> bool:
    """Ortak filtre anahtarlarında değerler eşleşiyorsa önbellek yeni soruyu kapsar."""
    for k, v in (new_params or {}).items():
        if k in cached_params and str(cached_params[k]).strip() != str(v).strip():
            return False
    return True


def _filter_records(records: list, params: dict) -> list:
    out = records
    for k, v in (params or {}).items():
        col = _LIVE_COLMAP.get(k)
        if not col or v in (None, ""):
            continue
        vv = str(v).strip()
        out = [r for r in out if str(r.get(col, "")).strip() == vv]
    return out


def _answer_live(integration_id: int, user_question: str,
                 session_id: str = "", force_fresh: bool = False) -> dict:
    """
    CANLI sorgu yanıtı: parametreleri çıkar → (önbellekte uygun veri yoksa) servisi o an
    çağır → EV_SUCCESS/EV_MESSAGE'a göre cevapla. DRILL-DOWN: aynı oturumda uyumlu bir
    veri seti zaten çekildiyse SAP'a TEKRAR GİTMEZ; önbellekten firma-içi filtreleyip yanıtlar.
    """
    from app.repositories.integration_repository import IntegrationRepository
    from app.services.fetchers import query_integration_live

    config    = IntegrationRepository().get_with_params(integration_id)
    extracted = _extract_live_params(config, user_question)
    extracted = _normalize_live_params(config, extracted)   # yıl → YYYY001 vb.

    cached = None if force_fresh else _live_cache_get(session_id, integration_id)

    # "aynı/bu/o malzeme" gibi eliptik referansı önceki odaktan (last_material) çöz
    if cached and "iv_material" not in extracted and cached.get("last_material"):
        qn = _norm_q(user_question)
        if any(p in qn for p in ["ayni malzeme", "bu malzeme", "o malzeme",
                                  "ayni malzemeyi", "bu malzemeyi", "ayni urun", "bu urun"]):
            extracted["iv_material"] = cached["last_material"]

    from_cache = bool(cached) and _no_conflict(cached["params"], extracted)

    if from_cache:
        # SAP'a GİTME — önbellekteki geniş veri setini soruya göre filtrele
        records = _filter_records(cached["records"], extracted)
        success, message = True, f"(önbellekten {len(cached['records'])} kayıt)"
        pseudo_sql = f"-- ÖNBELLEK (SAP'a gidilmedi): {config.service_method} filtre={extracted}"
        print(f"[LIVE CACHE] oturum={session_id} → SAP'a gidilmedi, "
              f"{len(cached['records'])} kayıttan {len(records)} filtrelendi")
        # son odak malzemeyi güncelle (drill-down zinciri için)
        if extracted.get("iv_material"):
            cached["last_material"] = extracted["iv_material"]
    else:
        pseudo_sql = f"-- CANLI SAP sorgusu: {config.service_method}({extracted})"
        print(f"[LIVE] {config.name} → {config.service_method}({extracted})")
        res = query_integration_live(integration_id, extracted)
        if res.get("status") == "error":
            return {
                "mode": "live", "live_success": False,
                "error": f"Canlı SAP sorgusu başarısız: {res.get('message')}",
                "summary": f"❌ Servise bağlanılamadı veya hata döndü: {res.get('message')}",
                "rows": [], "count": 0, "chart_type": "NONE", "chart_data": {},
                "kpis": [], "highlights": [], "follow_ups": [],
                "tables_used": [config.name], "integration_names": [config.name],
                "sql": pseudo_sql,
            }
        success = res.get("success", True)
        message = res.get("message") or ""
        records = res.get("records") or []
        # Başarılı ve veri varsa oturum önbelleğine al (sonraki drill-down'lar için)
        if success and records:
            _live_cache_put(session_id, integration_id, extracted, records)

    if not success:
        return {
            "mode": "live", "live_success": False, "live_message": message,
            "summary": f"⚠️ SAP servisi hata bildirdi: {message or 'EV_SUCCESS=false'}",
            "rows": [], "count": 0, "chart_type": "NONE", "chart_data": {},
            "kpis": [], "highlights": [], "follow_ups": [],
            "tables_used": [config.name], "integration_names": [config.name],
            "sql": pseudo_sql,
        }

    records = _sort_live_for_ranking(user_question, records)  # sıralama sorularında üste taşı

    _hint = (config.schema_text or "")[:1500]
    if any(isinstance(r, dict) and "SATICI_ADI" in r for r in records):
        _hint += ("\n- SATICI_ADI → Satıcı (tedarikçi) ADI. Kullanıcıya satıcıyı VENDOR koduyla "
                  "DEĞİL, SATICI_ADI ile göster ve satıcılardan SATICI_ADI üzerinden bahset.")
    report, display_rows = _compose_report(
        user_question, records, [config.name], context_hint=_hint,
    )
    summary = report.get("text_summary", "")
    if message:
        summary = f"{summary}\n\nℹ️ {message}"

    return {
        "mode": "live", "live_success": True, "live_message": message,
        "from_cache": from_cache,
        "sql": pseudo_sql,
        "rows": display_rows[:500], "count": len(records),
        "summary": summary,
        "chart_type": report.get("chart_type", "NONE"),
        "chart_data": report.get("chart_data", {}),
        "kpis": report.get("kpis", []),
        "secondary_chart": report.get("secondary_chart"),
        "highlights": report.get("highlights", []),
        "follow_ups": report.get("follow_ups", [])[:3],
        "tables_used": [config.name], "integration_names": [config.name],
        "metrics_used": [],
    }


def ask(user_question: str, filters: dict | None = None,
        session_id: str | None = None, user_id: str | None = None,
        approval_mode: bool = False, force_fresh: bool = False,
        company: str | None = None) -> dict:
    """
    Donus:
    {
      "sql":         "SELECT ...",
      "rows":        [...],
      "count":       N,
      "summary":     "Turkce analiz metni",
      "chart_type":  "BAR | LINE | PIE | TABLE | NONE",
      "chart_data":  {"labels": [...], "datasets": [...]},
      "tables_used": ["shipments"],
      "integration_names": ["Shipment Service"],
      "rag_chunks":  [...],      # debug
      "error":       "..."       # sadece hata durumunda
    }
    """
    filters = filters or {}
    _usage_reset()   # bu istek için gerçek token sayacını sıfırla

    # -- 0. Niyet yönlendirme: bilgi/nasıl sorusu mu? → PDF-RAG (Belgeler) --------
    #    approval_mode=True yalnızca kullanıcı sohbetinde gelir (worker rerun'da False).
    #    force_fresh (worker rerun) bilgi yönlendirmesini atlar → veri hattı çalışır.
    if approval_mode and not force_fresh:
        try:
            from app.services.doc_rag import classify_intent, answer_question
            if classify_intent(user_question) == "knowledge":
                print(f"[ROUTER] '{user_question[:40]}...' → KNOWLEDGE (PDF-RAG)")
                return answer_question(user_question, company or "ALL")
        except Exception as _re:
            print(f"[ROUTER] yönlendirme atlandı: {_re}")

    _filter_str = json.dumps(filters, sort_keys=True) if filters else ""
    # session_id cache key'e GİRMEZ — aynı soru farklı oturumlarda farklı
    # bağlam çözümleyebilir, bu yüzden multi-turn modda cache'i bypass et.
    _sess_str = f"|sid={session_id}" if session_id else ""
    key = hashlib.md5((user_question + _filter_str + _sess_str).encode()).hexdigest()
    if key in _CACHE and not force_fresh:
        cached = _CACHE[key]
        # Hatalı cache'i bypass et
        if cached.get("error"):
            del _CACHE[key]
        else:
            print("[CACHE HIT]")
            return cached

    # -- 1. RAG: Qdrant'tan ilgili entegrasyonlari bul -----------------------
    chunks = _retrieve_chunks(user_question, top_k=5)

    # Tekrarsiz, skora gore sirali integration_id listesi
    seen        : set[int]  = set()
    matched_ids : list[int] = []
    for c in sorted(chunks, key=lambda x: x["score"], reverse=True):
        iid = c["integration_id"]
        if iid not in seen:
            seen.add(iid)
            matched_ids.append(iid)

    print(f"[RAG] Eslesen integration_id: {matched_ids}")

    # -- 2. Sema metinlerini cek (FİRMA filtreli) ----------------------------
    schemas = _fetch_schemas(matched_ids, company)
    if not schemas:
        # RAG eşleşmesi firma dışıysa → firmanın tüm aktif şemalarına düş
        schemas = _fetch_schemas([], company)
    if not schemas:
        return {"error": "Bu firma için aktif entegrasyon/şema bulunamadı.", "tables_used": []}

    tables_used        = [s["table"]            for s in schemas]
    integration_names  = list({s["integration_name"] for s in schemas})
    # Aday entegrasyonlar firma şemalarıyla sınırlı (firma dışı id sızmaz).
    schema_ids    = [s["integration_id"] for s in schemas]
    candidate_ids = [i for i in matched_ids if i in schema_ids] or schema_ids
    print(f"[RAG] Kullanilan tablolar: {tables_used} | Entegrasyonlar: {integration_names}")

    # -- 2b. CANLI (anlık) sorgu entegrasyonu mu? (SQL yok, o an SOAP'tan çek) ----
    # Firma-kapsamlı + anahtar-kelime tabanlı güvenilir yönlendirme (RAG'a bağımlı değil).
    _live_iid = _route_live(user_question, company, candidate_ids)
    if _live_iid:
        print(f"[ROUTER] '{user_question[:40]}...' → CANLI SORGU (id={_live_iid})")
        # session_id → aynı veri seti üzerine drill-down sorularında SAP'ı tekrar çağırma,
        # oturum önbelleğinden filtreleyerek cevapla.
        return _answer_live(_live_iid, user_question,
                            session_id=session_id, force_fresh=force_fresh)

    combined_schema = "\n\n".join(
        f"=== Tablo: {s['table']} (Entegrasyon: {s['integration_name']}) ===\n{s['schema_text']}"
        for s in schemas
    )

    # Rollup (özet) tablo ipucu — trend/eski-dönem sorgularını rollup'a yönlendirir
    try:
        from app.services.lifecycle.rollup import rollup_hint_for
        _rollup_hint = rollup_hint_for(list(dict.fromkeys(tables_used)))
    except Exception as _re:
        print(f"[ROLLUP HINT] atlandı: {_re}")
        _rollup_hint = ""
    if _rollup_hint:
        combined_schema += "\n" + _rollup_hint

    # Semantic Layer — firma + entegrasyon kapsamlı metrik sözlüğü
    _metric_block  = ""
    _metrics_used  = []
    try:
        from app.services import semantic_layer
        _metrics = semantic_layer.fetch_for(company, candidate_ids)
        _metric_block = semantic_layer.format_for_prompt(_metrics)
        _metrics_used = semantic_layer.detect_used(user_question, _metrics)
        if _metric_block:
            combined_schema += "\n" + _metric_block
        if _metrics_used:
            print(f"[SEMANTIC] kullanılan metrikler: {[m['key'] for m in _metrics_used]}")
    except Exception as _se:
        print(f"[SEMANTIC] metrik enjeksiyonu atlandı: {_se}")

    rag_context = ""
    if chunks:
        top_texts   = [c["chunk_text"] for c in chunks[:3]]
        rag_context = "\nIlgili baglam:\n" + "\n---\n".join(top_texts)

    # -- 3a. Niyet ayrıştır (Intent Parser) -----------------------------------
    import datetime as _dt
    _today     = _dt.date.today()
    _this_year = _today.year
    _today_str = _today.isoformat()

    # Sprint 2.4 — multi-turn context: son N=3 mesaj çiftini yükle
    history = _load_recent_context(session_id or "", n=3)
    if history:
        print(f"[CONTEXT] {len(history)} önceki mesaj yüklendi (session={session_id})")

    intent = _parse_intent(user_question, _today_str, history=history)
    print(f"[INTENT] {intent}")

    # Intent'ten ek bağlam oluştur
    _intent_context = f"\n=== SORGU ANALİZİ ===\nSorgu Tipi: {intent.get('sorgu_tipi','?')}\nAçıklama: {intent.get('aciklama','')}"
    if intent.get("donemler"):
        _intent_context += "\nTarih Dönemleri:"
        for d in intent["donemler"]:
            _intent_context += f"\n  {d.get('etiket','')}: {d.get('baslangic','')} → {d.get('bitis','')}"

    # Aktif sidebar filtrelerini bağlama ekle
    _filter_context = ""
    _filter_where   = []   # doğrudan WHERE'e eklenecek koşullar

    if filters:
        _filter_context = "\n=== AKTİF FİLTRELER (bunları SQL'e ekle) ==="
        if filters.get("start_date"):
            _filter_context += f"\n- Başlangıç tarihi: {filters['start_date']} (TRY_CAST(ERDAT AS DATE) >= bu tarih)"
            _filter_where.append(f"TRY_CAST(ERDAT AS DATE) >= '{filters['start_date']}'")
        if filters.get("end_date"):
            _filter_context += f"\n- Bitiş tarihi: {filters['end_date']} (TRY_CAST(ERDAT AS DATE) <= bu tarih)"
            _filter_where.append(f"TRY_CAST(ERDAT AS DATE) <= '{filters['end_date']}'")
        if filters.get("musteri"):
            _filter_context += f"\n- Müşteri adı içeriyor: '{filters['musteri']}'"
            _filter_where.append(f"UPPER(MUSTERI_ADI) LIKE UPPER('%{filters['musteri']}%')")
        if filters.get("city"):
            _filter_context += f"\n- Şehir: '{filters['city']}'"
            _filter_where.append(f"UPPER(CITY1) LIKE UPPER('%{filters['city']}%')")
        if filters.get("tdurum"):
            _filter_context += f"\n- Transfer durumu: '{filters['tdurum']}'"
            _filter_where.append(f"TDURUM = '{filters['tdurum']}'")
        _intent_context += _filter_context

    # -- 3b. Karşılaştırma sorgusu mu? Intent'ten tarihler geldiyse doğrudan SQL üret --------
    _is_compare = (
        intent.get("sorgu_tipi") == "karşılaştırma"
        or any(kw in user_question.lower() for kw in
               ['karşılaştır', 'kıyasla', 'fark', 'birinci', 'ikinci', 'hafta', 'dönem'])
    )
    _donemler = intent.get("donemler", [])

    sql = None  # başlangıçta None

    if _is_compare and len(_donemler) >= 2:
        # Intent tarihleri kesinleştirdi → GPT'siz doğrudan SQL oluştur
        d1, d2      = _donemler[0], _donemler[1]
        _all_start  = d1.get('baslangic', '')
        _all_end    = d2.get('bitis', '')
        _tbl        = tables_used[0] if tables_used else 'shipments'

        # Tarih WHERE koşulu — filtreler varsa onları da ekle
        _base_where = f"TRY_CAST(ERDAT AS DATE) BETWEEN '{_all_start}' AND '{_all_end}'"
        _extra = [c for c in _filter_where
                  if not c.startswith("TRY_CAST(ERDAT AS DATE) >=")
                  and not c.startswith("TRY_CAST(ERDAT AS DATE) <=")]
        _where_clause = _base_where
        if _extra:
            _where_clause += "\n  AND " + "\n  AND ".join(_extra)

        sql = (
            f"SELECT\n"
            f"  CASE\n"
            f"    WHEN TRY_CAST(ERDAT AS DATE) BETWEEN '{d1['baslangic']}' AND '{d1['bitis']}'"
            f" THEN '{d1['etiket']}'\n"
            f"    WHEN TRY_CAST(ERDAT AS DATE) BETWEEN '{d2['baslangic']}' AND '{d2['bitis']}'"
            f" THEN '{d2['etiket']}'\n"
            f"  END AS DONEM,\n"
            f"  COUNT(DISTINCT TKNUM)  AS SEVKIYAT_SAYISI,\n"
            f"  COUNT(*)               AS KALEM_SAYISI,\n"
            f"  ROUND(SUM(LFIMG), 2)   AS TOPLAM_MIKTAR,\n"
            f"  ROUND(AVG(LFIMG), 2)   AS ORTALAMA_MIKTAR\n"
            f"FROM [{_tbl}]\n"
            f"WHERE {_where_clause}\n"
            f"GROUP BY\n"
            f"  CASE\n"
            f"    WHEN TRY_CAST(ERDAT AS DATE) BETWEEN '{d1['baslangic']}' AND '{d1['bitis']}'"
            f" THEN '{d1['etiket']}'\n"
            f"    WHEN TRY_CAST(ERDAT AS DATE) BETWEEN '{d2['baslangic']}' AND '{d2['bitis']}'"
            f" THEN '{d2['etiket']}'\n"
            f"  END"
        )
        print(f"[SQL DIRECT] Karşılaştırma şablonu kullanıldı:\n{sql}")

    # -- 3c. Standart sorgular için GPT'ye sor --------------------------------
    if sql is None:
        _history_block = _format_history_for_prompt(history)
        sql_prompt = f"""Sen bir SAP Lojistik ve Microsoft SQL Server (T-SQL) uzmanısın.
Aşağıdaki şema ve bağlam bilgisini kullanarak kullanıcı sorusunu yanıtlayacak T-SQL SELECT sorgusunu yaz.

{combined_schema}
{rag_context}
{_intent_context}
{_history_block}

ÇOK TURLU SOHBET: Yukarıda önceki konuşma varsa ve mevcut soru kısa/eliptikse
("aynısını Mart için", "daha detaylı göster", "bunu grafikle"), önceki sorudaki
tablo/filtre/grup ölçütünü TAŞI. Sadece değişen kısmı (ör. yeni tarih) güncelle.

=== VERİTABANI BİLGİSİ ===
- Bugün: {_today.isoformat()} (yıl belirtilmezse {_this_year} kullan)
- ERDAT, DPLBG, FIDATUM vb. → NVARCHAR 'YYYY-MM-DD' → TRY_CAST(ERDAT AS DATE) kullan
- Türkçe aylar: Ocak=01 Şubat=02 Mart=03 Nisan=04 Mayıs=05 Haziran=06
  Temmuz=07 Ağustos=08 Eylül=09 Ekim=10 Kasım=11 Aralık=12
- LIMIT yok → SELECT TOP N kullan
- GROUP BY → tüm aggregate olmayan sütunları listele
- Metin araması → UPPER(kolon) LIKE UPPER('%aranan%')

KURAL: SADECE SELECT veya WITH ile başla. Açıklama, yorum veya markdown YAZMA.

Soru: {user_question}
SQL:"""
        sql = _clean_sql(_call_openai(sql_prompt, max_tokens=700))
        time.sleep(0.3)

    # -- 3d. Güvenlik kontrolü ------------------------------------------------
    if not _is_safe_sql(sql):
        print(f"[SECURITY] Güvenlik başarısız, retry...\nSQL: {sql[:200]}")
        retry_prompt = (
            f"Sen T-SQL uzmanısın. SADECE SELECT ile başlayan geçerli T-SQL yaz. "
            f"Açıklama, Türkçe metin veya markdown YAZMA.\n\n"
            f"Tablo: {tables_used[0] if tables_used else 'shipments'}\n"
            f"Tarih kolonları NVARCHAR 'YYYY-MM-DD' → TRY_CAST(kolon AS DATE) kullan.\n"
            f"Bugün: {_today.isoformat()}\n\n"
            f"Soru: {user_question}\nSQL:"
        )
        sql = _clean_sql(_call_openai(retry_prompt, max_tokens=600))
        time.sleep(0.3)

        if not _is_safe_sql(sql):
            return {"error": "Güvenlik denetimi: Geçerli bir SELECT sorgusu üretilemedi.",
                    "sql": sql, "tables_used": tables_used}

    # -- 4. T-SQL çalıştır, hata alınırsa CASE WHEN GROUP BY'ı düzelt --------
    rows = []
    try:
        conn   = get_connection()
        cursor = conn.cursor()
        cursor.execute(sql)
        columns = [col[0] for col in cursor.description]
        rows    = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()
    except Exception as e:
        err_msg = str(e)
        # Sık hata: GROUP BY'da aggregate olmayan sütun eksik
        # → GPT'ye SQL'i düzelt, tekrar dene
        if "GROUP BY" in err_msg.upper() or "column" in err_msg.lower() or "aggregate" in err_msg.lower():
            print(f"[SQL FIX] Hata: {err_msg[:120]} — SQL düzeltiliyor...")
            fix_prompt = (
                f"Bu T-SQL sorgusunu çalıştırdım ve hata aldım:\n"
                f"HATA: {err_msg}\n\n"
                f"SQL:\n{sql}\n\n"
                f"Hatayı düzelt ve sadece düzeltilmiş SELECT sorgusunu döndür. "
                f"Açıklama yazma. MSSQL T-SQL sözdizimi kullan."
            )
            sql = _clean_sql(_call_openai(fix_prompt, max_tokens=700))
            if not _is_safe_sql(sql):
                return {"error": err_msg, "sql": sql, "tables_used": tables_used}
            try:
                conn   = get_connection()
                cursor = conn.cursor()
                cursor.execute(sql)
                columns = [col[0] for col in cursor.description]
                rows    = [dict(zip(columns, row)) for row in cursor.fetchall()]
                conn.close()
            except Exception as e2:
                return {"error": str(e2), "sql": sql, "tables_used": tables_used}
        else:
            return {"error": err_msg, "sql": sql, "tables_used": tables_used}

    # -- 4b. 0 satır döndü: ya onay sürecini başlat ya da (eski mod) doğrudan çek --
    if len(rows) == 0 and candidate_ids:
        if approval_mode:
            # Human-in-the-loop: otomatik çekme yerine önce KULLANICIYA sor.
            # Kullanıcı onaylarsa frontend /approvals/request ile admin onayına düşürür.
            from app.services.ingestion import detect_gap
            gap = detect_gap(intent, candidate_ids, filters, question=user_question)
            if gap:
                return {
                    "status"           : "confirmation_needed",
                    "gap"              : gap.to_dict(),
                    "reason"           : gap.reason,
                    "summary"          : gap.reason,
                    "sql"              : sql,
                    "rows"             : [],
                    "count"            : 0,
                    "chart_type"       : "NONE",
                    "chart_data"       : {},
                    "kpis"             : [],
                    "highlights"       : [],
                    "tables_used"      : tables_used,
                    "integration_names": integration_names,
                    "metrics_used"     : _metrics_used,
                }
            # Gap yok → gerçekten veri yok; normal boş sonuç akışına devam
        else:
            rows = _try_on_demand_fetch(candidate_ids, intent, sql, tables_used)

    # -- 5. Çıktı moduna göre cevap: text (varsayılan) / table / report -------
    # Kullanıcı "göster/grafik/rapor/görsel" demedikçe sadece metinle analiz edip yanıtla.
    report, display_rows = _compose_report(user_question, rows, tables_used)

    result = {
        "sql"              : sql,
        "rows"             : display_rows,
        "count"            : len(rows),
        "summary"          : report.get("text_summary", ""),
        "chart_type"       : report.get("chart_type", "NONE"),
        "chart_data"       : report.get("chart_data", {}),
        "kpis"             : report.get("kpis", []),
        "secondary_chart"  : report.get("secondary_chart"),
        "highlights"       : report.get("highlights", []),
        "follow_ups"       : report.get("follow_ups", [])[:3],
        "tables_used"      : tables_used,
        "integration_names": integration_names,
        "metrics_used"     : _metrics_used,
        "rag_chunks"       : [c["chunk_text"] for c in chunks],
    }

    _CACHE[key] = result
    return result
