/* ============================================================================
   test_tables.sql — SAP-AI Copilot DEMO / TEST tabloları (MSSQL / T-SQL)

   Kullanım:
     1) SSMS'te DEMO/TEST veritabanını seç (örn. ZehraTestDB).
     2) Bu betiği çalıştır → tüm tablolar oluşur (varsa dokunmaz, idempotent).
     3) Sentetik veriyi doldurmak için:
          cd SAP-AI
          py testdata/seed_demo_data.py --yes      (shipments + sas_data + entegrasyonlar)
          py testdata/seed_demo_docs.py --yes       (PDF bilgi tabanı)

   NOT: Bu tabloların TAMAMI uygulama/seed tarafından da otomatik oluşturulur
   (IF NOT EXISTS). Bu dosya, şemayı SSMS'te açıkça kurmak/incelemek isteyenler
   içindir. GERÇEK üretim veritabanında DEĞİL, ayrı bir test DB'sinde çalıştırın.
   ============================================================================ */

/* ---------- 1) Entegrasyon meta tabloları ---------- */

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'integrations')
CREATE TABLE integrations (
    id             INT IDENTITY(1,1) PRIMARY KEY,
    name           NVARCHAR(200) NOT NULL UNIQUE,
    description    NVARCHAR(MAX),
    company        NVARCHAR(100) NULL,          -- çok-kiracılık (firma)
    service_type   NVARCHAR(20)  NULL,          -- SOAP / REST / ODATA
    wsdl_url       NVARCHAR(500),
    service_method NVARCHAR(200),
    username       NVARCHAR(100),
    password       NVARCHAR(100),
    auth_type      NVARCHAR(20)  NULL,          -- BASIC / BEARER / NONE
    extra_config   NVARCHAR(MAX) NULL,          -- JSON (örn. live_query, keywords)
    is_active      BIT DEFAULT 1,
    created_at     DATETIME DEFAULT GETDATE()
);

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'integration_schemas')
CREATE TABLE integration_schemas (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    integration_id  INT NOT NULL REFERENCES integrations(id),
    schema_text     NVARCHAR(MAX),
    target_table    NVARCHAR(100),
    updated_at      DATETIME DEFAULT GETDATE()
);

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'integration_params')
CREATE TABLE integration_params (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    integration_id  INT NOT NULL REFERENCES integrations(id),
    param_name      NVARCHAR(100),
    param_type      NVARCHAR(50),
    is_required     BIT DEFAULT 0,
    default_value   NVARCHAR(200),
    description     NVARCHAR(500)
);

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'integration_vectors')
CREATE TABLE integration_vectors (
    id               INT IDENTITY(1,1) PRIMARY KEY,
    integration_id   INT NOT NULL REFERENCES integrations(id),
    qdrant_point_id  NVARCHAR(100) NOT NULL UNIQUE,
    chunk_text       NVARCHAR(MAX),
    indexed_at       DATETIME DEFAULT GETDATE()
);

/* ---------- 2) Belge (PDF-RAG) tablosu ---------- */

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
);

/* ---------- 3) Sohbet geçmişi tabloları ---------- */

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'chat_sessions')
CREATE TABLE chat_sessions (
    id         NVARCHAR(40)  NOT NULL PRIMARY KEY,
    user_id    NVARCHAR(100) NOT NULL,
    title      NVARCHAR(500),
    tags       NVARCHAR(500) NULL,
    pinned     BIT NOT NULL DEFAULT 0,
    created_at DATETIME DEFAULT GETDATE(),
    updated_at DATETIME DEFAULT GETDATE()
);

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'chat_messages')
CREATE TABLE chat_messages (
    id         INT IDENTITY(1,1) PRIMARY KEY,
    session_id NVARCHAR(40)  NOT NULL,
    role       NVARCHAR(20)  NOT NULL,
    content    NVARCHAR(MAX),
    data_json  NVARCHAR(MAX),
    created_at DATETIME DEFAULT GETDATE()
);

