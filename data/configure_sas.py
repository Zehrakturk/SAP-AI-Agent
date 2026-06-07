"""
data/configure_sas.py — SAS Servisi (integration id=7) tam yapılandırması.

WSDL: ZAI_RFC_FG001_002 (Beyçelik SAP — endpoint .env'den: SAP_SAS_WSDL_URL)
  Girdi (4, hepsi opsiyonel): IV_FISCPER, IV_MATERIAL, IV_PLANT, IV_VENDOR
  Dönüş: ET_RETURN (tablo) + EV_COUNT + EV_MESSAGE + EV_SUCCESS
  ET_RETURN satır kolonları: REQTSN, DATAPAKID, RECORD, RECORDMODE, FISCPER,
    _-BIC_-ZBPRME, _-BIC_-ZTERM, FISCVARNT, PLANT, MATERIAL, VENDOR,
    AMOUNT, PRICE_UNIT, PRICE, CURRENCY

Kullanım:
    cd SAP-AI
    python data/configure_sas.py

Idempotent: tekrar çalıştırılabilir. Mevcut kullanıcı adı/şifre KORUNUR (üzerine yazmaz)
— Beyçelik SAP kimlik bilgilerini Entegrasyonlar ekranından siz girmelisiniz.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import io
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
except Exception:
    pass

import pyodbc
from dotenv import load_dotenv
load_dotenv()

INTEGRATION_ID  = 7
SERVICE_METHOD  = "ZAI_RFC_FG001_002"
# İç SAP hostname'i KODA GÖMÜLÜ DEĞİL — .env'den okunur (public repo güvenliği).
# .env: SAP_SAS_ENDPOINT=http://<sap-host>:8000/sap/bc/srt/rfc/sap/.../zai_rfc_fg001_002_ws
ENDPOINT        = os.getenv("SAP_SAS_ENDPOINT",
                            "http://your-sap-host:8000/sap/bc/srt/rfc/sap/"
                            "zai_rfc_fg001_002/100/zai_rfc_fg001_002/zai_rfc_fg001_002_ws")
WSDL_URL        = os.getenv("SAP_SAS_WSDL_URL", ENDPOINT + "?wsdl")
TARGET_TABLE    = "sas_data"

# Girdi parametreleri (WSDL: hepsi minOccurs=0 → opsiyonel)
PARAMS = [
    ("IV_FISCPER",  "numeric7", "Mali yıl/dönem. Bir YIL belirtilirse 4 haneli yılı yaz "
                                "(örn. 2023); sistem otomatik 2023001 yapar (yıllık veri 001 döneminde)."),
    ("IV_MATERIAL", "char40",   "Malzeme numarası"),
    ("IV_PLANT",    "char4",    "Üretim yeri"),
    ("IV_VENDOR",   "char10",   "Satıcının hesap numarası"),
]

SCHEMA_TEXT = """Tablo: sas_data (Entegrasyon: SAS Servisi — Beyçelik)
Açıklama: SAP BW'den ZAI_RFC_FG001_002 fonksiyonuyla çekilen satınalma/malzeme
fiyat ve tutar verileri. Her satır bir malzeme-satıcı-dönem-üretim yeri kombinasyonudur.
CEVAPLARDA teknik kolon adlarını DEĞİL, aşağıdaki TÜRKÇE İŞ TERİMLERİNİ kullan.

Kolon → Türkçe terim:
- FISCPER        → Mali yıl / dönem (7 hane YYYYPPP, örn. 2023001 = 2023 mali yılı 1. dönem)
- FISCVARNT      → Mali yıl varyantı
- PLANT          → Üretim yeri
- MATERIAL       → Malzeme (malzeme kodu)
- VENDOR         → Satıcı (tedarikçi)
- AMOUNT         → Tutar (toplam alış tutarı, CURRENCY para biriminde)
- PRICE          → Birim fiyat (zaten veride var, hesaplama gerekmez)
- PRICE_UNIT     → Fiyat birimi (kaç birim için)
- CURRENCY       → Para birimi (örn. TRY)
- __BIC__ZTERM   → Ödeme koşulu (gün)
- __BIC__ZBPRME  → Temel ölçü birimi
- REQTSN, DATAPAKID, RECORD, RECORDMODE → BW teknik alanları (cevapta kullanma)

Örnek sorular: 'bir malzemenin satıcıya göre fiyatı', 'üretim yerine göre toplam
satınalma tutarı', 'dönem bazında fiyat'."""


def _connect(retries: int = 4):
    cs = (f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={os.getenv('DB_SERVER')};"
          f"DATABASE={os.getenv('DB_NAME')};UID={os.getenv('DB_USER')};"
          f"PWD={os.getenv('DB_PASS')};TrustServerCertificate=yes;Encrypt=yes;"
          f"Connection Timeout=10;")
    last = None
    for i in range(retries):
        try:
            return pyodbc.connect(cs, timeout=10)
        except Exception as e:
            last = e
            print(f"  [DB] bağlantı denemesi {i+1}/{retries} başarısız, 5 sn bekleniyor...")
            time.sleep(5)
    raise SystemExit(f"DB'ye bağlanılamadı (sunucu erişilemiyor olabilir): {last}")


