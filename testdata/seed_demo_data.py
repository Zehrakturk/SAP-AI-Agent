# -*- coding: utf-8 -*-
"""
testdata/seed_demo_data.py — DEMO / TEST sistemi için SENTETİK veri üretir.

Amaç: Tezde ekran görüntüsü almak için, kurumun GERÇEK verisi yerine tamamen
uydurma (ama gerçekçi) sevkiyat ve satınalma verisi içeren bir demo ortam kurmak.

GÜVENLİK:
  - Bu script .env'deki DB_NAME veritabanına yazar. GERÇEK üretim veritabanına
    ASLA çalıştırmayın. Ayrı bir demo veritabanı kullanın (örn. DB_NAME=SAPAI_DEMO).
  - Çalıştırmak için açıkça onay gerekir:  python testdata/seed_demo_data.py --yes

Kullanım:
    1) Ayrı bir demo DB oluşturun ve .env'de DB_NAME'i ona çevirin.
    2) cd SAP-AI
    3) python testdata/seed_demo_data.py --yes
    4) (gerekirse) Qdrant indeksleme otomatik denenir; OpenAI/Qdrant kapalıysa atlanır.
    5) Uygulamayı başlatın, "demo / demo123" ile giriş yapın (firma: Demo).
"""

import os
import sys
import random
import datetime as dt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import io
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
except Exception:
    pass

from dotenv import load_dotenv
load_dotenv()

from app.services.db import get_connection

random.seed(42)
DEMO_COMPANY = "Demo"
PARAM_HASH   = "demo"
TODAY        = dt.date(2026, 6, 14)
# Sevkiyat verisi bu tarihten bugüne yayılır → Ocak–Haziran 2026 tüm aylar kapsanır
# (Mart/Nisan gibi geçmiş ay karşılaştırmaları için yeterli geçmiş olur).
SHIP_START   = dt.date(2026, 1, 1)
SHIP_SPAN    = (TODAY - SHIP_START).days  # ~165 gün

# ───────────────────────── sentetik sözlükler (hepsi UYDURMA) ─────────────────────────
CITIES    = ["İstanbul", "Ankara", "İzmir", "Bursa", "Kocaeli", "Gebze",
             "Adana", "Konya", "Gaziantep", "Manisa", "Eskişehir", "Tekirdağ"]
CUSTOMERS = [
    ("D100001", "Demo Otomotiv Sanayi A.Ş."), ("D100002", "Anadolu Makine Ltd. Şti."),
    ("D100003", "Ege Plastik San. ve Tic."),  ("D100004", "Marmara Lojistik A.Ş."),
    ("D100005", "Toros Metal İşleme A.Ş."),    ("D100006", "Başak Mühendislik Ltd."),
    ("D100007", "Yıldız Beyaz Eşya San."),     ("D100008", "Deniz Kablo ve Tel A.Ş."),
    ("D100009", "Akın Kalıp Teknolojileri"),   ("D100010", "Pınar Gıda Ambalaj A.Ş."),
]
MATERIALS = [
    ("DM-SAC-1001", "Demo Soğuk Haddelenmiş Sac"), ("DM-CONTA-2003", "Demo Kauçuk Conta"),
    ("DM-CIVATA-3007", "Demo Paslanmaz Cıvata M8"), ("DM-PROFIL-4002", "Demo Alüminyum Profil"),
    ("DM-RULMAN-5005", "Demo Bilyalı Rulman"),      ("DM-KABLO-6008", "Demo Bakır Kablo 2.5mm"),
    ("DM-BORU-7001", "Demo Çelik Boru DN50"),       ("DM-PLASTIK-8004", "Demo Enjeksiyon Parça"),
]
DRIVERS   = ["Ahmet Yılmaz", "Mehmet Demir", "Hasan Kaya", "Mustafa Çelik",
             "Ali Şahin", "Hüseyin Aydın", "İbrahim Korkmaz", "Osman Arslan"]
VSART     = [("01", "Karayolu"), ("02", "Denizyolu"), ("03", "Havayolu")]
TDURUM    = [("01", "OLUŞTURULDU"), ("02", "MAL ÇIKIŞI YAPILDI"),
             ("03", "YOLDA"), ("04", "TESLİM EDİLDİ")]
