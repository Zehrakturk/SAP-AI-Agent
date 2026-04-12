
from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
import random
from app.models.store import AI_LOGS, USERS, CHAT_SESSIONS

analytics_bp = Blueprint("analytics", __name__)


def _last_n_days(n: int):
    labels, counts = [], []
    today = datetime.now().date()
    for i in range(n - 1, -1, -1):
        day = today - timedelta(days=i)
        label = day.strftime("%d %b")
        labels.append(label)
        day_logs = [l for l in AI_LOGS if l["timestamp"].startswith(label)]
        counts.append(len(day_logs) if day_logs else random.randint(40, 180))
    return labels, counts


@analytics_bp.route("/dashboard", methods=["GET"])
def dashboard():
    today_label = datetime.now().strftime("%d %b")
    today_logs  = [l for l in AI_LOGS if l["timestamp"].startswith(today_label)]

    total_users    = len(USERS)
    messages_today = len(today_logs) or random.randint(150, 220)
    tokens_today   = sum(l["tokens"] for l in today_logs) or random.randint(200000, 280000)
    avg_latency    = (
        round(sum(l["latency"] for l in today_logs) / len(today_logs) / 1000, 1)
        if today_logs else round(random.uniform(0.9, 1.4), 1)
    )

    return jsonify({
        "total_users":    total_users,
        "messages_today": messages_today,
        "tokens_today":   f"{tokens_today // 1000}K",
        "avg_latency":    f"{avg_latency}s",
    })


@analytics_bp.route("/daily", methods=["GET"])
def daily():
    days = int(request.args.get("days", 14))
    labels, counts = _last_n_days(days)
    return jsonify({"labels": labels, "data": counts})


@analytics_bp.route("/tokens", methods=["GET"])
def token_usage():
    labels, _ = _last_n_days(14)
    input_tok  = [random.randint(6000, 18000) for _ in labels]
    output_tok = [random.randint(2000,  7000) for _ in labels]
    return jsonify({"labels": labels, "input": input_tok, "output": output_tok})


@analytics_bp.route("/top-questions", methods=["GET"])
def top_questions():
    limit = int(request.args.get("limit", 5))
    counts: dict = {}
    for l in AI_LOGS:
        counts[l["question"]] = counts.get(l["question"], 0) + 1
    top = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:limit]
    # Shorten labels for chart display
    labels = [q[:40] + "…" if len(q) > 40 else q for q, _ in top]
    data   = [c for _, c in top]
    return jsonify({"labels": labels, "data": data})


@analytics_bp.route("/model-usage", methods=["GET"])
def model_usage():
    counts: dict = {}
    for l in AI_LOGS:
        counts[l["model"]] = counts.get(l["model"], 0) + 1
    return jsonify({
        "labels": list(counts.keys()),
        "data":   list(counts.values()),
    })


@analytics_bp.route("/latency", methods=["GET"])
def latency():
    labels, _ = _last_n_days(14)
    data = [random.randint(700, 2000) for _ in labels]
    return jsonify({"labels": labels, "data": data})