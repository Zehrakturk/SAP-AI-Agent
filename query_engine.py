import pyodbc
import json
from openai import OpenAI
from app.models.store import DB_PATH
import re
import json

client = OpenAI() 

SCHEMA = """
Tablo: shipments
Açıklama: SAP sisteminden alınan sevkiyat, teslimat ve kalem bazlı lojistik verilerini içerir.

Kolonlar:
- TKNUM: Sevkiyat (Shipment) numarası.
- ERDAT: Sevkiyatın oluşturulma tarihi (YYYY-MM-DD).
- ERNAM: Sevkiyat belgesini oluşturan kullanıcı adı.
- DPLBG: Yükleme başlangıcı için planlanan tarih.
- ROUTE: Nakliye rotası kodu.
- ROUTE_TNM: Nakliye rotasının tam adı (Örn: Northern Route).
- SHTYP: Sevkiyat tipi (Örn: Z002).
- VSART: Taşıma türü kodu (Shipping Type - Örn: 08).
- VSART_TNM: Teslimatın yapılacağı araç veya taşıma yöntemi adı.
- TNDR_TRKID: İhale/İzleme kimliği.
- SIGNI: Plaka numarası (Konteyner veya araç kimliği).
- ZDORSE_NO: Dorsenin plaka numarası.
- SOFOR_ADI1: Sürücü/Şoför adı.
- SOFOR_ADI2: Sürücü/Şoför soyadı.
- NDURUM: Nakliye durum kodu (Örn: 05 - Sevkiyatın aşamasını belirtir).
- ADURUM: Araç durum kodu.
- FIDATUM: Finansal onay tarihi.
- SDATUM: Sevk talep tarihi.
- WADAT_IST: Fiili mal çıkış tarihi (YYYY-MM-DD).
- VBELN: Satış siparişi veya teslimat numarası.
- ERDAT_LKP: Siparişin/Teslimatın yaratılma tarihi.
- ERNAM_LKP: Siparişi/Teslimatı yaratan kullanıcı.
- KUNAG: Siparişi veren (Sold-to party) müşteri numarası.
- MUSTERI_ADI: Müşterinin tam ticari ünvanı.
- KUNNR: Malı teslim alan (Ship-to party) müşteri numarası.
- ISIM: Müşteri ismi veya ek açıklama alanı.
- BEZEI: Şehir veya bölge açıklaması (Örn: Modena).
- CITY1: İlçe veya ülke bilgisi (Görselde ITALY olarak geçiyor).
- POSNR: Teslimat kalem (pozisyon) numarası.
- MATNR: Malzeme (Ürün) numarası.
- MAKTX: Malzeme/Ürün kısa açıklaması.
- LFIMG: Teslimat miktarı (Numerik değer).
- LGORT: Depo yeri (Storage Location).
- ZZTDEPO: Toplama yapılacak ana depo kodu.
- VGBEL: Referans alınan önceki belge numarası (Sipariş referansı).
- UMVKZ: Ölçü birimi dönüştürme katsayısı (Bölünen).
- UMVKN: Ölçü birimi dönüştürme katsayısı (Bölen).
- BSTKD: Müşteri referans numarası (PO Number).
- TDURUM: Teslimatın güncel durum kodu (Örn: 04).
- TDURUM_TNM: Teslimat durumunun metin açıklaması (Örn: MAL ÇIKIŞI YAPILDI).
- VOLUM: Malzemenin hacim miktarı.
- VOLEH: Hacim ölçü birimi (Örn: M3, L).
- fetched_at: Verinin SAP'den çekilerek bu tabloya kaydedildiği zaman damgası.
"""


def _call_openai_json(prompt: str, max_tokens: int = 800) -> dict:
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            max_tokens=max_tokens,
            response_format={ "type": "json_object" }, # Modelin SADECE JSON dönmesini zorluyoruz
            messages=[
                {"role": "system", "content": "Sen verileri analiz edip SADECE geçerli bir JSON formatında yanıt veren bir asistan/API'sin."},
                {"role": "user", "content": prompt}
            ]
        )
        content = response.choices[0].message.content.strip()
        return json.loads(content) # Gelen string yanıtı Python sözlüğüne (dictionary) çeviriyoruz
    except Exception as e:
        # JSON parse hatası veya API hatası olursa sistemin çökmemesi için varsayılan dönüş
        return {
            "text_summary": "Veri analiz edilirken bir hata oluştu.",
            "chart_type": "NONE",
            "chart_data": {}
        }

def _call_openai(prompt: str, max_tokens: int = 500) -> str:
    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()