VENDORS   = [
    ("V900001", "Demo Çelik Tedarik A.Ş."),  ("V900002", "Anadolu Hammadde Ltd."),
    ("V900003", "Marmara Metal Tic. A.Ş."),  ("V900004", "Ege Kimya San. ve Tic."),
    ("V900005", "Yıldırım Bağlantı Elemanları"), ("V900006", "Deniz Kablo Üretim A.Ş."),
]
PLANTS    = ["1000", "2000", "3000"]

SAS_SCHEMA_TEXT = (
    "Tablo: sas_data_demo (Satinalma Servisi - Demo). Demo amacli sentetik "
    "satinalma/malzeme fiyat ve tutar verileri (gercek veri DEGILDIR).\n"
    "SQL YAZARKEN SADECE su gercek kolon adlarini kullan (asagidaki Turkce "
    "terimleri ASLA kolon adi olarak SQL'e yazma): FISCPER, FISCVARNT, PLANT, "
    "MATERIAL, MAKTX, VENDOR, SATICI_ADI, AMOUNT, PRICE, PRICE_UNIT, CURRENCY, "
    "ZTERM, ZBPRME.\n"
    "Kolonlarin anlami (bu Turkce terimleri YALNIZCA cevap metninde kullan, "
    "SQL'de degil): FISCPER = mali yil/donem (7 hane YYYYPPP, orn 2023001 = 2023 "
    "mali yili); FISCVARNT = mali yil varyanti; PLANT = uretim yeri; "
    "MATERIAL = malzeme kodu; MAKTX = malzeme aciklamasi; VENDOR = satici kodu; "
    "SATICI_ADI = satici adi (kullaniciya saticiyi kodla degil bu adla goster); "
    "AMOUNT = tutar (toplam alis tutari, CURRENCY biriminde); PRICE = birim fiyat; "
    "PRICE_UNIT = fiyat birimi (kac birim icin); CURRENCY = para birimi; "
    "ZTERM = odeme kosulu (gun); ZBPRME = temel olcu birimi.\n"
    "NOTLAR: Birim fiyat dogrudan PRICE kolonudur (hesaplama gerekmez). "
    "Mali yil/donem filtresi icin FISCPER kolonunu kullan; FISCPER bir TARIH "
    "DEGILDIR, tarih araligi ile filtreleme. Orn 2023 mali yili: "
    "WHERE FISCPER LIKE '2023%'."
)

# shipments tablosunun tam kolon kümesi (setup_db şema metniyle uyumlu)
SHIP_COLS = [
    ("TKNUM","NVARCHAR(20)"),("ERDAT","NVARCHAR(10)"),("ERNAM","NVARCHAR(50)"),
    ("DPLBG","NVARCHAR(10)"),("ROUTE","NVARCHAR(20)"),("ROUTE_TNM","NVARCHAR(100)"),
    ("SHTYP","NVARCHAR(10)"),("VSART","NVARCHAR(10)"),("VSART_TNM","NVARCHAR(50)"),
    ("TNDR_TRKID","NVARCHAR(40)"),("SIGNI","NVARCHAR(30)"),("ZDORSE_NO","NVARCHAR(30)"),
    ("SOFOR_ADI1","NVARCHAR(80)"),("SOFOR_ADI2","NVARCHAR(80)"),("NDURUM","NVARCHAR(10)"),
    ("ADURUM","NVARCHAR(10)"),("FIDATUM","NVARCHAR(10)"),("SDATUM","NVARCHAR(10)"),
    ("WADAT_IST","NVARCHAR(10)"),("VBELN","NVARCHAR(20)"),("ERDAT_LKP","NVARCHAR(10)"),
    ("ERNAM_LKP","NVARCHAR(50)"),("KUNAG","NVARCHAR(20)"),("MUSTERI_ADI","NVARCHAR(120)"),
    ("KUNNR","NVARCHAR(20)"),("ISIM","NVARCHAR(120)"),("BEZEI","NVARCHAR(120)"),
    ("CITY1","NVARCHAR(60)"),("POSNR","NVARCHAR(10)"),("MATNR","NVARCHAR(30)"),
    ("MAKTX","NVARCHAR(120)"),("LFIMG","FLOAT"),("LGORT","NVARCHAR(10)"),
    ("ZZTDEPO","NVARCHAR(10)"),("VGBEL","NVARCHAR(20)"),("UMVKZ","INT"),("UMVKN","INT"),
    ("BSTKD","NVARCHAR(40)"),("TDURUM","NVARCHAR(10)"),("TDURUM_TNM","NVARCHAR(50)"),
    ("VOLUM","FLOAT"),("VOLEH","NVARCHAR(10)"),
]
SAS_COLS = [
    ("FISCPER","NVARCHAR(10)"),("FISCVARNT","NVARCHAR(4)"),("PLANT","NVARCHAR(6)"),
    ("MATERIAL","NVARCHAR(40)"),("MAKTX","NVARCHAR(120)"),("VENDOR","NVARCHAR(20)"),
    ("SATICI_ADI","NVARCHAR(120)"),("AMOUNT","FLOAT"),("PRICE","FLOAT"),
    ("PRICE_UNIT","INT"),("CURRENCY","NVARCHAR(5)"),("ZTERM","NVARCHAR(10)"),
    ("ZBPRME","NVARCHAR(10)"),
]


