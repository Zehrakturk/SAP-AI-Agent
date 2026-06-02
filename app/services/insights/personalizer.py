"""
personalizer — kullanıcının geçmiş sorgularına göre insight'ları yeniden sıralar.

Mantık (basit ve şeffaf):
  1. chat_messages'tan kullanıcının (role='user') son sorgularını oku.
  2. Anahtar kelimelerle ilgi alanı tag'lerine eşle (rota, müşteri, ürün, ...).
  3. Her insight'ın tag'leriyle örtüşmeye göre boost puanı ver.
  4. severity önceliğini bozmadan, eşit severity içinde ilgiye göre sırala.

Settings'ten manuel override: settings tablosunda 'insight_interests' anahtarı
(virgülle ayrık tag listesi) varsa onlar geçmişin üstüne eklenir.
"""

from __future__ import annotations

import re
from collections import Counter

from app.services.db import get_connection


# Türkçe anahtar kelime → ilgi tag'i eşlemesi
_KEYWORD_TAGS: dict[str, list[str]] = {
    "rota"      : ["rota", "güzergah", "guzergah", "hat", "sevk yeri"],
    "şehir"     : ["şehir", "sehir", "il", "istanbul", "ankara", "izmir", "city", "plaka"],
    "müşteri"   : ["müşteri", "musteri", "müsteri", "cari", "alıcı", "alici", "customer"],
    "ürün"      : ["ürün", "urun", "malzeme", "matnr", "product", "stok kalemi"],
    "operasyon" : ["durum", "tdurum", "gecik", "takıl", "takil", "bekle", "yüklen", "yuklen", "teslim"],
    "satış"     : ["satış", "satis", "sipariş", "siparis", "gelir", "ciro", "sales"],
    "sevkiyat"  : ["sevkiyat", "sevk", "teslimat", "kargo", "shipment", "lojistik"],
    "miktar"    : ["miktar", "adet", "tonaj", "hacim", "lfimg", "tutar"],
    "trend"     : ["trend", "artış", "artis", "düşüş", "dusus", "değişim", "degisim", "karşılaştır", "karsilastir"],
    "korelasyon": ["korelasyon", "ilişki", "iliski", "neden", "sebep", "etki"],
}


def _user_recent_questions(user_id: str, limit: int = 50) -> list[str]:
    """Kullanıcının son N sorusunu chat_messages'tan çeker (oturum sahibi eşleşmesiyle)."""
    try:
        conn   = get_connection()
        cursor = conn.cursor()
        # chat_sessions.user_id ile bağ kur (varsa); yoksa tüm user mesajları
        cursor.execute("""
            SELECT TOP (?) m.content
            FROM   chat_messages m
            JOIN   chat_sessions s ON s.id = m.session_id
            WHERE  m.role = 'user' AND s.user_id = ?
            ORDER  BY m.id DESC
        """, (limit, user_id))
        return [r[0] or "" for r in cursor.fetchall()]
    except Exception as e:
        print(f"[PERSONALIZER] Sorgu geçmişi okunamadı: {e}")
        return []
    finally:
        try: conn.close()
        except Exception: pass


_PREF_KEY = "insight_interests"


def _ensure_pref_table(cursor) -> None:
    cursor.execute("""
        IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'user_preferences')
        CREATE TABLE user_preferences (
            user_id    NVARCHAR(100) NOT NULL,
            pref_key   NVARCHAR(100) NOT NULL,
            pref_value NVARCHAR(MAX),
            updated_at DATETIME DEFAULT GETDATE(),
            CONSTRAINT PK_user_preferences PRIMARY KEY (user_id, pref_key)
        )
    """)


