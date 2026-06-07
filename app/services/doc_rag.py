"""
app/services/doc_rag.py — PDF tabanlı bilgi RAG'ı (firma bazında).

Yüklenen PDF'ler metne çevrilir, chunk'lanır, embed edilip ayrı bir Qdrant
koleksiyonuna (firma payload'lı) yazılır. "Nasıl yapılır / hata / yol haritası"
gibi bilgi soruları bu belgelerden yanıtlanır.

Public:
    index_pdf(file_bytes, filename, company, uploaded_by) -> dict
    answer_question(question, company) -> dict
    list_documents(company) -> list[dict]
    delete_document(document_id, company) -> bool
    classify_intent(question) -> "data" | "knowledge"
"""

from __future__ import annotations

import io
import os
import re
import uuid
from datetime import datetime

from openai        import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue,
)

from dotenv import load_dotenv
from app.services.db import get_connection

load_dotenv(override=True)   # .env sistem ortam değişkenlerini ezsin (doğru API anahtarı)
_openai = OpenAI()
_qdrant = QdrantClient(
    url=os.getenv("QDRANT_URL", "http://localhost:6333"),
    api_key=os.getenv("QDRANT_API_KEY", None),
    prefer_grpc=False, check_compatibility=False,
)

DOC_COLLECTION  = os.getenv("QDRANT_DOC_COLLECTION", "SAP-AI-DOCS")
EMBED_MODEL     = "text-embedding-3-small"
VECTOR_SIZE     = 1536
CHUNK_CHARS     = 1500
ANSWER_MODEL    = os.getenv("ANALYSIS_MODEL", "gpt-4o")


