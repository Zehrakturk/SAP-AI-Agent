"""
app/services/qdrant_indexer.py

MSSQL'deki integration_schemas tablosunu okur,
metinleri embed eder ve Qdrant'a indexler.
Sonuçları integration_vectors tablosuna kaydeder.

Tablo şemaları (MSSQL):
  integrations        — id, name, description, wsdl_url, service_method, username, password, is_active
  integration_schemas — id, integration_id, schema_text, target_table, updated_at
  integration_vectors — id, integration_id, qdrant_point_id, chunk_text
"""

from __future__ import annotations

import os
import uuid

from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

from app.services.db import get_connection

load_dotenv()

openai_client = OpenAI()

qdrant = QdrantClient(
    url=os.getenv("QDRANT_URL", "http://localhost:6333"),
    api_key=os.getenv("QDRANT_API_KEY", None),
    prefer_grpc=False,
    check_compatibility=False,
)

COLLECTION      = os.getenv("QDRANT_COLLECTION", "SAP-AI")
EMBED_MODEL     = "text-embedding-3-small"
VECTOR_SIZE     = 1536
CHUNK_MAX_CHARS = 1500


def _ensure_collection() -> None:
    existing = [c.name for c in qdrant.get_collections().collections]
    if COLLECTION not in existing:
        qdrant.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
        print(f"[QDRANT] '{COLLECTION}' koleksiyonu oluşturuldu.")
    else:
        print(f"[QDRANT] '{COLLECTION}' koleksiyonu zaten mevcut.")


def _embed(text: str) -> list[float]:
    resp = openai_client.embeddings.create(model=EMBED_MODEL, input=text)
    return resp.data[0].embedding


def _chunk_text(text: str, max_chars: int = CHUNK_MAX_CHARS) -> list[str]:
    """Büyük şema metinlerini satır bazlı chunk'lara böler."""
    lines   = text.splitlines()
    chunks  = []
    current: list[str] = []
    length  = 0

    for line in lines:
        if length + len(line) > max_chars and current:
            chunks.append("\n".join(current))
            current = []
            length  = 0
        current.append(line)
        length += len(line) + 1

    if current:
        chunks.append("\n".join(current))

    return chunks or [text]


def index_integration(integration_id: int) -> int:
    """
    Belirtilen entegrasyonun tüm şemalarını Qdrant'a (yeniden) indexler.
    Önce eski vektörleri Qdrant + MSSQL'den siler, sonra yeniden embed eder.
    Döner: indexlenen chunk sayısı
    """
    _ensure_collection()

    conn   = get_connection()
    cursor = conn.cursor()

    # 1. Eski vektörleri temizle
    cursor.execute(
        "SELECT qdrant_point_id FROM integration_vectors WHERE integration_id = ?",
        (integration_id,),
    )
    old_ids = [r[0] for r in cursor.fetchall()]

    if old_ids:
        qdrant.delete(collection_name=COLLECTION, points_selector=old_ids)
        cursor.execute(
            "DELETE FROM integration_vectors WHERE integration_id = ?",
            (integration_id,),
        )
        conn.commit()
        print(f"[INDEX] {len(old_ids)} eski vektör silindi.")

    # 2. Şema metinlerini oku
    cursor.execute("""
        SELECT s.id, s.target_table, s.schema_text, i.name, i.description
        FROM   integration_schemas s
        JOIN   integrations i ON i.id = s.integration_id
        WHERE  s.integration_id = ?
          AND  i.is_active = 1
    """, (integration_id,))
    schemas = cursor.fetchall()

    if not schemas:
        conn.close()
        raise ValueError(f"integration_id={integration_id} icin aktif sema bulunamadi.")

    points    : list[PointStruct] = []
    db_records: list[tuple]       = []

    for schema_id, target_table, schema_text, int_name, int_desc in schemas:
        header    = (
            f"Entegrasyon: {int_name}\n"
            f"Aciklama: {int_desc or ''}\n"
            f"Tablo: {target_table}\n"
        )
        full_text = header + (schema_text or "")
        chunks    = _chunk_text(full_text)

        for chunk in chunks:
            point_id = str(uuid.uuid4())
            vector   = _embed(chunk)

            points.append(PointStruct(
                id      = point_id,
                vector  = vector,
                payload = {
                    "integration_id"  : integration_id,
                    "schema_id"       : schema_id,
                    "target_table"    : target_table,
                    "integration_name": int_name,
                },
            ))
            db_records.append((integration_id, point_id, chunk[:1000]))

    # 3. Qdrant'a toplu upsert
    qdrant.upsert(collection_name=COLLECTION, points=points)
    print(f"[QDRANT] {len(points)} chunk upsert edildi.")

    # 4. MSSQL'e kaydet
    cursor.executemany(
        "INSERT INTO integration_vectors (integration_id, qdrant_point_id, chunk_text) "
        "VALUES (?, ?, ?)",
        db_records,
    )
    conn.commit()
    conn.close()

    print(f"[INDEX] integration_id={integration_id} -> {len(points)} chunk indexlendi.")
    return len(points)


def index_all_integrations() -> dict:
    """Tüm aktif entegrasyonları Qdrant'a indexler."""
    _ensure_collection()

    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM integrations WHERE is_active = 1")
    integrations = cursor.fetchall()
    conn.close()

    if not integrations:
        return {"message": "Aktif entegrasyon bulunamadi."}

    results = {}
    for int_id, int_name in integrations:
        try:
            count = index_integration(int_id)
            results[int_name] = {"status": "ok", "chunks": count}
        except Exception as e:
            results[int_name] = {"status": "error", "message": str(e)}

    return results


if __name__ == "__main__":
    print("Tum entegrasyonlar indexleniyor...")
    result = index_all_integrations()
    for name, info in result.items():
        if info.get("status") == "ok":
            print(f"  OK  {name}: {info['chunks']} chunk")
        else:
            print(f"  ERR {name}: {info['message']}")
