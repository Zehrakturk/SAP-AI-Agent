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

load_dotenv()

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
# Yardimcilar
# -----------------------------------------------------------------------------

def _embed(text: str) -> list[float]:
    resp = openai_client.embeddings.create(model=EMBED_MODEL, input=text)
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
            return resp.choices[0].message.content.strip()
        except Exception as e:
            if "429" in str(e):
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
        hits: list[ScoredPoint] = qdrant.search(
            collection_name=QDRANT_COLLECTION,
            query_vector=vector,
            limit=top_k,
            score_threshold=threshold,
        )
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

def _fetch_schemas(integration_ids: list[int]) -> list[dict]:
    """
    integration_schemas + integrations tablosundan schema_text getirir.
    integration_ids bossa tum aktif entegrasyonlar gelir (fallback).
    """
    conn   = get_connection()
    cursor = conn.cursor()

    if integration_ids:
        placeholders = ",".join("?" * len(integration_ids))
        cursor.execute(
            f"""
            SELECT s.integration_id, s.target_table, s.schema_text, i.name
            FROM   integration_schemas s
            JOIN   integrations i ON i.id = s.integration_id
            WHERE  s.integration_id IN ({placeholders})
              AND  i.is_active = 1
            """,
            integration_ids,
        )
    else:
        cursor.execute("""
            SELECT s.integration_id, s.target_table, s.schema_text, i.name
            FROM   integration_schemas s
            JOIN   integrations i ON i.id = s.integration_id
            WHERE  i.is_active = 1
        """)

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


def ask(user_question: str, filters: dict | None = None,
        session_id: str | None = None, user_id: str | None = None,
        approval_mode: bool = False, force_fresh: bool = False) -> dict:
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

    # -- 2. Sema metinlerini cek ---------------------------------------------
    schemas = _fetch_schemas(matched_ids)
    if not schemas:
        return {"error": "DB'de aktif entegrasyon/sema bulunamadi.", "tables_used": []}

    tables_used        = [s["table"]            for s in schemas]
    integration_names  = list({s["integration_name"] for s in schemas})
    # RAG eşleşmesi boşsa (fallback'te tüm şemalar geldiyse) gap tespiti için
    # aday entegrasyonları şemalardan türet → "veri yok → onay" akışı yine çalışsın.
    schema_ids    = [s["integration_id"] for s in schemas]
    candidate_ids = matched_ids or schema_ids
    print(f"[RAG] Kullanilan tablolar: {tables_used} | Entegrasyonlar: {integration_names}")

    combined_schema = "\n\n".join(
        f"=== Tablo: {s['table']} (Entegrasyon: {s['integration_name']}) ===\n{s['schema_text']}"
        for s in schemas
    )

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
                }
            # Gap yok → gerçekten veri yok; normal boş sonuç akışına devam
        else:
            rows = _try_on_demand_fetch(candidate_ids, intent, sql, tables_used)

    # -- 5. Zengin analiz + görselleştirme ------------------------------------
    if rows:
        report_prompt = f"""Sen bir kıdemli lojistik analistsin ve Power BI uzmanısın.
Kullanıcının sorusuna verilen SQL sorgusu çalıştırıldı ve aşağıdaki veriler geldi.
Bu verileri analiz edip zengin bir görselleştirme paketi üret.

Kullanıcı Sorusu: "{user_question}"
Kullanılan Tablolar: {', '.join(tables_used)}
Veri ({len(rows)} kayıt, ilk 200 gösteriliyor):
{json.dumps(rows[:200], ensure_ascii=False, default=str)}

KURALLAR:
- Karşılaştırma sorusuysa (iki dönem, iki grup vb.) PRIMARY chart GROUPED BAR olsun, secondary LINE olsun.
- Dağılım sorusuysa PRIMARY PIE, secondary BAR.
- Zaman serisi / trend sorusuysa PRIMARY LINE (fill:true), secondary BAR.
- Tekil liste sorusuysa PRIMARY yatay BAR (type: "bar", indexAxis: "y"), secondary TABLE.
- datasets içinde birden fazla veri seti olabilir (gruplu karşılaştırma için).
- kpis: Her zaman 3-4 adet KPI üret. Sayısal değerler için toplam, ortalama, maksimum, değişim yüzdesi hesapla.
- change alanı: "+%12.3" veya "-%5.1" formatında, trend: "up" veya "down".
- highlights: 3 adet kısa Türkçe bulgu cümlesi (emoji ile).
- secondary_chart null olabilir ama mümkünse doldur.

Sadece geçerli JSON döndür:
{{
  "text_summary": "Kapsamlı Türkçe analiz metni. Farkları, yüzdeleri, öne çıkan değerleri belirt. En az 3 cümle.",
  "chart_type": "BAR veya LINE veya PIE",
  "chart_data": {{
    "labels": ["Etiket1", "Etiket2"],
    "datasets": [
      {{"label": "Veri Seti 1", "data": [100, 200]}},
      {{"label": "Veri Seti 2", "data": [150, 180]}}
    ]
  }},
  "kpis": [
    {{"label": "Toplam Sevkiyat", "value": "247", "change": "+12.3%", "trend": "up", "color": "blue"}},
    {{"label": "Haftalık Ort.", "value": "61.8", "change": "+8.1%", "trend": "up", "color": "green"}},
    {{"label": "En Yüksek Gün", "value": "43", "change": null, "trend": null, "color": "amber"}},
    {{"label": "Değişim", "value": "%+49", "change": null, "trend": "up", "color": "red"}}
  ],
  "secondary_chart": {{
    "type": "LINE",
    "title": "Günlük Dağılım",
    "data": {{
      "labels": ["1.Hafta", "2.Hafta"],
      "datasets": [{{"label": "Günlük Ort.", "data": [8.8, 13.1]}}]
    }}
  }},
  "highlights": [
    "📦 1. haftada 62, 2. haftada 91 sevkiyat gerçekleşti — %46.8 artış",
    "🏆 En yoğun gün 8 Nisan ile 18 sevkiyat",
    "📍 İstanbul en çok sevkiyat yapılan şehir (%34)"
  ]
}}"""

        try:
            report = json.loads(_call_openai(report_prompt, max_tokens=1800, json_mode=True,
                                             model=_ANALYSIS_MODEL))
        except Exception:
            report = {
                "text_summary"    : "Analiz edilemedi.",
                "chart_type"      : "BAR",
                "chart_data"      : {},
                "kpis"            : [],
                "secondary_chart" : None,
                "highlights"      : [],
            }
    else:
        report = {
            "text_summary"    : "Belirtilen kriterlere uygun veri bulunamadı.",
            "chart_type"      : "NONE",
            "chart_data"      : {},
            "kpis"            : [],
            "secondary_chart" : None,
            "highlights"      : [],
        }

    result = {
        "sql"              : sql,
        "rows"             : rows,
        "count"            : len(rows),
        "summary"          : report.get("text_summary", ""),
        "chart_type"       : report.get("chart_type", "NONE"),
        "chart_data"       : report.get("chart_data", {}),
        "kpis"             : report.get("kpis", []),
        "secondary_chart"  : report.get("secondary_chart"),
        "highlights"       : report.get("highlights", []),
        "tables_used"      : tables_used,
        "integration_names": integration_names,
        "rag_chunks"       : [c["chunk_text"] for c in chunks],
    }

    _CACHE[key] = result
    return result
