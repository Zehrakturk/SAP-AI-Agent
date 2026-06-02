"""
app/models/store.py
In-memory data store — replace with a real DB (SQLite / PostgreSQL) for production.
Schema mirrors Section 12 of the project documentation.
"""
from datetime import datetime, timedelta
import os
import pyodbc
import random
import sqlite3
from pathlib import Path
from dotenv import load_dotenv
from zeep.helpers import serialize_object
from decimal import Decimal

load_dotenv()

# Kimlik bilgileri .env'den okunur — kaynak kodda düz metin tutulmaz.
DB_SERVER = os.getenv("DB_SERVER", "")
DB_NAME   = os.getenv("DB_NAME", "")
DB_USER   = os.getenv("DB_USER", "")
DB_PASS   = os.getenv("DB_PASS", "")

CONN_STR = (
    f"DRIVER={{ODBC Driver 18 for SQL Server}};"
    f"SERVER={DB_SERVER};"
    f"DATABASE={DB_NAME};"
    f"UID={DB_USER};"
    f"PWD={DB_PASS};"
    f"TrustServerCertificate=yes;"   # ← self-signed sertifika varsa
    f"Encrypt=yes;"
)
# ─────────────────────────────────────────────
# USERS
# ─────────────────────────────────────────────
USERS = [
    {"id": 1, "username": "admin",      "password": "admin123", "name": "System Admin",  "role": "ADMIN",       "department": "IT",          "status": "active",   "created_at": "2025-01-10", "last_login": "2 min ago"},
    {"id": 8, "username": "p.frank",   "password": "view123",  "name": "Paul Frank",    "role": "VIEWER",      "department": "Management",  "status": "inactive", "created_at": "2025-03-11", "last_login": "5 days ago"},
]

# ─────────────────────────────────────────────
# CHAT SESSIONS & MESSAGES
# ─────────────────────────────────────────────
CHAT_SESSIONS = [
    
]

CHAT_MESSAGES = {
   
}

# ─────────────────────────────────────────────
# AI LOGS  (generated on import)
# ─────────────────────────────────────────────
_USERS_IDS  = ["a.mueller", "r.kaya", "k.yilmaz", "j.bauer", "h.schmidt", "admin"]
_MODELS     = ["claude-sonnet-4-6", "claude-opus-4-6", "claude-haiku-4-5"]
_QUESTIONS  = [
    "Which suppliers had delayed deliveries?",
    "What are critical stock levels?",
    "Highest cost increase this month?",
    "Best quote request available?",
    "Summary of purchase orders this week?",
    "Finance report for cost center CC-3300?",
    "Outstanding purchase requests?",
    "Stock replenishment recommendations?",
]

def _generate_logs(n=80):
    logs = []
    now = datetime.now()
    for i in range(n):
        dt = now - timedelta(seconds=random.randint(0, 7 * 24 * 3600))
        logs.append({
            "id":        f"LOG-{str(n - i).zfill(4)}",
            "user_id":   random.choice(_USERS_IDS),
            "question":  random.choice(_QUESTIONS),
            "response":  "AI generated response stored here.",
            "model":     random.choice(_MODELS),
            "tokens":    random.randint(800, 4800),
            "latency":   random.randint(600, 2200),
            "status":    "error" if random.random() < 0.08 else "success",
            "timestamp": dt.strftime("%d %b %H:%M"),
            "_sort_ts":  dt.timestamp(),
        })
    logs.sort(key=lambda x: x["_sort_ts"], reverse=True)
    return logs

AI_LOGS = _generate_logs(80)

