"""
data/setup_db.py

MSSQL'de gerekli tabloları oluşturur, integration + schema seed verisini ekler,
ardından Qdrant'a indexler.

Kullanım:
    cd SAP-AI
    python data/setup_db.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.services.db import get_connection

# ── Shipments tablosu şema açıklaması (Qdrant'a indexlenecek metin) ──────────
SHIPMENT_SCHEMA_TEXT = """
Tablo: shipments
Açıklama: SAP'den gelen sevkiyat (taşıma) verileri. Her satır bir ürün kaleminin
sevkiyat bilgisini temsil eder.

=== ÖNEMLİ: KOLON TİPLERİ ===
Tarih sütunları NVARCHAR(10) formatında saklanır: 'YYYY-MM-DD' (örn: '2025-04-03')
Tarih karşılaştırmalarında mutlaka TRY_CAST(ERDAT AS DATE) kullan.
Sayısal sütunlar: LFIMG, VOLUM (float), UMVKZ, UMVKN (int)

Kolonlar ve Tipleri:
- TKNUM       : NVARCHAR — Taşıma/Sevkiyat numarası (birincil tanımlayıcı, örn: '0012345678')
- ERDAT       : NVARCHAR(10) tarih 'YYYY-MM-DD' — Sevkiyat oluşturma tarihi
- ERNAM       : NVARCHAR — Oluşturan kullanıcı
- DPLBG       : NVARCHAR(10) tarih 'YYYY-MM-DD' — Planlanan yükleme tarihi
- ROUTE       : NVARCHAR — Rota kodu
- ROUTE_TNM   : NVARCHAR — Rota adı
- SHTYP       : NVARCHAR — Sevkiyat tipi kodu
- VSART       : NVARCHAR — Nakliye tipi kodu
- VSART_TNM   : NVARCHAR — Nakliye tipi adı (örn: 'Karayolu', 'Denizyolu', 'Havayolu')
- TNDR_TRKID  : NVARCHAR — İhale takip numarası
- SIGNI       : NVARCHAR — Araç plaka numarası
- ZDORSE_NO   : NVARCHAR — Dorse plaka numarası
- SOFOR_ADI1  : NVARCHAR — Sürücü 1 adı soyadı
- SOFOR_ADI2  : NVARCHAR — Sürücü 2 adı soyadı
- NDURUM      : NVARCHAR — Nümerik durum kodu
- ADURUM      : NVARCHAR — Alfanümerik durum kodu
- FIDATUM     : NVARCHAR(10) tarih 'YYYY-MM-DD' — Fiili yükleme tarihi
- SDATUM      : NVARCHAR(10) tarih 'YYYY-MM-DD' — Planlanan teslimat tarihi
- WADAT_IST   : NVARCHAR(10) tarih 'YYYY-MM-DD' — İstenilen teslimat tarihi
- VBELN       : NVARCHAR — Teslimat belgesi numarası
- ERDAT_LKP   : NVARCHAR(10) tarih 'YYYY-MM-DD' — Teslimat oluşturma tarihi
- ERNAM_LKP   : NVARCHAR — Teslimatı oluşturan kullanıcı
- KUNAG       : NVARCHAR — Sipariş veren müşteri kodu
- MUSTERI_ADI : NVARCHAR — Müşteri adı (tam metin)
- KUNNR       : NVARCHAR — Sevk yapılacak müşteri kodu
- ISIM        : NVARCHAR — Firma/müşteri ismi
- BEZEI       : NVARCHAR — Açıklama
- CITY1       : NVARCHAR — Teslimat şehri (örn: 'İstanbul', 'Ankara')
- POSNR       : NVARCHAR — Pozisyon numarası
- MATNR       : NVARCHAR — Malzeme numarası
- MAKTX       : NVARCHAR — Malzeme açıklaması
- LFIMG       : FLOAT — Teslim edilen miktar
- LGORT       : NVARCHAR — Depo yeri kodu
- ZZTDEPO     : NVARCHAR — Hedef depo kodu
- VGBEL       : NVARCHAR — Kaynak belge numarası
- UMVKZ       : INT — Birim dönüşüm payı
- UMVKN       : INT — Birim dönüşüm paydası
- BSTKD       : NVARCHAR — Müşteri sipariş numarası
- TDURUM      : NVARCHAR — Taşıma durum kodu (örn: '01','02','03','04','05')
- TDURUM_TNM  : NVARCHAR — Durum açıklaması (örn: 'OLUŞTURULDU', 'MAL ÇIKIŞI YAPILDI', 'TESLİM EDİLDİ')
- VOLUM       : FLOAT — Hacim değeri
- VOLEH       : NVARCHAR — Hacim birimi (örn: 'M3')
- fetched_at  : DATETIME — SAP'den çekilme zamanı