def _create_data_table(cur, name, cols):
    coldefs = ",\n        ".join(f"[{c}] {t}" for c, t in cols)
    cur.execute(f"""
        IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = '{name}')
        CREATE TABLE [{name}] (
            id INT IDENTITY(1,1) PRIMARY KEY,
            fetched_at DATETIME DEFAULT GETDATE(),
            param_hash NVARCHAR(20) NULL,
            integration_id INT NULL,
            {coldefs}
        )
    """)


def _ensure_integration_columns(cur):
    """Eski integrations şemasına eksik kolonları idempotent ekle."""
    cur.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='integrations'")
    have = {r[0].upper() for r in cur.fetchall()}
    for col, ddl in {
        "COMPANY":      "company NVARCHAR(100) NULL",
        "SERVICE_TYPE": "service_type NVARCHAR(20) NULL",
        "EXTRA_CONFIG": "extra_config NVARCHAR(MAX) NULL",
        "AUTH_TYPE":    "auth_type NVARCHAR(20) NULL",
    }.items():
        if col not in have:
            cur.execute(f"ALTER TABLE integrations ADD {ddl}")


def _cleanup_demo(cur):
    """Onceki demo entegrasyonlarini + bagli kayitlari + demo veri satirlarini sil.
    Idempotent: tekrar calistirmada CIFT KAYIT olusmasini onler (firma='Demo' kapsamli)."""
    cur.execute("SELECT id FROM integrations WHERE company=?", (DEMO_COMPANY,))
    ids = [r[0] for r in cur.fetchall()]
    if ids:
        ph = ",".join("?" * len(ids))
        for tbl in ("integration_params", "integration_schemas", "integration_vectors"):
            try:
                cur.execute(f"DELETE FROM {tbl} WHERE integration_id IN ({ph})", ids)
            except Exception:
                pass
        cur.execute(f"DELETE FROM integrations WHERE id IN ({ph})", ids)
    # demo veri tablolari yalniz demo verisi tutar → tum satirlari temizle
    for t in ("shipments_demo", "sas_data_demo"):
        try:
            cur.execute(f"IF OBJECT_ID('{t}','U') IS NOT NULL DELETE FROM [{t}]")
        except Exception:
            pass


