from flask import Blueprint, request, jsonify
from app.services.query_engine import ask

query_bp = Blueprint("query", __name__)

@query_bp.route("/ask", methods=["POST"])
def ask_question():
    data = request.get_json()
    question = data.get("question", "").strip()
    if not question:
        return jsonify({"error": "Soru boş olamaz"}), 400
    result = ask(question)
    return jsonify(result)

@query_bp.route("/filter", methods=["POST"])
def filter_data():
    """Filtre UI'dan gelen yapılandırılmış sorgu."""
    f = request.get_json()
    conditions = []
    params = []

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

    sql = "SELECT * FROM shipments"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY ERDAT DESC LIMIT 500"

    import sqlite3
    from app.models.store import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    conn.close()

    return jsonify({"rows": rows, "count": len(rows), "sql": sql})