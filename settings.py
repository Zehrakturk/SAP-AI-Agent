"""app/api/settings.py — Portal settings endpoints."""
from flask import Blueprint, jsonify, request
from app.models.store import SETTINGS

settings_bp = Blueprint("settings", __name__)

SAP_CONNECTORS = [
    {"name": "Z_GET_QUOTE_REQUESTS",       "type": "OData",    "status": "online",  "last_ping": "1m ago"},
    {"name": "Z_GET_PURCHASE_ORDERS",      "type": "RFC/BAPI", "status": "online",  "last_ping": "1m ago"},
    {"name": "Z_GET_SUPPLIER_PERFORMANCE", "type": "CDS View", "status": "online",  "last_ping": "2m ago"},
    {"name": "Z_GET_STOCK_LEVELS",         "type": "OData",    "status": "warning", "last_ping": "8m ago"},
    {"name": "Z_GET_FINANCIAL_SUMMARY",    "type": "SOAP",     "status": "offline", "last_ping": "42m ago"},
]

AVAILABLE_MODELS = [
    {"id": "claude-sonnet-4-6", "name": "Claude Sonnet 4.6", "vendor": "Anthropic", "tier": "balanced"},
    {"id": "claude-opus-4-6",   "name": "Claude Opus 4.6",   "vendor": "Anthropic", "tier": "premium"},
    {"id": "claude-haiku-4-5",  "name": "Claude Haiku 4.5",  "vendor": "Anthropic", "tier": "fast"},
]


@settings_bp.route("/", methods=["GET"])
def get_settings():
    return jsonify(SETTINGS)


@settings_bp.route("/", methods=["PUT"])
def update_settings():
    data = request.get_json(force=True)
    allowed = ["model", "temperature", "max_tokens", "top_p", "daily_budget",
               "backend_url", "rate_limit", "timeout", "system_prompt", "security", "logging"]
    for key in allowed:
        if key in data:
            if isinstance(data[key], dict) and isinstance(SETTINGS.get(key), dict):
                SETTINGS[key].update(data[key])
            else:
                SETTINGS[key] = data[key]
    return jsonify({"message": "Settings updated.", "settings": SETTINGS})


@settings_bp.route("/models", methods=["GET"])
def list_models():
    return jsonify(AVAILABLE_MODELS)


@settings_bp.route("/test-connection", methods=["POST"])
def test_connection():
    """Simulate a backend connectivity test."""
    import time
    time.sleep(0.8)   # Simulate round-trip
    return jsonify({
        "status":  "ok",
        "message": "Connection successful — Python backend responding.",
        "latency": "42ms",
    })


@settings_bp.route("/connectors", methods=["GET"])
def list_connectors():
    return jsonify(SAP_CONNECTORS)