# ─────────────────────────────────────────────
# SETTINGS
# ─────────────────────────────────────────────
SETTINGS = {
    "model":          "claude-sonnet-4-6",
    "temperature":    0.2,
    "max_tokens":     1024,
    "top_p":          0.95,
    "daily_budget":   50000,
    "backend_url":    "http://localhost:8000",
    "rate_limit":     10,
    "timeout":        30,
    "system_prompt":  (
        "You are an SAP AI Copilot. You assist users with SAP data analysis. "
        "Only use data retrieved via approved tools. Never access SAP tables directly. "
        "Respect role-based access controls."
    ),
    "security": {
        "prompt_injection_protection": True,
        "rbac":                        True,
        "sensitive_data_filtering":    True,
        "rate_limiting":               True,
        "audit_logging":               True,
        "session_expiry":              True,
    },
    "logging": {
        "log_questions":     True,
        "log_responses":     True,
        "log_tokens":        True,
        "log_tool_calls":    True,
        "log_auth_failures": True,
        "retention_days":    90,
        "log_level":         "INFO",
    },
}

DB_PATH = Path(__file__).parent.parent.parent / "data" / "sap_data.db"

def get_conn():
    DB_PATH.parent.mkdir(exist_ok=True)
    return sqlite3.connect(DB_PATH)

def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS shipments (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                fetched_at  DATETIME DEFAULT CURRENT_TIMESTAMP,

                TKNUM       TEXT,
                ERDAT       TEXT,
                ERNAM       TEXT,
                DPLBG       TEXT,
                ROUTE       TEXT,
                SHTYP       TEXT,
                VSART       TEXT,
                TNDR_TRKID  TEXT,
                ROUTE_TNM   TEXT,
                SIGNI       TEXT,
                ZDORSE_NO   TEXT,
                SOFOR_ADI1  TEXT,
                SOFOR_ADI2  TEXT,
                NDURUM      TEXT,
                ADURUM      TEXT,
                FIDATUM     TEXT,
                SDATUM      TEXT,
                WADAT_IST   TEXT,
                VBELN       TEXT,
                ERDAT_LKP   TEXT,
                ERNAM_LKP   TEXT,
                KUNAG       TEXT,
                MUSTERI_ADI TEXT,
                KUNNR       TEXT,
                ISIM        TEXT,
                BEZEI       TEXT,
                CITY1       TEXT,
                POSNR       TEXT,
                MATNR       TEXT,
                MAKTX       TEXT,
                LFIMG       REAL,
                LGORT       TEXT,
                ZZTDEPO     TEXT,
                VGBEL       TEXT,
                UMVKZ       REAL,
                UMVKN       REAL,
                BSTKD       TEXT,
                TDURUM      TEXT,
                TDURUM_TNM  TEXT,
                VOLUM       REAL,
                VOLEH       TEXT,
                VSART_TNM   TEXT,

                UNIQUE(TKNUM, VBELN, POSNR)  -- aynı kayıt iki kez girmesin
            )
        """)

        # ── Entegrasyon bağlantı bilgileri ──────────────────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS integrations (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                name            TEXT NOT NULL UNIQUE,
                description     TEXT,
                service_type    TEXT DEFAULT 'SOAP',   -- SOAP | OData | RFC | CDS
                wsdl_url        TEXT,
                base_url        TEXT,
                service_method  TEXT,
                username        TEXT,
                password        TEXT,
                extra_params    TEXT,                  -- JSON blob (ek parametreler)
                is_active       INTEGER DEFAULT 1,
                created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ── Her entegrasyonun hedef tablo şeması ────────────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS integration_schemas (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                integration_id  INTEGER NOT NULL REFERENCES integrations(id),
                target_table    TEXT NOT NULL,
                schema_text     TEXT,                  -- LLM'e verilecek kolon açıklaması
                updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(integration_id, target_table)
            )
        """)

        # ── Qdrant point_id ↔ integration eşleme ───────────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS integration_vectors (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                integration_id    INTEGER NOT NULL REFERENCES integrations(id),
                qdrant_point_id   TEXT NOT NULL UNIQUE,
                chunk_text        TEXT,
                indexed_at        DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)



# def save_shipments(records: list):
#     if not records:
#         return