def _seed_integration(cur, name, desc, target_table, schema_text, params, service_type="SOAP"):
    cur.execute("SELECT id FROM integrations WHERE name=?", (name,))
    row = cur.fetchone()
    if row:
        int_id = row[0]
        cur.execute("UPDATE integrations SET description=?, company=?, service_type=?, is_active=1 WHERE id=?",
                    (desc, DEMO_COMPANY, service_type, int_id))
    else:
        cur.execute("""INSERT INTO integrations (name, description, company, service_type, is_active)
                       OUTPUT INSERTED.id VALUES (?,?,?,?,1)""",
                    (name, desc, DEMO_COMPANY, service_type))
        int_id = cur.fetchone()[0]

    # şema (upsert)
    cur.execute("SELECT id FROM integration_schemas WHERE integration_id=? AND target_table=?",
                (int_id, target_table))
    s = cur.fetchone()
    if s:
        cur.execute("UPDATE integration_schemas SET schema_text=?, updated_at=GETDATE() WHERE id=?",
                    (schema_text, s[0]))
    else:
        cur.execute("INSERT INTO integration_schemas (integration_id, schema_text, target_table) VALUES (?,?,?)",
                    (int_id, schema_text, target_table))

    # parametreler
    for p_name, p_type, desc_p in params:
        cur.execute("SELECT id FROM integration_params WHERE integration_id=? AND param_name=?",
                    (int_id, p_name))
        if not cur.fetchone():
            cur.execute("""INSERT INTO integration_params
                (integration_id, param_name, param_type, is_required, default_value, description)
                VALUES (?,?,?,0,'',?)""", (int_id, p_name, p_type, desc_p))
    return int_id


def _insert_rows(cur, table, int_id, rows):
    if not rows:
        return
    cur.execute(f"DELETE FROM [{table}] WHERE integration_id=?", (int_id,))  # idempotent
    keys = list(rows[0].keys())
    cols = keys + ["integration_id", "param_hash"]
    ph   = ",".join("?" * len(cols))
    sql  = f"INSERT INTO [{table}] ([{'],['.join(cols)}]) VALUES ({ph})"
    data = [tuple(r[k] for k in keys) + (int_id, PARAM_HASH) for r in rows]
    cur.executemany(sql, data)


def gen_shipments(n_shipments=340):
    rows = []
    for i in range(n_shipments):
        tknum = f"009{i:07d}"
        d = SHIP_START + dt.timedelta(days=random.randint(0, SHIP_SPAN))
        erdat = d.isoformat()
        wadat = (d + dt.timedelta(days=random.randint(1, 6))).isoformat()
        kun, mus = random.choice(CUSTOMERS)
        city = random.choice(CITIES)
        vs, vsn = random.choice(VSART)
        td, tdn = random.choice(TDURUM)
        sofor = random.choice(DRIVERS)
        plaka = f"{random.randint(1,81):02d} {random.choice('DEFGHK')}{random.choice('RSTVY')} {random.randint(100,9999)}"
        for pos in range(1, random.randint(1, 4)):
            mat, matx = random.choice(MATERIALS)
            rows.append({
                "TKNUM": tknum, "ERDAT": erdat, "ERNAM": "DEMO_USER",
                "ROUTE": f"R{random.randint(10,99)}", "ROUTE_TNM": f"{city} Rotası",
                "VSART": vs, "VSART_TNM": vsn, "SIGNI": plaka,
                "SOFOR_ADI1": sofor, "SDATUM": wadat, "WADAT_IST": wadat,
                "VBELN": f"80{i:07d}", "KUNAG": kun, "MUSTERI_ADI": mus,
                "KUNNR": kun, "ISIM": mus, "CITY1": city, "POSNR": f"{pos*10:06d}",
                "MATNR": mat, "MAKTX": matx, "LFIMG": float(random.randint(5, 800)),
                "LGORT": random.choice(["1000","2000"]),
                "BSTKD": f"PO-{random.randint(10000,99999)}",
                "TDURUM": td, "TDURUM_TNM": tdn,
                "VOLUM": round(random.uniform(0.5, 40.0), 2), "VOLEH": "M3",
            })
    return rows


