import sqlite3
import json
from openai import OpenAI
from app.models.store import DB_PATH

client = OpenAI() 

SCHEMA = """
Tablo: shipments
Kolonlar:
- TKNUM: Sevkiyat numarası
- ERDAT: Oluşturma tarihi (YYYY-MM-DD)
- ERNAM: Oluşturan kullanıcı
- DPLBG: Planlama tarihi
- ROUTE: Rota
- SHTYP: Sevkiyat tipi
- VSART: Taşıma türü kodu
- VSART_TNM: Taşıma türü adı (Sea, vb.)
- SIGNI: Ödeme tipi
- SOFOR_ADI1: Şoför adı
- NDURUM: Numerik durum kodu
- ADURUM: Alan durum kodu
- WADAT_IST: İstenen teslimat tarihi (YYYY-MM-DD)
- VBELN: Satış siparişi numarası
- KUNAG: Müşteri numarası
- MUSTERI_ADI: Müşteri adı
- KUNNR: Müşteri kodu
- ISIM: Müşteri ismi
- BEZEI: Bölge adı
- CITY1: Şehir
- POSNR: Pozisyon numarası
- MATNR: Malzeme numarası
- MAKTX: Malzeme açıklaması
- LFIMG: Teslimat miktarı (sayı)
- LGORT: Depo yeri
- ZZTDEPO: Depo kodu
- VGBEL: Önceki belge numarası
- TDURUM: Transfer durum kodu
- TDURUM_TNM: Transfer durum açıklaması
- VOLUM: Hacim (sayı)
- VOLEH: Hacim birimi
- fetched_at: Sisteme eklenme zamanı
"""


def _call_openai(prompt: str, max_tokens: int = 500) -> str:
    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()


def ask(user_question: str) -> dict:
    # 1. SQL üret
    sql_prompt = f"""Sen bir SQL uzmanısın. Aşağıdaki SQLite tablosu için kullanıcının Türkçe sorusunu geçerli bir SQLite SELECT sorgusuna çevir.

{SCHEMA}

KURALLAR:
- Sadece SELECT sorgusu yaz
- Türkçe karakter aramalarında LIKE kullan (büyük/küçük harf duyarsız)
- Tarih kolonları TEXT formatında saklanıyor (YYYY-MM-DD)
- Sadece SQL yaz, başka hiçbir şey yazma, markdown kullanma, backtick kullanma

Soru: {user_question}
SQL:"""

    sql = _call_openai(sql_prompt, max_tokens=300)

    # Güvenlik: sadece SELECT
    if not sql.strip().upper().startswith("SELECT"):
        return {"error": "Güvensiz sorgu engellendi.", "sql": sql}

    # 2. SQLite'ta çalıştır
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(sql)
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
    except Exception as e:
        return {"error": str(e), "sql": sql}

    # 3. Sonucu özetle
    if rows:
        summary_prompt = f"""Kullanıcı şunu sordu: "{user_question}"
Sorgu sonucunda {len(rows)} kayıt bulundu.
İlk 5 kayıt: {json.dumps(rows[:5], ensure_ascii=False, default=str)}

Sonucu kullanıcıya kısa, net ve Türkçe olarak açıkla. Sadece özet yaz."""
        summary = _call_openai(summary_prompt, max_tokens=300)
    else:
        summary = "Bu kriterlere uyan kayıt bulunamadı."

    return {
        "sql": sql,
        "rows": rows,
        "count": len(rows),
        "summary": summary
    }