#     # 1. Beklenen SAP Kolonları Sırası (SQL'deki ? işaretleriyle birebir eşleşmeli)
#     expected_keys = [
#         "TKNUM", "VBELN", "POSNR", "ERDAT", "ERNAM", "DPLBG", "ROUTE", "ROUTE_TNM", "SHTYP", "VSART", 
#         "VSART_TNM", "TNDR_TRID", "SIGNI", "ZDORSE_NO", "SOFOR_ADI1", "SOFOR_ADI2", "NDURUM", 
#         "ADURUM", "FIDATUM", "SDATUM", "WADAT_IST", "ERDAT_LKP", "ERNAM_LKP", "KUNAG", "MUSTERI_ADI", 
#         "KUNNR", "ISIM", "BEZEI", "CITY1", "MATNR", "MAKTX", "LFIMG", "LGORT", "ZZTDEPO", "VGBEL", 
#         "UMVKZ", "UMVKN", "BSTKD", "TDURUM", "TDURUM_TNM", "VOLUM", "VOLEH"
#     ]
    
#     # 2. PyODBC dictionary anlamaz, verileri sıralı Tuple'lara çeviriyoruz
#     # SAP'den veri gelmemişse (eksikse) None atıyoruz
#     safe_tuples = []
#     for rec in records:
#         row_data = tuple(rec.get(key, None) for key in expected_keys)
#         safe_tuples.append(row_data)

