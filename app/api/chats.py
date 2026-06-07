"""
app/api/chats.py  —  MSSQL tabanlı sohbet geçmişi yönetimi.

Tablolar (otomatik oluşturulur):
  chat_sessions  — id, user_id, title, created_at, updated_at
  chat_messages  — id, session_id, role, content, data_json, created_at
"""

import json
import uuid
from datetime import datetime

from flask import Blueprint, request, jsonify

from app.services.db import get_connection

chats_bp = Blueprint("chats", __name__)

# ─────────────────────────────────────────────────────────────────────────────
# Tablo kurulumu (uygulama başlarken bir kez çalıştır)
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_tables():
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'chat_sessions')
        CREATE TABLE chat_sessions (
            id         NVARCHAR(40)  NOT NULL PRIMARY KEY,
            user_id    NVARCHAR(100) NOT NULL,
            title      NVARCHAR(500),
            created_at DATETIME DEFAULT GETDATE(),
            updated_at DATETIME DEFAULT GETDATE()
        )
    """)
    cursor.execute("""
        IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'chat_messages')
        CREATE TABLE chat_messages (
            id         INT IDENTITY(1,1) PRIMARY KEY,
            session_id NVARCHAR(40)  NOT NULL,
            role       NVARCHAR(20)  NOT NULL,
            content    NVARCHAR(MAX),
            data_json  NVARCHAR(MAX),
            created_at DATETIME DEFAULT GETDATE()
        )
    """)
    # Sprint 3.3 — tag + pin kolonları (idempotent ALTER)
    cursor.execute("""
        IF COL_LENGTH('chat_sessions', 'tags') IS NULL
            ALTER TABLE chat_sessions ADD tags NVARCHAR(500) NULL
    """)
    cursor.execute("""
        IF COL_LENGTH('chat_sessions', 'pinned') IS NULL
            ALTER TABLE chat_sessions ADD pinned BIT NOT NULL DEFAULT 0
    """)
    conn.commit()
    conn.close()


try:
    _ensure_tables()
except Exception as _e:
    print(f"[CHATS] Tablo oluşturma başarısız (DB bağlantısı yok?): {_e}")


# ─────────────────────────────────────────────────────────────────────────────
# Yardımcılar
# ─────────────────────────────────────────────────────────────────────────────

def _current_user_id(req) -> str:
    """
    Sohbet sahibini belirler. Tek doğruluk kaynağı `tenant.user_id_from_request`
    (token formatı `demo-token-{id}-{role}-{company}`). Böylece auth değişiklikleri
    sonrası user_id tutarlı kalır ve geçmiş "kaybolmaz".
    """
    from app.services.tenant import user_id_from_request
    uid = user_id_from_request(req)
    return str(uid) if uid not in (None, "") else "unknown"


def _session_owner(cursor, session_id):
    """Oturumun sahibini (user_id) döndürür; oturum yoksa None."""
    cursor.execute("SELECT user_id FROM chat_sessions WHERE id = ?", (session_id,))
    row = cursor.fetchone()
    return row[0] if row else None


def _can_access(req, owner_id) -> bool:
    """Sahibi olan veya global (ADMIN/ALL) kullanıcı erişebilir."""
    if owner_id is None:
        return False
    from app.services.tenant import company_from_request, is_global
    if is_global(company_from_request(req)):
        return True
    return str(owner_id) == _current_user_id(req)


def _row_to_session(row, cols) -> dict:
    d = dict(zip(cols, row))
    if isinstance(d.get("created_at"), datetime):
        d["created_at"] = d["created_at"].strftime("%d %b %H:%M")
    if isinstance(d.get("updated_at"), datetime):
        d["updated_at"] = d["updated_at"].strftime("%d %b %H:%M")
    # tags → liste, pinned → bool
    if "tags" in d:
        raw = d.get("tags") or ""
        d["tags"] = [t.strip() for t in str(raw).split(",") if t.strip()]
    if "pinned" in d:
        d["pinned"] = bool(d.get("pinned"))
    return d


def _auto_tags(text: str, max_tags: int = 3) -> list[str]:
    """
    Metinden ilgi tag'leri çıkarır (personalizer keyword sözlüğünü yeniden kullanır).
    API maliyeti yok — anahtar kelime eşlemesi.
    """
    try:
        from app.services.insights.personalizer import _KEYWORD_TAGS
    except Exception:
        return []
    tl = (text or "").lower()
    found = [tag for tag, kws in _KEYWORD_TAGS.items() if any(k in tl for k in kws)]
    return found[:max_tags]


def _row_to_message(row, cols) -> dict:
    d = dict(zip(cols, row))
    if isinstance(d.get("created_at"), datetime):
        d["created_at"] = d["created_at"].strftime("%d %b %H:%M")
    # data_json string → dict
    if d.get("data_json"):
        try:
            d["data"] = json.loads(d["data_json"])
        except Exception:
            d["data"] = {}
    return d


# ─────────────────────────────────────────────────────────────────────────────
# Oturum listesi
# ─────────────────────────────────────────────────────────────────────────────

@chats_bp.route("/sessions", methods=["GET"])
def list_sessions():
    user_id = _current_user_id(request)
    q       = (request.args.get("q") or "").lower()

    conn   = get_connection()
    cursor = conn.cursor()
    # NOT: Kasıtlı olarak LIMIT/TOP YOK — kullanıcının TÜM sohbet geçmişi süresiz tutulur
    # ve döner. Geçmiş yalnızca kullanıcı bir oturumu açıkça silerse kaybolur.
    cursor.execute("""
        SELECT s.id, s.user_id, s.title, s.tags, s.pinned,
               s.created_at, s.updated_at,
               COUNT(m.id) AS message_count
        FROM   chat_sessions s
        LEFT   JOIN chat_messages m ON m.session_id = s.id
        WHERE  s.user_id = ?
        GROUP  BY s.id, s.user_id, s.title, s.tags, s.pinned,
                  s.created_at, s.updated_at
        ORDER  BY s.pinned DESC, s.updated_at DESC
    """, (user_id,))
    cols = [c[0] for c in cursor.description]
    rows = [_row_to_session(r, cols) for r in cursor.fetchall()]
    conn.close()

    # Arama — başlık VEYA tag eşleşmesi
    if q:
        rows = [
            r for r in rows
            if q in (r.get("title") or "").lower()
            or any(q in t.lower() for t in (r.get("tags") or []))
        ]

    # tag filtresi (?tag=sevkiyat)
    tag_filter = (request.args.get("tag") or "").lower().strip()
    if tag_filter:
        rows = [r for r in rows
                if any(tag_filter == t.lower() for t in (r.get("tags") or []))]

    return jsonify(rows)


# ─────────────────────────────────────────────────────────────────────────────
# Oturum oluştur
# ─────────────────────────────────────────────────────────────────────────────

@chats_bp.route("/sessions", methods=["POST"])
def create_session():
    user_id = _current_user_id(request)
    data    = request.get_json(force=True) or {}
    title   = (data.get("title") or "Yeni Sohbet")[:500]
    sid     = str(uuid.uuid4())

    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO chat_sessions (id, user_id, title) VALUES (?, ?, ?)",
        (sid, user_id, title)
    )
    conn.commit()
    conn.close()
    return jsonify({"id": sid, "title": title, "user_id": user_id}), 201


# ─────────────────────────────────────────────────────────────────────────────
# Oturum detayı
# ─────────────────────────────────────────────────────────────────────────────

@chats_bp.route("/sessions/<session_id>", methods=["GET"])
def get_session(session_id):
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM chat_sessions WHERE id = ?", (session_id,))
    cols = [c[0] for c in cursor.description]
    row  = cursor.fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "Oturum bulunamadı"}), 404
    owner = dict(zip(cols, row)).get("user_id")
    if not _can_access(request, owner):
        return jsonify({"error": "Bu oturuma erişim yetkiniz yok"}), 403
    return jsonify(_row_to_session(row, cols))


# ─────────────────────────────────────────────────────────────────────────────
# Oturum mesajları
# ─────────────────────────────────────────────────────────────────────────────

@chats_bp.route("/sessions/<session_id>/messages", methods=["GET"])
def get_messages(session_id):
    conn   = get_connection()
    cursor = conn.cursor()
    if not _can_access(request, _session_owner(cursor, session_id)):
        conn.close()
        return jsonify({"error": "Bu oturuma erişim yetkiniz yok"}), 403
    # NOT: LIMIT/TOP YOK — oturumdaki tüm mesajlar (tam geçmiş) kronolojik döner.
    cursor.execute(
        "SELECT * FROM chat_messages WHERE session_id = ? ORDER BY created_at ASC, id ASC",
        (session_id,)
    )
    cols = [c[0] for c in cursor.description]
    rows = [_row_to_message(r, cols) for r in cursor.fetchall()]
    conn.close()
    return jsonify(rows)


# ─────────────────────────────────────────────────────────────────────────────
# Mesaj kaydet (query.py'den çağrılır)
# ─────────────────────────────────────────────────────────────────────────────

@chats_bp.route("/sessions/<session_id>/messages", methods=["POST"])
def add_message(session_id):
    data = request.get_json(force=True) or {}
    role    = data.get("role", "user")
    content = data.get("content", "")
    # AI yanıtının tam verisi (rows, chart_data vb.) JSON olarak saklanır
    msg_data = data.get("data")
    data_json = json.dumps(msg_data, ensure_ascii=False, default=str) if msg_data else None

    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO chat_messages (session_id, role, content, data_json) VALUES (?, ?, ?, ?)",
        (session_id, role, content[:4000], data_json)
    )
    # Oturumun updated_at'ını güncelle
    cursor.execute(
        "UPDATE chat_sessions SET updated_at = GETDATE() WHERE id = ?",
        (session_id,)
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True}), 201


# ─────────────────────────────────────────────────────────────────────────────
# Oturum sil
# ─────────────────────────────────────────────────────────────────────────────

@chats_bp.route("/sessions/<session_id>", methods=["DELETE"])
def delete_session(session_id):
    conn   = get_connection()
    cursor = conn.cursor()
    # Yalnız oturum sahibi (veya global admin) silebilir — başkasının geçmişi silinemez
    if not _can_access(request, _session_owner(cursor, session_id)):
        conn.close()
        return jsonify({"error": "Bu oturumu silme yetkiniz yok"}), 403
    cursor.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
    cursor.execute("DELETE FROM chat_sessions  WHERE id = ?",        (session_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


# ─────────────────────────────────────────────────────────────────────────────
# Oturum başlığını güncelle
# ─────────────────────────────────────────────────────────────────────────────

@chats_bp.route("/sessions/<session_id>/title", methods=["PATCH"])
def update_title(session_id):
    title = (request.get_json(force=True) or {}).get("title", "")[:500]
    conn  = get_connection()
    cursor = conn.cursor()
    if not _can_access(request, _session_owner(cursor, session_id)):
        conn.close()
        return jsonify({"error": "Yetki yok"}), 403
    cursor.execute(
        "UPDATE chat_sessions SET title = ? WHERE id = ?",
        (title, session_id)
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


# ─────────────────────────────────────────────────────────────────────────────
# Pin / Unpin  (Sprint 3.3)
# ─────────────────────────────────────────────────────────────────────────────

@chats_bp.route("/sessions/<session_id>/pin", methods=["PATCH"])
def toggle_pin(session_id):
    pinned = bool((request.get_json(force=True) or {}).get("pinned", True))
    conn   = get_connection()
    cursor = conn.cursor()
    if not _can_access(request, _session_owner(cursor, session_id)):
        conn.close()
        return jsonify({"error": "Yetki yok"}), 403
    cursor.execute(
        "UPDATE chat_sessions SET pinned = ? WHERE id = ?",
        (1 if pinned else 0, session_id)
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "pinned": pinned})


# ─────────────────────────────────────────────────────────────────────────────
# Etiket güncelle  (Sprint 3.3)
# ─────────────────────────────────────────────────────────────────────────────

@chats_bp.route("/sessions/<session_id>/tags", methods=["PATCH"])
def update_tags(session_id):
    data = request.get_json(force=True) or {}
    tags = data.get("tags")
    # Sahiplik kontrolü
    _c = get_connection(); _cur = _c.cursor()
    _owner = _session_owner(_cur, session_id); _c.close()
    if not _can_access(request, _owner):
        return jsonify({"error": "Yetki yok"}), 403
    # tags verilmezse başlıktan/ilk mesajdan otomatik üret
    if tags is None:
        conn   = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT TOP 1 content FROM chat_messages
            WHERE session_id = ? AND role = 'user' ORDER BY id ASC
        """, (session_id,))
        row = cursor.fetchone()
        conn.close()
        tags = _auto_tags(row[0] if row else "")
    else:
        tags = [str(t).strip() for t in tags if str(t).strip()][:5]

    value = ",".join(tags)
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE chat_sessions SET tags = ? WHERE id = ?",
        (value, session_id)
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "tags": tags})