=== ÖRNEK T-SQL SORGULAR ===

-- Tarih aralığı filtreleme:
SELECT COUNT(*) AS SAYI FROM shipments
WHERE TRY_CAST(ERDAT AS DATE) BETWEEN '2025-04-01' AND '2025-04-07'

-- Haftalık karşılaştırma (CASE WHEN ile):
SELECT
  CASE WHEN TRY_CAST(ERDAT AS DATE) BETWEEN '2025-04-01' AND '2025-04-07' THEN '1. Hafta (1-7 Nisan)'
       WHEN TRY_CAST(ERDAT AS DATE) BETWEEN '2025-04-08' AND '2025-04-15' THEN '2. Hafta (8-15 Nisan)'
  END AS HAFTA,
  COUNT(DISTINCT TKNUM) AS SEVKIYAT_SAYISI,
  SUM(LFIMG) AS TOPLAM_MIKTAR
FROM shipments
WHERE TRY_CAST(ERDAT AS DATE) BETWEEN '2025-04-01' AND '2025-04-15'
GROUP BY
  CASE WHEN TRY_CAST(ERDAT AS DATE) BETWEEN '2025-04-01' AND '2025-04-07' THEN '1. Hafta (1-7 Nisan)'
       WHEN TRY_CAST(ERDAT AS DATE) BETWEEN '2025-04-08' AND '2025-04-15' THEN '2. Hafta (8-15 Nisan)'
  END

-- Şehir bazlı dağılım:
SELECT CITY1, COUNT(DISTINCT TKNUM) AS ADET FROM shipments
WHERE TRY_CAST(ERDAT AS DATE) >= '2025-04-01'
GROUP BY CITY1 ORDER BY ADET DESC

-- Müşteri arama (büyük/küçük harf duyarsız):
SELECT * FROM shipments
WHERE UPPER(MUSTERI_ADI) LIKE UPPER('%aranan%')
"""

INTEGRATION_NAME        = "Sevkiyat Servisi"
INTEGRATION_DESCRIPTION = (
    "SAP sisteminden sevkiyat, taşıma ve teslimat verilerini SOAP/WSDL üzerinden çeker. "
    "Müşteri bazlı teslimat durumları, gecikme analizleri, rota/plaka takibi ve hacim "
    "raporları için kullanılır."
)
# SAP bağlantı bilgileri .env'den okunur (kaynak kodda düz metin tutulmaz).
WSDL_URL       = os.getenv("SAP_WSDL_URL", "")
SERVICE_METHOD = os.getenv("SAP_SERVICE_METHOD", "ZWHSD_FG001_009_WS")
SAP_USERNAME   = os.getenv("SAP_USERNAME", "")
SAP_PASSWORD   = os.getenv("SAP_PASSWORD", "")


def create_tables(cursor):
    """MSSQL'de gerekli tabloları oluştur (yoksa)."""

    cursor.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM sys.tables WHERE name = 'integrations'
        )
        CREATE TABLE integrations (
            id             INT IDENTITY(1,1) PRIMARY KEY,
            name           NVARCHAR(200) NOT NULL UNIQUE,
            description    NVARCHAR(MAX),
            wsdl_url       NVARCHAR(500),
            service_method NVARCHAR(200),
            username       NVARCHAR(100),
            password       NVARCHAR(100),
            is_active      BIT DEFAULT 1,
            created_at     DATETIME DEFAULT GETDATE()
        )
    """)
    print("[DB] integrations tablosu hazır.")

    cursor.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM sys.tables WHERE name = 'integration_schemas'
        )
        CREATE TABLE integration_schemas (
            id              INT IDENTITY(1,1) PRIMARY KEY,
            integration_id  INT NOT NULL REFERENCES integrations(id),
            schema_text     NVARCHAR(MAX),
            target_table    NVARCHAR(100),
            updated_at      DATETIME DEFAULT GETDATE()
        )
    """)
    print("[DB] integration_schemas tablosu hazır.")

    cursor.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM sys.tables WHERE name = 'integration_vectors'
        )
        CREATE TABLE integration_vectors (
            id               INT IDENTITY(1,1) PRIMARY KEY,
            integration_id   INT NOT NULL REFERENCES integrations(id),
            qdrant_point_id  NVARCHAR(100) NOT NULL UNIQUE,
            chunk_text       NVARCHAR(MAX),
            indexed_at       DATETIME DEFAULT GETDATE()
        )
    """)
    print("[DB] integration_vectors tablosu hazır.")

    cursor.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM sys.tables WHERE name = 'integration_params'
        )
        CREATE TABLE integration_params (
            id              INT IDENTITY(1,1) PRIMARY KEY,
            integration_id  INT NOT NULL REFERENCES integrations(id),
            param_name      NVARCHAR(100),
            param_type      NVARCHAR(50),
            is_required     BIT DEFAULT 0,
            default_value   NVARCHAR(200),
            description     NVARCHAR(500)
        )
    """)
    print("[DB] integration_params tablosu hazır.")