def main():
    conn = _connect()
    cur  = conn.cursor()

    # 1) integrations satırını güncelle (kimlik bilgileri KORUNUR)
    cur.execute("SELECT name, service_type, service_method, wsdl_url, username "
                "FROM integrations WHERE id = ?", (INTEGRATION_ID,))
    row = cur.fetchone()
    if not row:
        raise SystemExit(f"integration id={INTEGRATION_ID} bulunamadı.")
    print(f"Entegrasyon: {row[0]} (mevcut method={row[2]!r}, user={row[4]!r})")

    # wsdl_url'i YALNIZ env'den açıkça verilmişse güncelle — aksi halde mevcut (çalışan)
    # DB değerini KORU (placeholder ile bozma).
    _env_wsdl = os.getenv("SAP_SAS_WSDL_URL") or os.getenv("SAP_SAS_ENDPOINT")
    if _env_wsdl:
        cur.execute("""
            UPDATE integrations
            SET service_type='SOAP', service_method=?, wsdl_url=?, company='Beycelik', is_active=1
            WHERE id=?
        """, (SERVICE_METHOD, WSDL_URL, INTEGRATION_ID))
        print(f"  ✓ service_type=SOAP, method={SERVICE_METHOD}, wsdl_url ayarlandı (.env'den), aktif")
    else:
        cur.execute("""
            UPDATE integrations
            SET service_type='SOAP', service_method=?, company='Beycelik', is_active=1
            WHERE id=?
        """, (SERVICE_METHOD, INTEGRATION_ID))
        print(f"  ✓ service_type=SOAP, method={SERVICE_METHOD}, aktif "
              f"(wsdl_url DOKUNULMADI — .env'de SAP_SAS_WSDL_URL yok)")

    # extra_config.live_query = true → bu entegrasyon SQL'e YAZILMAZ, anlık sorgulanır
    import json as _json
    if cur.execute("SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS "
                   "WHERE TABLE_NAME='integrations' AND COLUMN_NAME='extra_config'").fetchone():
        cur.execute("SELECT extra_config FROM integrations WHERE id=?", (INTEGRATION_ID,))
        _raw = cur.fetchone()[0]
        _cfg = _json.loads(_raw) if _raw else {}
        _cfg["live_query"] = True
        # Yönlendirme anahtar kelimeleri (satınalma alanı — Press üretim terimleriyle çakışmaz)
        _cfg["keywords"] = [
            "satinalma", "satin alma", "alis", "alis tutar", "alinan", "tedarik",
            "tedarikci", "satici", "vendor", "malzeme fiyat", "malzeme alis",
            "birim fiyat", "fiyat", "tutar", "mali yil", "mali yıl",
            "purchas", "amount", "price", "sas servisi", "sas",
        ]
        cur.execute("UPDATE integrations SET extra_config=? WHERE id=?",
                    (_json.dumps(_cfg, ensure_ascii=False), INTEGRATION_ID))
        print("  ✓ extra_config.live_query=true + yönlendirme keywords (anlık sorgu)")

    # auth_type kolonu varsa BASIC yap
    if cur.execute("SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS "
                   "WHERE TABLE_NAME='integrations' AND COLUMN_NAME='auth_type'").fetchone():
        cur.execute("UPDATE integrations SET auth_type='BASIC' WHERE id=? AND (auth_type IS NULL OR auth_type='')",
                    (INTEGRATION_ID,))

    # 2) Girdi parametreleri (idempotent)
    cur.execute("SELECT param_name FROM integration_params WHERE integration_id=?", (INTEGRATION_ID,))
    mevcut = {r[0].upper() for r in cur.fetchall()}
    for name, ptype, desc in PARAMS:
        if name.upper() in mevcut:
            print(f"  = param var: {name}")
            continue
        cur.execute("""INSERT INTO integration_params
            (integration_id, param_name, param_type, is_required, default_value, description)
            VALUES (?,?,?,0,'',?)""", (INTEGRATION_ID, name, ptype, desc))
        print(f"  + param eklendi: {name} ({ptype})")

    # 3) Şema (target_table + schema_text) — upsert
    cur.execute("SELECT 1 FROM integration_schemas WHERE integration_id=?", (INTEGRATION_ID,))
    if cur.fetchone():
        cur.execute("UPDATE integration_schemas SET target_table=?, schema_text=?, updated_at=GETDATE() "
                    "WHERE integration_id=?", (TARGET_TABLE, SCHEMA_TEXT, INTEGRATION_ID))
        print(f"  ✓ şema güncellendi (target_table={TARGET_TABLE})")
    else:
        cur.execute("INSERT INTO integration_schemas (integration_id, target_table, schema_text) "
                    "VALUES (?,?,?)", (INTEGRATION_ID, TARGET_TABLE, SCHEMA_TEXT))
        print(f"  ✓ şema oluşturuldu (target_table={TARGET_TABLE})")

    conn.commit()

    # Özet
    cur.execute("SELECT name, service_type, service_method, wsdl_url, is_active, company "
                "FROM integrations WHERE id=?", (INTEGRATION_ID,))
    r = cur.fetchone()
    print("\n=== SON DURUM ===")
    print(f"  {r[0]} | {r[1]} | {r[2]} | aktif={r[4]} | {r[5]}")
    print(f"  wsdl_url: {r[3]}")
    cur.execute("SELECT param_name, param_type FROM integration_params WHERE integration_id=? ORDER BY id",
                (INTEGRATION_ID,))
    print("  parametreler:", [f"{p[0]}({p[1]})" for p in cur.fetchall()])
    conn.close()
    print("\n✓ SAS yapılandırması tamam. Beyçelik SAP kullanıcı adı/şifresini Entegrasyonlar")
    print("  ekranından girip 'Veri Çek' ile test edebilirsiniz (ardından indeksleyin).")


if __name__ == "__main__":
    main()