def gen_sas(n=180):
    rows = []
    periods = ["2023001", "2024001", "2025001"]
    for _ in range(n):
        mat, matx = random.choice(MATERIALS)
        ven, vad = random.choice(VENDORS)
        price = round(random.uniform(40, 1800), 2)
        qty   = random.randint(10, 500)
        rows.append({
            "FISCPER": random.choice(periods), "FISCVARNT": "K4",
            "PLANT": random.choice(PLANTS), "MATERIAL": mat, "MAKTX": matx,
            "VENDOR": ven, "SATICI_ADI": vad,
            "AMOUNT": round(price * qty, 2), "PRICE": price,
            "PRICE_UNIT": 1, "CURRENCY": "TRY",
            "ZTERM": random.choice(["30", "45", "60", "90"]),
            "ZBPRME": random.choice(["ADET", "KG", "M", "M2"]),
        })
    # Demo sorusu deterministik olsun: 2023 mali yılında EN YÜKSEK birim fiyat
    rows.append({
        "FISCPER": "2023001", "FISCVARNT": "K4", "PLANT": "1000",
        "MATERIAL": "DM-PASLANMAZ-7012", "MAKTX": "Demo Paslanmaz Çelik Levha",
        "VENDOR": "V900003", "SATICI_ADI": "Marmara Metal Tic. A.Ş.",
        "AMOUNT": 5200.0 * 120, "PRICE": 5200.0, "PRICE_UNIT": 1,
        "CURRENCY": "TRY", "ZTERM": "60", "ZBPRME": "ADET",
    })
    return rows


def main():
    if "--yes" not in sys.argv:
        print("UYARI: Bu script DB_NAME veritabanına SENTETİK demo verisi yazar.")
        print(f"  Hedef DB_NAME = {os.getenv('DB_NAME')!r}")
        print("  Gerçek üretim veritabanı DEĞİLSE devam edin:  python testdata/seed_demo_data.py --yes")
        return

    print(f"[DEMO] Hedef veritabanı: {os.getenv('DB_NAME')!r}")
    conn = get_connection()
    cur  = conn.cursor()

    print("[1/4] Tablolar hazırlanıyor...")
    from testdata.setup_db import create_tables, SHIPMENT_SCHEMA_TEXT
    create_tables(cur)
    _ensure_integration_columns(cur)
    _create_data_table(cur, "shipments_demo", SHIP_COLS)
    _create_data_table(cur, "sas_data_demo", SAS_COLS)
    conn.commit()

    print("[1.5/4] Önceki demo kayıtları temizleniyor (çift kayıt önlenir)...")
    _cleanup_demo(cur)
    conn.commit()

    print("[2/4] Demo entegrasyonları seed ediliyor...")
    ship_id = _seed_integration(
        cur, "Sevkiyat Servisi (Demo)",
        "Demo sentetik sevkiyat/teslimat verileri (gerçek veri DEĞİLDİR).",
        "shipments_demo", SHIPMENT_SCHEMA_TEXT.replace("shipments", "shipments_demo"),
        [("ISTART_DATE", "DATE", "Başlangıç tarihi"), ("IFINISH_DATE", "DATE", "Bitiş tarihi")],
    )
    sas_id = _seed_integration(
        cur, "Satınalma Servisi (Demo)",
        "Demo sentetik satınalma/fiyat verileri (gerçek veri DEĞİLDİR).",
        "sas_data_demo", SAS_SCHEMA_TEXT,
        [("IV_MATERIAL","char40","Malzeme"), ("IV_VENDOR","char10","Satıcı"),
         ("IV_FISCPER","numeric7","Mali yıl/dönem"), ("IV_PLANT","char4","Üretim yeri")],
    )
    conn.commit()

    print("[3/4] Sentetik veriler yazılıyor...")
    ship_rows = gen_shipments()
    sas_rows  = gen_sas()
    _insert_rows(cur, "shipments_demo", ship_id, ship_rows)
    _insert_rows(cur, "sas_data_demo", sas_id, sas_rows)
    conn.commit()
    print(f"   shipments: {len(ship_rows)} satır | sas_data: {len(sas_rows)} satır")
    conn.close()

    print("[4/4] Qdrant indeksleme (opsiyonel)...")
    try:
        from app.services.qdrant_indexer import index_all_integrations
        results = index_all_integrations()
        for name, info in results.items():
            print(f"   {name}: {info.get('status')}")
    except Exception as e:
        print(f"   (atlandı — OpenAI/Qdrant erişilemedi: {e})")

    print("\n✓ Demo hazır. Uygulamayı başlatıp 'demo / demo123' ile giriş yapın (firma: Demo).")
    print("  Örnek sorular:")
    print("   - Son 30 günde şehir bazında sevkiyat sayısı")
    print("   - Nisan ayında en çok teslimat yapılan müşteri")
    print("   - 2023 mali yılında birim fiyatı en yüksek malzemem hangisi?")


if __name__ == "__main__":
    main()