# ─────────────────────────────────────────────────────────────────────────────
# Qdrant / embedding yardımcıları
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_collection() -> None:
    existing = [c.name for c in _qdrant.get_collections().collections]
    if DOC_COLLECTION not in existing:
        _qdrant.create_collection(
            collection_name=DOC_COLLECTION,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
        print(f"[DOC-RAG] '{DOC_COLLECTION}' koleksiyonu oluşturuldu.")


def _embed(text: str) -> list[float]:
    resp = _openai.embeddings.create(model=EMBED_MODEL, input=text)
    try:
        from app.services.query_engine import _usage_add as _qe_usage_add
        _qe_usage_add(resp)
    except Exception:
        pass
    return resp.data[0].embedding


def _chunk(text: str, max_chars: int = CHUNK_CHARS) -> list[str]:
    """Paragraf/satır bazlı, ~max_chars'lık chunk'lar."""
    text = re.sub(r"\n{3,}", "\n\n", text)
    parts, cur, ln = [], [], 0
    for para in text.split("\n"):
        if ln + len(para) > max_chars and cur:
            parts.append("\n".join(cur)); cur, ln = [], 0
        cur.append(para); ln += len(para) + 1
    if cur:
        parts.append("\n".join(cur))
    return [p.strip() for p in parts if p.strip()] or ([text.strip()] if text.strip() else [])


# ─────────────────────────────────────────────────────────────────────────────
# documents tablosu
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_table(cursor) -> None:
    cursor.execute("""
        IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'documents')
        CREATE TABLE documents (
            id            INT IDENTITY(1,1) PRIMARY KEY,
            company       NVARCHAR(50),
            filename      NVARCHAR(300),
            title         NVARCHAR(300),
            page_count    INT,
            char_count    INT,
            chunk_count   INT,
            uploaded_by   NVARCHAR(50),
            uploaded_at   DATETIME DEFAULT GETDATE()
        )
    """)


# ─────────────────────────────────────────────────────────────────────────────
# PDF indexleme
# ─────────────────────────────────────────────────────────────────────────────

def index_pdf(file_bytes: bytes, filename: str, company: str,
              uploaded_by: str | None = None) -> dict:
    """PDF'i metne çevirir, embed edip Qdrant + documents'a yazar."""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(file_bytes))
    pages  = reader.pages
    text   = "\n".join((p.extract_text() or "") for p in pages).strip()

    if not text:
        return {"status": "error",
                "message": "PDF'ten metin çıkarılamadı (taranmış/görüntü PDF olabilir)."}

    chunks = _chunk(text)
    _ensure_collection()

    # documents satırı
    conn = get_connection(); cur = conn.cursor()
    try:
        _ensure_table(cur)
        cur.execute("""
            INSERT INTO documents
              (company, filename, title, page_count, char_count, chunk_count, uploaded_by)
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (company, filename[:300], filename[:300], len(pages),
              len(text), len(chunks), uploaded_by))
        doc_id = int(cur.fetchone()[0])
        conn.commit()
    finally:
        conn.close()

    # Qdrant upsert
    points = []
    for i, ch in enumerate(chunks):
        points.append(PointStruct(
            id=str(uuid.uuid4()),
            vector=_embed(ch),
            payload={"document_id": doc_id, "company": company,
                     "filename": filename, "chunk_index": i, "text": ch[:2000]},
        ))
    _qdrant.upsert(collection_name=DOC_COLLECTION, points=points)
    print(f"[DOC-RAG] '{filename}' ({company}) → {len(points)} chunk indexlendi (doc_id={doc_id}).")

    return {"status": "ok", "document_id": doc_id, "filename": filename,
            "pages": len(pages), "chunks": len(chunks)}


# ─────────────────────────────────────────────────────────────────────────────
# Soru yanıtlama (firma filtreli)
# ─────────────────────────────────────────────────────────────────────────────

def answer_question(question: str, company: str, top_k: int = 6) -> dict:
    """Belgelerden firma-filtreli RAG cevabı üretir."""
    try:
        _ensure_collection()
        qvec = _embed(question)
        # ALL (admin) → tüm firmalar; aksi halde firma filtresi
        qfilter = None
        if company and company != "ALL":
            qfilter = Filter(must=[FieldCondition(key="company", match=MatchValue(value=company))])
        # qdrant-client 1.12+ → query_points (eski .search kaldırıldı)
        _resp = _qdrant.query_points(collection_name=DOC_COLLECTION, query=qvec,
                                     limit=top_k, query_filter=qfilter, with_payload=True)
        hits = _resp.points
    except Exception as e:
        print(f"[DOC-RAG] Arama hatası: {e}")
        hits = []

    if not hits:
        return {
            "mode": "knowledge",
            "summary": ("Bu konuda yüklenmiş bir belge bulunamadı. "
                        "İlgili PDF'i **Belgeler** sayfasından yükledikten sonra tekrar sorabilirsiniz."),
            "sources": [], "rows": [], "count": 0,
            "chart_type": "NONE", "chart_data": {}, "kpis": [], "highlights": [],
            "follow_ups": [],
        }

    # Bağlam + kaynaklar
    context_blocks, sources = [], []
    for h in hits:
        p = h.payload or {}
        fn = p.get("filename", "?")
        txt = p.get("text", "")
        context_blocks.append(f"[Kaynak: {fn}]\n{txt}")
        sources.append({"filename": fn, "snippet": txt[:240]})

    context = "\n\n---\n\n".join(context_blocks)
    prompt = (
        "Aşağıdaki belge alıntılarına dayanarak kullanıcının sorusunu Türkçe yanıtla. "
        "Adım adım, uygulanabilir ve net ol. Yalnızca alıntılardaki bilgiyi kullan; "
        "bilgi yoksa 'belgelerde bu konuda bilgi yok' de.\n\n"
        f"=== BELGELER ===\n{context}\n\n=== SORU ===\n{question}\n\n"
        "Sadece geçerli JSON döndür:\n"
        '{"answer": "Türkçe yanıt metni (adım adım)", '
        '"follow_ups": ["Kullanıcının doğal olarak soracağı 3 kısa takip sorusu (en fazla 8 kelime, bu belgelere dayalı)"]}'
    )
    answer, follow_ups = "", []
    try:
        resp = _openai.chat.completions.create(
            model=ANSWER_MODEL, max_tokens=1000,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
        )
        try:    # gerçek token sayacına ekle (log için)
            from app.services.query_engine import _usage_add as _qe_usage_add
            _qe_usage_add(resp)
        except Exception:
            pass
        import json as _json
        parsed = _json.loads(resp.choices[0].message.content)
        answer = (parsed.get("answer") or "").strip()
        follow_ups = [str(x) for x in (parsed.get("follow_ups") or [])][:3]
    except Exception as e:
        answer = f"Yanıt üretilemedi: {e}"

    # Kaynakları benzersizleştir (dosya bazında)
    seen, uniq = set(), []
    for s in sources:
        if s["filename"] not in seen:
            seen.add(s["filename"]); uniq.append(s)

    return {
        "mode": "knowledge", "summary": answer, "sources": uniq,
        "rows": [], "count": 0, "chart_type": "NONE", "chart_data": {},
        "kpis": [], "highlights": [], "follow_ups": follow_ups,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Liste / silme
# ─────────────────────────────────────────────────────────────────────────────

def list_documents(company: str) -> list[dict]:
    conn = get_connection(); cur = conn.cursor()
    try:
        _ensure_table(cur); conn.commit()
        if company and company != "ALL":
            cur.execute("SELECT id, company, filename, page_count, chunk_count, uploaded_by, uploaded_at "
                        "FROM documents WHERE company = ? ORDER BY id DESC", (company,))
        else:
            cur.execute("SELECT id, company, filename, page_count, chunk_count, uploaded_by, uploaded_at "
                        "FROM documents ORDER BY id DESC")
        cols = [c[0] for c in cur.description]
        out = []
        for r in cur.fetchall():
            d = dict(zip(cols, r))
            if isinstance(d.get("uploaded_at"), datetime):
                d["uploaded_at"] = d["uploaded_at"].strftime("%d.%m.%Y %H:%M")
            out.append(d)
        return out
    finally:
        conn.close()


def delete_document(document_id: int, company: str) -> bool:
    """Belgeyi MSSQL + Qdrant'tan siler (firma sahipliği kontrollü)."""
    conn = get_connection(); cur = conn.cursor()
    try:
        _ensure_table(cur)
        # Sahiplik: admin (ALL) her şeyi, firma yalnız kendi belgesini siler
        if company and company != "ALL":
            cur.execute("SELECT id FROM documents WHERE id=? AND company=?", (document_id, company))
        else:
            cur.execute("SELECT id FROM documents WHERE id=?", (document_id,))
        if not cur.fetchone():
            return False
        cur.execute("DELETE FROM documents WHERE id=?", (document_id,))
        conn.commit()
    finally:
        conn.close()

    # Qdrant'tan ilgili chunk'ları sil
    try:
        _qdrant.delete(
            collection_name=DOC_COLLECTION,
            points_selector=Filter(must=[
                FieldCondition(key="document_id", match=MatchValue(value=int(document_id)))
            ]),
        )
    except Exception as e:
        print(f"[DOC-RAG] Qdrant silme uyarısı: {e}")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Niyet sınıflandırma — rapor/veri mi, bilgi/nasıl mı?
# ─────────────────────────────────────────────────────────────────────────────

_KNOWLEDGE_KW = (
    "nasıl", "nasil", "hata", "çöz", "coz", "ne yapmal", "yol harita", "adım", "adim",
    "kurulum", "yapılandır", "yapilandir", "rehber", "nedir", "anlat", "açıkla", "acikla",
    "troubleshoot", "hata alıyorum", "çalışmıyor", "calismiyor", "düzelt", "duzelt",
)
_DATA_KW = (
    "rapor", "göster", "goster", "kaç", "kac", "listele", "karşılaştır", "karsilastir",
    "kıyasla", "kiyasla", "toplam", "trend", "sevkiyat", "satış", "satis", "adet",
    "miktar", "grafik", "dağılım", "dagilim", "en çok", "en cok",
)


def classify_intent(question: str) -> str:
    """'data' (rapor/veri → SQL) veya 'knowledge' (bilgi → PDF) döner."""
    q = (question or "").lower()
    k_hit = sum(1 for kw in _KNOWLEDGE_KW if kw in q)
    d_hit = sum(1 for kw in _DATA_KW if kw in q)
    if k_hit and not d_hit:
        return "knowledge"
    if d_hit and not k_hit:
        return "data"
    if k_hit > d_hit:
        return "knowledge"
    if d_hit > k_hit:
        return "data"
    # Belirsiz → tek ucuz LLM kararı
    try:
        resp = _openai.chat.completions.create(
            model=os.getenv("SQL_MODEL", "gpt-4o"), max_tokens=5,
            messages=[{"role": "user", "content": (
                "Soru bir VERİ/RAPOR isteği mi yoksa NASIL-YAPILIR/BİLGİ isteği mi? "
                "Sadece 'data' veya 'knowledge' yaz.\nSoru: " + (question or ""))}],
        )
        ans = resp.choices[0].message.content.strip().lower()
        return "knowledge" if "knowledge" in ans else "data"
    except Exception:
        return "data"