/* ---------- 4) Veri tablosu: SEVKİYAT (sentetik) ----------
   Sistem kolonları: id, fetched_at, param_hash, integration_id
   Veri kolonları: SAP sevkiyat/teslimat alanları (NVARCHAR/FLOAT/INT) */

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'shipments_demo')
CREATE TABLE shipments_demo (
    id             INT IDENTITY(1,1) PRIMARY KEY,
    fetched_at     DATETIME DEFAULT GETDATE(),
    param_hash     NVARCHAR(20)  NULL,
    integration_id INT           NULL,
    TKNUM        NVARCHAR(20),    ERDAT       NVARCHAR(10),  ERNAM       NVARCHAR(50),
    DPLBG        NVARCHAR(10),    ROUTE       NVARCHAR(20),  ROUTE_TNM   NVARCHAR(100),
    SHTYP        NVARCHAR(10),    VSART       NVARCHAR(10),  VSART_TNM   NVARCHAR(50),
    TNDR_TRKID   NVARCHAR(40),    SIGNI       NVARCHAR(30),  ZDORSE_NO   NVARCHAR(30),
    SOFOR_ADI1   NVARCHAR(80),    SOFOR_ADI2  NVARCHAR(80),  NDURUM      NVARCHAR(10),
    ADURUM       NVARCHAR(10),    FIDATUM     NVARCHAR(10),  SDATUM      NVARCHAR(10),
    WADAT_IST    NVARCHAR(10),    VBELN       NVARCHAR(20),  ERDAT_LKP   NVARCHAR(10),
    ERNAM_LKP    NVARCHAR(50),    KUNAG       NVARCHAR(20),  MUSTERI_ADI NVARCHAR(120),
    KUNNR        NVARCHAR(20),    ISIM        NVARCHAR(120), BEZEI       NVARCHAR(120),
    CITY1        NVARCHAR(60),    POSNR       NVARCHAR(10),  MATNR       NVARCHAR(30),
    MAKTX        NVARCHAR(120),   LFIMG       FLOAT,         LGORT       NVARCHAR(10),
    ZZTDEPO      NVARCHAR(10),    VGBEL       NVARCHAR(20),  UMVKZ       INT,
    UMVKN        INT,             BSTKD       NVARCHAR(40),  TDURUM      NVARCHAR(10),
    TDURUM_TNM   NVARCHAR(50),    VOLUM       FLOAT,         VOLEH       NVARCHAR(10)
);

/* ---------- 5) Veri tablosu: SATINALMA (sentetik) ---------- */

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'sas_data_demo')
CREATE TABLE sas_data_demo (
    id             INT IDENTITY(1,1) PRIMARY KEY,
    fetched_at     DATETIME DEFAULT GETDATE(),
    param_hash     NVARCHAR(20)  NULL,
    integration_id INT           NULL,
    FISCPER     NVARCHAR(10),  FISCVARNT NVARCHAR(4),   PLANT      NVARCHAR(6),
    MATERIAL    NVARCHAR(40),  MAKTX     NVARCHAR(120), VENDOR     NVARCHAR(20),
    SATICI_ADI  NVARCHAR(120), AMOUNT    FLOAT,         PRICE      FLOAT,
    PRICE_UNIT  INT,           CURRENCY  NVARCHAR(5),   ZTERM      NVARCHAR(10),
    ZBPRME      NVARCHAR(10)
);

/* ============================================================================
   Aşağıdaki tablolar İLGİLİ ÖZELLİK KULLANILINCA uygulama tarafından OTOMATİK
   oluşturulur (elle gerekmez):
     - semantic_metrics      (Metrikler sayfası)
     - insights              (İçgörüler)
     - approval_requests, ingestion_jobs, audit_log   (İnsan-döngüde / HITL)
     - user_preferences      (kişiselleştirme)
     - shipments_daily       (rollup / veri yaşam döngüsü)
   ============================================================================ */