#     # 3. MSSQL MERGE Sorgumuz (Key: TKNUM, VBELN, POSNR)
#     # ? işaretleri safe_tuples içindeki verilerle sırasıyla dolacak
#     merge_sql = """
#     MERGE shipments AS target
#     USING (VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?))
#     AS source (TKNUM, VBELN, POSNR, ERDAT, ERNAM, DPLBG, ROUTE, ROUTE_TNM, SHTYP, VSART, VSART_TNM, TNDR_TRID, SIGNI, ZDORSE_NO, SOFOR_ADI1, SOFOR_ADI2, NDURUM, ADURUM, FIDATUM, SDATUM, WADAT_IST, ERDAT_LKP, ERNAM_LKP, KUNAG, MUSTERI_ADI, KUNNR, ISIM, BEZEI, CITY1, MATNR, MAKTX, LFIMG, LGORT, ZZTDEPO, VGBEL, UMVKZ, UMVKN, BSTKD, TDURUM, TDURUM_TNM, VOLUM, VOLEH)
#     ON target.TKNUM = source.TKNUM AND target.VBELN = source.VBELN AND target.POSNR = source.POSNR
#     WHEN MATCHED THEN
#         UPDATE SET 
#             target.ERDAT = source.ERDAT, target.ERNAM = source.ERNAM, target.DPLBG = source.DPLBG, 
#             target.ROUTE = source.ROUTE, target.ROUTE_TNM = source.ROUTE_TNM, target.SHTYP = source.SHTYP, 
#             target.VSART = source.VSART, target.VSART_TNM = source.VSART_TNM, target.TNDR_TRID = source.TNDR_TRID, 
#             target.SIGNI = source.SIGNI, target.ZDORSE_NO = source.ZDORSE_NO, target.SOFOR_ADI1 = source.SOFOR_ADI1, 
#             target.SOFOR_ADI2 = source.SOFOR_ADI2, target.NDURUM = source.NDURUM, target.ADURUM = source.ADURUM, 
#             target.FIDATUM = source.FIDATUM, target.SDATUM = source.SDATUM, target.WADAT_IST = source.WADAT_IST, 
#             target.ERDAT_LKP = source.ERDAT_LKP, target.ERNAM_LKP = source.ERNAM_LKP, target.KUNAG = source.KUNAG, 
#             target.MUSTERI_ADI = source.MUSTERI_ADI, target.KUNNR = source.KUNNR, target.ISIM = source.ISIM, 
#             target.BEZEI = source.BEZEI, target.CITY1 = source.CITY1, target.MATNR = source.MATNR, 
#             target.MAKTX = source.MAKTX, target.LFIMG = source.LFIMG, target.LGORT = source.LGORT, 
#             target.ZZTDEPO = source.ZZTDEPO, target.VGBEL = source.VGBEL, target.UMVKZ = source.UMVKZ, 
#             target.UMVKN = source.UMVKN, target.BSTKD = source.BSTKD, target.TDURUM = source.TDURUM, 
#             target.TDURUM_TNM = source.TDURUM_TNM, target.VOLUM = source.VOLUM, target.VOLEH = source.VOLEH,
#             target.fetched_at = CURRENT_TIMESTAMP
#     WHEN NOT MATCHED THEN
#         INSERT (TKNUM, VBELN, POSNR, ERDAT, ERNAM, DPLBG, ROUTE, ROUTE_TNM, SHTYP, VSART, VSART_TNM, TNDR_TRID, SIGNI, ZDORSE_NO, SOFOR_ADI1, SOFOR_ADI2, NDURUM, ADURUM, FIDATUM, SDATUM, WADAT_IST, ERDAT_LKP, ERNAM_LKP, KUNAG, MUSTERI_ADI, KUNNR, ISIM, BEZEI, CITY1, MATNR, MAKTX, LFIMG, LGORT, ZZTDEPO, VGBEL, UMVKZ, UMVKN, BSTKD, TDURUM, TDURUM_TNM, VOLUM, VOLEH)
#         VALUES (source.TKNUM, source.VBELN, source.POSNR, source.ERDAT, source.ERNAM, source.DPLBG, source.ROUTE, source.ROUTE_TNM, source.SHTYP, source.VSART, source.VSART_TNM, source.TNDR_TRID, source.SIGNI, source.ZDORSE_NO, source.SOFOR_ADI1, source.SOFOR_ADI2, source.NDURUM, source.ADURUM, source.FIDATUM, source.SDATUM, source.WADAT_IST, source.ERDAT_LKP, source.ERNAM_LKP, source.KUNAG, source.MUSTERI_ADI, source.KUNNR, source.ISIM, source.BEZEI, source.CITY1, source.MATNR, source.MAKTX, source.LFIMG, source.LGORT, source.ZZTDEPO, source.VGBEL, source.UMVKZ, source.UMVKN, source.BSTKD, source.TDURUM, source.TDURUM_TNM, source.VOLUM, source.VOLEH);
#     """

#     # 4. Veritabanına Bağlan ve Veriyi Bas
#     try:
#         conn = pyodbc.connect(CONN_STR)
#         cursor = conn.cursor()
        
#         # fast_executemany, SQL Server'da binlerce satırı saniyeler içinde yazmanı sağlar. Çok kritiktir!
#         cursor.fast_executemany = True 
        
#         cursor.executemany(merge_sql, safe_tuples)
#         conn.commit()
#         print(f"[DB] MSSQL'e işlem başarılı! Eşleşenler güncellendi, yeniler eklendi. Toplam satır: {len(safe_tuples)}")
#     except Exception as e:
#         print(f"[DB HATA] Kayıt sırasında sorun oluştu: {e}")
#     finally:
#         # Hata olsa bile bağlantıyı güvenle kapatırız
#         if 'conn' in locals():
#             conn.close()

# from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

# def _safe_decimal(val, precision="0.001"):
#     if val is None:
#         return None
#     try:
#         return Decimal(str(val)).quantize(Decimal(precision), rounding=ROUND_HALF_UP)
#     except (InvalidOperation, TypeError):
#         return None

from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
def _safe_float(val):
    if val is None or val == "":
        return None
    try:
        return round(float(str(val)), 3)
    except (ValueError, TypeError):
        return None

def _safe_int(val):
    if val is None or val == "":
        return None
    try:
        return int(float(str(val)))
    except (ValueError, TypeError):
        return None