def seed_integration(cursor) -> int:
    """
    Entegrasyon kaydını ekle (zaten varsa atla).
    Döner: integration_id
    """
    cursor.execute(
        "SELECT id FROM integrations WHERE name = ?",
        (INTEGRATION_NAME,),
    )
    row = cursor.fetchone()
    if row:
        int_id = row[0]
        print(f"[SEED] '{INTEGRATION_NAME}' zaten mevcut (id={int_id}), atlanıyor.")
        return int_id

    cursor.execute("""
        INSERT INTO integrations (name, description, wsdl_url, service_method, username, password, is_active)
        VALUES (?, ?, ?, ?, ?, ?, 1)
    """, (
        INTEGRATION_NAME,
        INTEGRATION_DESCRIPTION,
        WSDL_URL,
        SERVICE_METHOD,
        SAP_USERNAME,
        SAP_PASSWORD,
    ))
    cursor.execute("SELECT id FROM integrations WHERE name = ?", (INTEGRATION_NAME,))
    int_id = cursor.fetchone()[0]
    print(f"[SEED] '{INTEGRATION_NAME}' eklendi (id={int_id}).")
    return int_id


def seed_schema(cursor, integration_id: int):
    """integration_schemas tablosuna schema_text ekle (zaten varsa güncelle)."""
    cursor.execute(
        "SELECT id FROM integration_schemas WHERE integration_id = ? AND target_table = 'shipments'",
        (integration_id,),
    )
    row = cursor.fetchone()
    if row:
        cursor.execute(
            "UPDATE integration_schemas SET schema_text = ?, updated_at = GETDATE() WHERE id = ?",
            (SHIPMENT_SCHEMA_TEXT, row[0]),
        )
        print(f"[SEED] integration_schemas güncellendi (id={row[0]}).")
    else:
        cursor.execute(
            "INSERT INTO integration_schemas (integration_id, schema_text, target_table) VALUES (?, ?, 'shipments')",
            (integration_id, SHIPMENT_SCHEMA_TEXT),
        )
        print("[SEED] integration_schemas eklendi.")


def seed_params(cursor, integration_id: int):
    """SAP SOAP metodunun parametrelerini ekle."""
    params = [
        ("ISTART_DATE",  "DATE", 1, None,       "Başlangıç tarihi (YYYYMMDD formatında)"),
        ("IFINISH_DATE", "DATE", 1, None,       "Bitiş tarihi (YYYYMMDD formatında)"),
    ]
    for p_name, p_type, is_req, default, desc in params:
        cursor.execute(
            "SELECT id FROM integration_params WHERE integration_id = ? AND param_name = ?",
            (integration_id, p_name),
        )
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO integration_params (integration_id, param_name, param_type, is_required, default_value, description)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (integration_id, p_name, p_type, is_req, default, desc))
            print(f"[SEED] Parametre eklendi: {p_name}")
        else:
            print(f"[SEED] Parametre zaten mevcut: {p_name}")


def main():
    print("=" * 55)
    print("  SAP-AI  —  MSSQL Kurulum & Seed Scripti")
    print("=" * 55)

    conn   = get_connection()
    cursor = conn.cursor()

    print("\n[1/3] Tablolar oluşturuluyor...")
    create_tables(cursor)
    conn.commit()

    print("\n[2/3] Seed verisi ekleniyor...")
    int_id = seed_integration(cursor)
    seed_schema(cursor, int_id)
    seed_params(cursor, int_id)
    conn.commit()
    conn.close()

    print("\n[3/3] Qdrant indexleme başlatılıyor...")
    from app.services.qdrant_indexer import index_all_integrations
    results = index_all_integrations()
    for name, info in results.items():
        if info.get("status") == "ok":
            print(f"  OK  {name}: {info['chunks']} chunk indexlendi")
        else:
            print(f"  ERR {name}: {info.get('message', '?')}")

    print("\nKurulum tamamlandı. 'python run.py' ile uygulamayı başlatabilirsiniz.")


if __name__ == "__main__":
    main()
