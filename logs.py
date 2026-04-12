from flask import Blueprint, request, jsonify, make_response
import csv, io
from app.models.store import AI_LOGS

logs_bp = Blueprint("logs", __name__)


@logs_bp.route("/", methods=["GET"])
def list_logs():
    status = request.args.get("status", "")
    model  = request.args.get("model",  "")
    user   = request.args.get("user_id","")
    q      = request.args.get("q",      "").lower()
    limit  = int(request.args.get("limit", 100))
    offset = int(request.args.get("offset", 0))

    result = AI_LOGS
    if status:
        result = [l for l in result if l["status"] == status]
    if model:
        result = [l for l in result if l["model"] == model]
    if user:
        result = [l for l in result if l["user_id"] == user]
    if q:
        result = [l for l in result if q in l["question"].lower() or q in l["user_id"]]

    total  = len(result)
    paged  = result[offset : offset + limit]
    # Strip internal sort key
    clean  = [{k: v for k, v in l.items() if k != "_sort_ts"} for l in paged]
    return jsonify({"total": total, "items": clean})


@logs_bp.route("/<log_id>", methods=["GET"])
def get_log(log_id):
    log = next((l for l in AI_LOGS if l["id"] == log_id), None)
    if not log:
        return jsonify({"detail": "Log not found"}), 404
    return jsonify({k: v for k, v in log.items() if k != "_sort_ts"})


@logs_bp.route("/summary", methods=["GET"])
def summary():
    logs = AI_LOGS
    total   = len(logs)
    success = sum(1 for l in logs if l["status"] == "success")
    errors  = total - success
    avg_tok = round(sum(l["tokens"]  for l in logs) / total) if total else 0
    avg_lat = round(sum(l["latency"] for l in logs) / total) if total else 0

    model_counts = {}
    for l in logs:
        model_counts[l["model"]] = model_counts.get(l["model"], 0) + 1

    return jsonify({
        "total":        total,
        "success":      success,
        "errors":       errors,
        "avg_tokens":   avg_tok,
        "avg_latency":  avg_lat,
        "by_model":     model_counts,
    })


@logs_bp.route("/export", methods=["POST"])
def export_logs():
    """Return logs as CSV download."""
    logs = [{k: v for k, v in l.items() if k != "_sort_ts"} for l in AI_LOGS]

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["id","user_id","question","model","tokens","latency","status","timestamp"])
    writer.writeheader()
    writer.writerows(logs)

    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=ai_logs.csv"
    response.headers["Content-Type"] = "text/csv"
    return response