# def ask(user_question: str) -> dict:
#     # 1. SQL Üretim Aşaması (Analiz yeteneği eklendi)
#     sql_prompt = f"""Sen bir SAP Lojistik ve T-SQL uzmanısın. 
# Aşağıdaki tablo şemasına göre kullanıcının sorusunu en iyi analiz edecek Microsoft SQL Server (T-SQL) SELECT sorgusunu yaz.

# {SCHEMA}

# KURALLAR:
# 1. Karşılaştırma sorularında GROUP BY, SUM(LFIMG), COUNT(*) gibi fonksiyonlarla grupla.
# 2. Tarih filtreleri için ERDAT kolonunu kullan. Tarih fonksiyonu olarak YEAR(ERDAT), MONTH(ERDAT), FORMAT(ERDAT, 'yyyy-MM') kullan. strftime KULLANMA.
# 3. Büyük/Küçük harf için UPPER(...) LIKE UPPER('%aranan%') kullan.
# 4. Sadece SQL yaz, açıklama yapma. SQLite syntax kullanma, sadece T-SQL yaz.

# Soru: {user_question}
# SQL:"""
#     raw_sql = _call_openai(sql_prompt, max_tokens=300)
#     sql = clean_sql(raw_sql) # Yukarıdaki temizleme fonksiyonunu çağırıyoruz

#     # Güvenlik Kontrolü (Daha esnek ve sağlam)
#     forbidden_words = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE"]
#     is_safe = sql.upper().startswith("SELECT") or sql.upper().startswith("WITH")
#     contains_forbidden = any(word in sql.upper() for word in forbidden_words)

#     if not is_safe or contains_forbidden:
#         return {
#             "error": "Sorgu güvenlik denetiminden geçemedi. Sadece veri okuma (SELECT) işlemlerine izin verilir.",
#             "sql": sql
#         }

#     # 2. SQLite Çalıştırma
#     try:
#         conn = pyodbc.connect(CONN_STR)
#         cursor = conn.cursor()
#         cursor.execute(sql)
#         columns = [col[0] for col in cursor.description]
#         rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
#         conn.close()
#     except Exception as e:
#         return {"error": str(e), "sql": sql}

#     # 3. Analitik Raporlama Aşaması (Yorumlama yeteneği eklendi)
#     if rows:
#         # Burada modele "Sadece özetleme, verileri birbiriyle kıyasla" diyoruz.
#         report_prompt = f"""
#         Kullanıcı Sorusu: "{user_question}"
#         Sistemden Çekilen Analitik Veriler: {json.dumps(rows, ensure_ascii=False, default=str)}

#         GÖREV:
#         Sen bir lojistik analistisin. Yukarıdaki ham verileri kullanarak kullanıcıya profesyonel bir rapor sun.
#         - Eğer aylar arası bir kıyaslama varsa (Şubat-Mart gibi), aradaki farkı (artış/azalış) miktarsal olarak belirt.
#         - En çok sevkiyat yapılan müşteriyi veya ürünü öne çıkar.
#         - Veri içindeki anomalileri (Örn: bir ayda çok az sevkiyat olması) yorumla.
#         - Yanıtı kısa maddeler halinde ve profesyonel bir dille yaz.
#         """
#         summary = _call_openai(report_prompt, max_tokens=600)
#     else:
#         summary = "Belirttiğiniz kriterlere uygun bir sevkiyat verisi bulunamadı."

