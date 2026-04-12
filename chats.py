from flask import Blueprint, request, jsonify
from app.models.store import CHAT_SESSIONS, CHAT_MESSAGES

chats_bp = Blueprint("chats", __name__)


@chats_bp.route("/sessions", methods=["GET"])
def list_sessions():
    dept = request.args.get("department", "")
    q    = request.args.get("q", "").lower()

    result = CHAT_SESSIONS
    if dept:
        result = [s for s in result if s["department"] == dept]
    if q:
        result = [s for s in result if q in s["user_id"].lower() or q in s["preview"].lower()]

    return jsonify(result)


@chats_bp.route("/sessions/<session_id>", methods=["GET"])
def get_session(session_id):
    session = next((s for s in CHAT_SESSIONS if s["id"] == session_id), None)
    if not session:
        return jsonify({"detail": "Session not found"}), 404
    return jsonify(session)


@chats_bp.route("/sessions/<session_id>/messages", methods=["GET"])
def get_messages(session_id):
    messages = CHAT_MESSAGES.get(session_id)
    if messages is None:
        return jsonify({"detail": "Session not found"}), 404
    return jsonify(messages)


@chats_bp.route("/sessions/<session_id>", methods=["DELETE"])
def delete_session(session_id):
    global CHAT_SESSIONS
    session = next((s for s in CHAT_SESSIONS if s["id"] == session_id), None)
    if not session:
        return jsonify({"detail": "Session not found"}), 404
    CHAT_SESSIONS = [s for s in CHAT_SESSIONS if s["id"] != session_id]
    CHAT_MESSAGES.pop(session_id, None)
    return jsonify({"message": f"Session {session_id} deleted."})


@chats_bp.route("/sessions/<session_id>/export", methods=["POST"])
def export_session(session_id):
    messages = CHAT_MESSAGES.get(session_id)
    if messages is None:
        return jsonify({"detail": "Session not found"}), 404

    fmt = request.get_json(force=True).get("format", "json")

    if fmt == "txt":
        lines = []
        for m in messages:
            role = "User" if m["role"] == "user" else "AI Copilot"
            lines.append(f"[{m['time']}] {role}:\n{m['content']}\n")
        return jsonify({"format": "txt", "content": "\n".join(lines)})

    return jsonify({"format": "json", "content": messages})