def _safe_date(val):
    if val is None or val == "" or val == "00000000" or val == "0000-00-00":
        return None
    try:
        val = str(val).strip()
        if len(val) == 8 and val.isdigit():
            return f"{val[:4]}-{val[4:6]}-{val[6:8]}"
        # YYYY-MM-DD formatı ama yıl 0000 ise None döndür
        if val.startswith("0000"):
            return None
        return val
    except Exception:
        return None

def _safe_str(val):
    """Boş stringleri None'a çevirir."""
    if val is None or val == "":
        return None
    return str(val).strip()

FLOAT_KEYS = {"LFIMG", "VOLUM"}
INT_KEYS   = {"UMVKZ", "UMVKN"}
DATE_KEYS  = {"ERDAT", "DPLBG", "FIDATUM", "SDATUM", "WADAT_IST", "ERDAT_LKP"}

def save_shipments(records: list):
    if not records:
        return

    expected_keys = [
        "TKNUM", "VBELN", "POSNR", "ERDAT", "ERNAM", "DPLBG", "ROUTE", "ROUTE_TNM", "SHTYP", "VSART",
        "VSART_TNM", "TNDR_TRKID", "SIGNI", "ZDORSE_NO", "SOFOR_ADI1", "SOFOR_ADI2", "NDURUM",
        "ADURUM", "FIDATUM", "SDATUM", "WADAT_IST", "ERDAT_LKP", "ERNAM_LKP", "KUNAG", "MUSTERI_ADI",
        "KUNNR", "ISIM", "BEZEI", "CITY1", "MATNR", "MAKTX", "LFIMG", "LGORT", "ZZTDEPO", "VGBEL",
        "UMVKZ", "UMVKN", "BSTKD", "TDURUM", "TDURUM_TNM", "VOLUM", "VOLEH"
    ]

    safe_tuples = []
    for rec in records:
        row_data = tuple(
            _safe_float(rec.get(key))  if key in FLOAT_KEYS
            else _safe_int(rec.get(key))   if key in INT_KEYS
            else _safe_date(rec.get(key))  if key in DATE_KEYS
            else _safe_str(rec.get(key))
            for key in expected_keys
        )
        safe_tuples.append(row_data)

    merge_sql = """
    MERGE shipments AS target
    USING (VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?))
    AS source (TKNUM, VBELN, POSNR, ERDAT, ERNAM, DPLBG, ROUTE, ROUTE_TNM, SHTYP, VSART, VSART_TNM, TNDR_TRKID, SIGNI, ZDORSE_NO, SOFOR_ADI1, SOFOR_ADI2, NDURUM, ADURUM, FIDATUM, SDATUM, WADAT_IST, ERDAT_LKP, ERNAM_LKP, KUNAG, MUSTERI_ADI, KUNNR, ISIM, BEZEI, CITY1, MATNR, MAKTX, LFIMG, LGORT, ZZTDEPO, VGBEL, UMVKZ, UMVKN, BSTKD, TDURUM, TDURUM_TNM, VOLUM, VOLEH)
    ON target.TKNUM = source.TKNUM AND target.VBELN = source.VBELN AND target.POSNR = source.POSNR
    WHEN MATCHED THEN
        UPDATE SET
            target.ERDAT = source.ERDAT, target.ERNAM = source.ERNAM, target.DPLBG = source.DPLBG,
            target.ROUTE = source.ROUTE, target.ROUTE_TNM = source.ROUTE_TNM, target.SHTYP = source.SHTYP,
            target.VSART = source.VSART, target.VSART_TNM = source.VSART_TNM, target.TNDR_TRKID = source.TNDR_TRKID,
            target.SIGNI = source.SIGNI, target.ZDORSE_NO = source.ZDORSE_NO, target.SOFOR_ADI1 = source.SOFOR_ADI1,
            target.SOFOR_ADI2 = source.SOFOR_ADI2, target.NDURUM = source.NDURUM, target.ADURUM = source.ADURUM,
            target.FIDATUM = source.FIDATUM, target.SDATUM = source.SDATUM, target.WADAT_IST = source.WADAT_IST,
            target.ERDAT_LKP = source.ERDAT_LKP, target.ERNAM_LKP = source.ERNAM_LKP, target.KUNAG = source.KUNAG,
            target.MUSTERI_ADI = source.MUSTERI_ADI, target.KUNNR = source.KUNNR, target.ISIM = source.ISIM,
            target.BEZEI = source.BEZEI, target.CITY1 = source.CITY1, target.MATNR = source.MATNR,
            target.MAKTX = source.MAKTX, target.LFIMG = source.LFIMG, target.LGORT = source.LGORT,
            target.ZZTDEPO = source.ZZTDEPO, target.VGBEL = source.VGBEL, target.UMVKZ = source.UMVKZ,
            target.UMVKN = source.UMVKN, target.BSTKD = source.BSTKD, target.TDURUM = source.TDURUM,
            target.TDURUM_TNM = source.TDURUM_TNM, target.VOLUM = source.VOLUM, target.VOLEH = source.VOLEH,
            target.fetched_at = CURRENT_TIMESTAMP
    WHEN NOT MATCHED THEN
        INSERT (TKNUM, VBELN, POSNR, ERDAT, ERNAM, DPLBG, ROUTE, ROUTE_TNM, SHTYP, VSART, VSART_TNM, TNDR_TRKID, SIGNI, ZDORSE_NO, SOFOR_ADI1, SOFOR_ADI2, NDURUM, ADURUM, FIDATUM, SDATUM, WADAT_IST, ERDAT_LKP, ERNAM_LKP, KUNAG, MUSTERI_ADI, KUNNR, ISIM, BEZEI, CITY1, MATNR, MAKTX, LFIMG, LGORT, ZZTDEPO, VGBEL, UMVKZ, UMVKN, BSTKD, TDURUM, TDURUM_TNM, VOLUM, VOLEH)
        VALUES (source.TKNUM, source.VBELN, source.POSNR, source.ERDAT, source.ERNAM, source.DPLBG, source.ROUTE, source.ROUTE_TNM, source.SHTYP, source.VSART, source.VSART_TNM, source.TNDR_TRKID, source.SIGNI, source.ZDORSE_NO, source.SOFOR_ADI1, source.SOFOR_ADI2, source.NDURUM, source.ADURUM, source.FIDATUM, source.SDATUM, source.WADAT_IST, source.ERDAT_LKP, source.ERNAM_LKP, source.KUNAG, source.MUSTERI_ADI, source.KUNNR, source.ISIM, source.BEZEI, source.CITY1, source.MATNR, source.MAKTX, source.LFIMG, source.LGORT, source.ZZTDEPO, source.VGBEL, source.UMVKZ, source.UMVKN, source.BSTKD, source.TDURUM, source.TDURUM_TNM, source.VOLUM, source.VOLEH);
    """

    try:
        conn = pyodbc.connect(CONN_STR)
        cursor = conn.cursor()
        cursor.fast_executemany = True
        cursor.executemany(merge_sql, safe_tuples)
        conn.commit()
        print(f"[DB] MSSQL'e işlem başarılı! Toplam satır: {len(safe_tuples)}")
    except Exception as e:
        print(f"[DB HATA] Kayıt sırasında sorun oluştu: {e}")
        # Hangi satırda patlıyor görmek için:
        for i, tup in enumerate(safe_tuples):
            try:
                cursor2 = conn.cursor()
                cursor2.execute(merge_sql, tup)
            except Exception as row_err:
                print(f"  → Satır {i} hata: {row_err}")
                print(f"  → Veri: {tup}")
                break
    finally:
        if 'conn' in locals():
            conn.close()