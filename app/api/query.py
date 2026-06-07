import json
import time
import uuid

from flask import Blueprint, request, jsonify

from app.services.query_engine import ask
from app.services.db import get_connection
from app.models.store import AI_LOGS

query_bp = Blueprint("query", __name__)


def _save_to_session(session_id: str, user_question: str, result: dict):
    """Kullanıcı sorusunu ve AI yanıtını chat_messages'a kaydeder."""
    if not session_id:
        return
    try:
        conn   = get_connection()
        cursor = conn.cursor()
        # Kullanıcı mesajı
        cursor.execute(
            "INSERT INTO chat_messages (session_id, role, content) VALUES (?, 'user', ?)",
            (session_id, user_question[:4000])
        )
        # AI yanıtı — summary kısa içerik, data_json tam veri
        data_json = json.dumps({
            "sql"        : result.get("sql", ""),
            "count"      : result.get("count", 0),
            "chart_type" : result.get("chart_type", ""),
            "chart_data" : result.get("chart_data", {}),
            "kpis"       : result.get("kpis", []),
            "highlights" : result.get("highlights", []),
            "follow_ups" : result.get("follow_ups", []),
            "sources"    : result.get("sources", []),
            "metrics_used": result.get("metrics_used", []),
            "tables_used": result.get("tables_used", []),
            "mode"       : result.get("mode"),
            "live_success": result.get("live_success"),
            "live_message": result.get("live_message"),
        }, ensure_ascii=False, default=str)
        cursor.execute(
            "INSERT INTO chat_messages (session_id, role, content, data_json) VALUES (?, 'assistant', ?, ?)",
            (session_id, (result.get("summary") or result.get("error") or "")[:4000], data_json)
        )
        # Oturum updated_at güncelle
        cursor.execute(
            "UPDATE chat_sessions SET updated_at = GETDATE() WHERE id = ?",
            (session_id,)
        )
        # İlk mesajsa otomatik etiketle (tags boşsa)
        try:
            cursor.execute(
                "SELECT tags FROM chat_sessions WHERE id = ?", (session_id,)
            )
            trow = cursor.fetchone()
            if trow is not None and not (trow[0] or "").strip():
                from app.api.chats import _auto_tags
                tags = _auto_tags(user_question)
                if tags:
                    cursor.execute(
                        "UPDATE chat_sessions SET tags = ? WHERE id = ?",
                        (",".join(tags), session_id)
                    )
        except Exception as _te:
            print(f"[CHAT TAG] Otomatik etiketleme atlandı: {_te}")
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[CHAT SAVE] Hata: {e}")


@query_bp.route("/ask", methods=["POST"])
def ask_question():
    data     = request.get_json()
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({"error": "Soru boş olamaz"}), 400

    # Kullanıcı kimliği + firma token'dan (demo-token-{id}-{role}-{company})
    from app.services.tenant import user_id_from_request, company_from_request
    user_id = user_id_from_request(request) or "unknown"
    company = company_from_request(request)

    filters    = data.get("filters")    or {}
    session_id = data.get("session_id") or ""

    t_start = time.time()
    try:
        result = ask(question, filters=filters, session_id=session_id,
                     user_id=user_id, approval_mode=True, company=company)
    except Exception as e:
        from app.services.query_engine import OpenAIQuotaError
        latency = int((time.time() - t_start) * 1000)
        if isinstance(e, OpenAIQuotaError) or "insufficient_quota" in str(e).lower():
            msg = ("⚠️ AI servisi kotası dolmuş (OpenAI insufficient_quota). "
                   "Yöneticinin OpenAI faturalandırmasını yenilemesi gerekiyor. "
                   "Bu geçici bir durumdur; sorgu motoru ve SAP bağlantısı çalışıyor.")
        else:
            print(f"[QUERY] ask() hata: {e}")
            import traceback; traceback.print_exc()
            msg = f"Sorgu işlenirken hata oluştu: {e}"
        return jsonify({"error": msg, "summary": msg, "rows": [], "count": 0,
                        "chart_type": "NONE", "tables_used": []}), 200
    latency = int((time.time() - t_start) * 1000)

    # Oturuma kaydet — pending_approval ise asistan yanıtı olarak özet+talep id'si yazılır
    _save_to_session(session_id, question, result)

    # Gerçek sorguyu AI_LOGS'a ekle — GERÇEK token kullanımı (OpenAI .usage toplamı)
    status = "error" if result.get("error") else "success"
    from app.services.query_engine import _usage_get
    import os as _os
    _usage = _usage_get()
    AI_LOGS.insert(0, {
        "id"       : f"LOG-{uuid.uuid4().hex[:8].upper()}",
        "user_id"  : user_id,
        "question" : question,
        "response" : result.get("summary", result.get("error", "")),
        "model"    : _os.getenv("SQL_MODEL", "gpt-4o"),
        "tokens"   : _usage.get("total_tokens", 0),       # gerçek toplam token
        "prompt_tokens"    : _usage.get("prompt_tokens", 0),
        "completion_tokens": _usage.get("completion_tokens", 0),
        "llm_calls"        : _usage.get("llm_calls", 0),
        "latency"  : latency,
        "status"   : status,
        "timestamp": time.strftime("%d %b %H:%M"),
        "_sort_ts" : time.time(),
    })

    return jsonify(result)


@query_bp.route("/filter", methods=["POST"])
def filter_data():
    f          = request.get_json() or {}
    conditions = []
    params     = []

    if f.get("start_date"):
        conditions.append("ERDAT >= ?")
        params.append(f["start_date"])
    if f.get("end_date"):
        conditions.append("ERDAT <= ?")
        params.append(f["end_date"])
    if f.get("musteri"):
        conditions.append("MUSTERI_ADI LIKE ?")
        params.append(f"%{f['musteri']}%")
    if f.get("city"):
        conditions.append("CITY1 LIKE ?")
        params.append(f"%{f['city']}%")
    if f.get("tdurum"):
        conditions.append("TDURUM = ?")
        params.append(f["tdurum"])
    if f.get("vsart"):
        conditions.append("VSART = ?")
        params.append(f["vsart"])

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    sql   = f"SELECT TOP 500 * FROM shipments {where} ORDER BY ERDAT DESC"

    try:
        conn   = get_connection()
        cursor = conn.cursor()
        cursor.execute(sql, params)
        columns = [col[0] for col in cursor.description]
        rows    = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()
    except Exception as e:
        return jsonify({"error": str(e), "sql": sql}), 500

    return jsonify({"rows": rows, "count": len(rows), "sql": sql})