def get_manual_interests(user_id: str) -> list[str]:
    """Kullanıcının manuel seçtiği ilgi alanları (user_preferences tablosu)."""
    try:
        conn   = get_connection()
        cursor = conn.cursor()
        _ensure_pref_table(cursor)
        conn.commit()
        cursor.execute(
            "SELECT pref_value FROM user_preferences WHERE user_id = ? AND pref_key = ?",
            (user_id, _PREF_KEY),
        )
        row = cursor.fetchone()
        if row and row[0]:
            return [t.strip().lower() for t in str(row[0]).split(",") if t.strip()]
    except Exception as e:
        print(f"[PERSONALIZER] Manuel ilgi okunamadı: {e}")
    finally:
        try: conn.close()
        except Exception: pass
    return []


def set_manual_interests(user_id: str, interests: list[str]) -> list[str]:
    """Kullanıcının manuel ilgi alanlarını kaydeder/günceller. Geçerli tag'leri döner."""
    valid = [t.strip().lower() for t in interests
             if t and t.strip().lower() in _KEYWORD_TAGS]
    value = ",".join(valid)
    conn   = get_connection()
    cursor = conn.cursor()
    try:
        _ensure_pref_table(cursor)
        cursor.execute("""
            MERGE user_preferences AS tgt
            USING (SELECT ? AS user_id, ? AS pref_key) AS src
              ON tgt.user_id = src.user_id AND tgt.pref_key = src.pref_key
            WHEN MATCHED THEN
              UPDATE SET pref_value = ?, updated_at = GETDATE()
            WHEN NOT MATCHED THEN
              INSERT (user_id, pref_key, pref_value) VALUES (?, ?, ?);
        """, (user_id, _PREF_KEY, value, user_id, _PREF_KEY, value))
        conn.commit()
    finally:
        conn.close()
    return valid


def available_interest_tags() -> list[str]:
    """UI'ın toggle gösterebilmesi için tüm ilgi tag'lerini döner."""
    return sorted(_KEYWORD_TAGS.keys())


def _manual_interests(user_id: str) -> list[str]:
    return get_manual_interests(user_id)


def compute_interest_profile(user_id: str) -> dict[str, float]:
    """
    Kullanıcının ilgi profilini döner: {"sevkiyat": 0.8, "müşteri": 0.5, ...}
    Değerler 0..1 arası normalize edilir.
    """
    questions = _user_recent_questions(user_id)
    counter: Counter = Counter()

    for q in questions:
        ql = (q or "").lower()
        for tag, keywords in _KEYWORD_TAGS.items():
            if any(kw in ql for kw in keywords):
                counter[tag] += 1

    # Manuel ilgi alanlarına ekstra ağırlık
    for tag in _manual_interests(user_id):
        counter[tag] += 5   # manuel seçim güçlü sinyal

    if not counter:
        return {}

    top = counter.most_common(1)[0][1]
    return {tag: round(cnt / top, 3) for tag, cnt in counter.items()}


def _insight_tags(row: dict) -> list[str]:
    """Bir insight satırından tag listesini normalize eder."""
    raw = row.get("tags") or ""
    tags = [t.strip().lower() for t in str(raw).split(",") if t.strip()]
    # type ve metric'i de zayıf sinyal olarak kat
    if row.get("insight_type"):
        tags.append(str(row["insight_type"]).lower())
    return tags


def personalize(rows: list[dict], user_id: str | None) -> list[dict]:
    """
    Insight listesini kullanıcı ilgisine göre yeniden sıralar.
    severity önceliği korunur — sadece eşit severity grubu içinde ilgi puanı uygulanır.

    Her satıra '_interest_score' eklenir (debug/şeffaflık için).
    """
    if not user_id or not rows:
        return rows

    profile = compute_interest_profile(user_id)
    if not profile:
        return rows   # geçmiş yok → varsayılan sıra

    sev_rank = {"critical": 1, "warning": 2, "info": 3}

    def score(row: dict) -> float:
        tags = _insight_tags(row)
        return round(sum(profile.get(t, 0.0) for t in tags), 3)

    for r in rows:
        r["_interest_score"] = score(r)

    # severity birincil, ilgi puanı ikincil (yüksek puan üste)
    rows.sort(key=lambda r: (
        sev_rank.get(str(r.get("severity", "")).lower(), 4),
        -r.get("_interest_score", 0.0),
    ))
    return rows