#     return {
#         "sql": sql,
#         "rows": rows,
#         "count": len(rows),
#         "summary": summary
#     }
def ask(user_question: str) -> dict:
    # 1. SQL Üretimi
    sql_prompt = f"""Sen bir SAP Lojistik ve T-SQL uzmanısın. 
Aşağıdaki tablo şemasına göre kullanıcının sorusunu en iyi analiz edecek Microsoft SQL Server (T-SQL) SELECT sorgusunu yaz.

{SCHEMA}

KURALLAR:
1. Karşılaştırma sorularında GROUP BY, SUM(LFIMG), COUNT(*) gibi fonksiyonlarla grupla.
2. Tarih filtreleri için YEAR(ERDAT), MONTH(ERDAT), FORMAT(ERDAT, 'yyyy-MM') kullan. strftime KULLANMA.
3. Büyük/Küçük harf için UPPER(...) LIKE UPPER('%aranan%') kullan.
4. Sadece SQL yaz, açıklama yapma. SQLite syntax kullanma, sadece T-SQL yaz.

Soru: {user_question}
SQL:"""

    raw_sql = _call_openai(sql_prompt, max_tokens=300)
    sql = clean_sql(raw_sql)

    forbidden_words = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE"]
    is_safe = sql.upper().startswith("SELECT") or sql.upper().startswith("WITH")
    contains_forbidden = any(word in sql.upper() for word in forbidden_words)

    if not is_safe or contains_forbidden:
        return {
            "error": "Sorgu güvenlik denetiminden geçemedi.",
            "sql": sql
        }

    # 2. SQL Server'da Çalıştır
    try:
        conn = pyodbc.connect(CONN_STR)
        cursor = conn.cursor()
        cursor.execute(sql)
        columns = [col[0] for col in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()
    except Exception as e:
        return {"error": str(e), "sql": sql}

    # 3. Analiz + Görsel Öneri (JSON)
    if rows:
        report_prompt = f"""
Sen bir lojistik analistisin ve aynı zamanda bir veri görselleştirme uzmanısın.

Kullanıcı Sorusu: "{user_question}"
Veriler: {json.dumps(rows, ensure_ascii=False, default=str)}

Aşağıdaki JSON formatında yanıt ver:
{{
  "text_summary": "Profesyonel Türkçe analiz metni. Farkları, artış/azalışları, öne çıkan değerleri belirt.",
  "chart_type": "BAR veya LINE veya PIE veya TABLE veya NONE",
  "chart_data": {{
    "labels": ["Etiket1", "Etiket2"],
    "datasets": [
      {{
        "label": "Veri Seti Adı",
        "data": [100, 200]
      }}
    ]
  }}
}}

chart_type seçim kuralları:
- Ay/dönem karşılaştırması → BAR veya LINE
- Dağılım/oran → PIE
- Detaylı liste → TABLE
- Tek bir sayısal sonuç → NONE

Sadece JSON döndür, başka hiçbir şey yazma.
"""
        result = _call_openai_json(report_prompt, max_tokens=800)
    else:
        result = {
            "text_summary": "Belirttiğiniz kriterlere uygun veri bulunamadı.",
            "chart_type": "NONE",
            "chart_data": {}
        }

    return {
        "sql": sql,
        "rows": rows,
        "count": len(rows),
        "summary": result.get("text_summary", ""),
        "chart_type": result.get("chart_type", "NONE"),
        "chart_data": result.get("chart_data", {})
    }

# def ask(user_question: str) -> dict:
#     # 1. SQL üret
#     sql_prompt = f"""Sen bir SQL uzmanısın. Aşağıdaki SQLite tablosu için kullanıcının Türkçe sorusunu geçerli bir SQLite SELECT sorgusuna çevir.

# {SCHEMA}

# KURALLAR:
# - Sadece SELECT sorgusu yaz
# - Türkçe karakter aramalarında LIKE kullan (büyük/küçük harf duyarsız)
# - Tarih kolonları TEXT formatında saklanıyor (YYYY-MM-DD)
# - Sadece SQL yaz, başka hiçbir şey yazma, markdown kullanma, backtick kullanma

# Soru: {user_question}
# SQL:"""

#     sql = _call_openai(sql_prompt, max_tokens=300)

#     # Güvenlik: sadece SELECT
#     if not sql.strip().upper().startswith("SELECT"):
#         return {"error": "Güvensiz sorgu engellendi.", "sql": sql}

#     # 2. SQLite'ta çalıştır
#     try:
#         conn = sqlite3.connect(DB_PATH)
#         conn.row_factory = sqlite3.Row
#         cursor = conn.execute(sql)
#         rows = [dict(r) for r in cursor.fetchall()]
#         conn.close()
#     except Exception as e:
#         return {"error": str(e), "sql": sql}

#     # 3. Sonucu özetle
#     if rows:
#         summary_prompt = f"""Kullanıcı şunu sordu: "{user_question}"
# Sorgu sonucunda {len(rows)} kayıt bulundu.
# İlk 5 kayıt: {json.dumps(rows[:5], ensure_ascii=False, default=str)}

# Sonucu kullanıcıya kısa, net ve Türkçe olarak açıkla. Sadece özet yaz."""
#         summary = _call_openai(summary_prompt, max_tokens=300)
#     else:
#         summary = "Bu kriterlere uyan kayıt bulunamadı."

#     return {
#         "sql": sql,
#         "rows": rows,
#         "count": len(rows),
#         "summary": summary
#     }

def clean_sql(sql_text: str) -> str:
    # Markdown bloklarını temizle (```sql ... ```)
    sql_text = re.sub(r"```sql|```", "", sql_text, flags=re.IGNORECASE)
    # Baştaki ve sondaki boşlukları temizle
    return sql_text.strip()
