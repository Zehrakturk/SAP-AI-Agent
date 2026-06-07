"""
app/api/semantics.py — Metrik Sözlüğü (Semantic Layer) yönetim API'si.

Endpoint'ler (prefix /api/v1/metrics) — tümü ADMIN:
  GET    /          — metrik listesi
  POST   /          — metrik ekle
  GET    /<id>      — tek metrik
  PUT    /<id>      — güncelle
  DELETE /<id>      — sil
"""

from __future__ import annotations

from flask import Blueprint, request, jsonify

from app.services.tenant import is_admin, company_from_request
from app.services       import semantic_layer

metrics_bp = Blueprint("metrics", __name__)


def _admin_guard():
    return None if is_admin(request) else (jsonify({"error": "Admin yetkisi gerekli"}), 403)


@metrics_bp.route("/", methods=["GET"])
def list_all():
    g = _admin_guard()
    if g:
        return g
    company = request.args.get("company")  # opsiyonel filtre
    return jsonify({"items": semantic_layer.list_metrics(company=company)})


@metrics_bp.route("/", methods=["POST"])
def create():
    g = _admin_guard()
    if g:
        return g
    data = request.get_json(force=True) or {}
    if not (data.get("metric_key") and data.get("expression")):
        return jsonify({"error": "metric_key ve expression zorunludur"}), 400
    return jsonify(semantic_layer.create_metric(data)), 201


@metrics_bp.route("/<int:metric_id>", methods=["GET"])
def get_one(metric_id):
    g = _admin_guard()
    if g:
        return g
    m = semantic_layer.get_metric(metric_id)
    return (jsonify(m), 200) if m else (jsonify({"error": "Bulunamadı"}), 404)


@metrics_bp.route("/<int:metric_id>", methods=["PUT"])
def update(metric_id):
    g = _admin_guard()
    if g:
        return g
    data = request.get_json(force=True) or {}
    m = semantic_layer.update_metric(metric_id, data)
    return (jsonify(m), 200) if m else (jsonify({"error": "Bulunamadı"}), 404)


@metrics_bp.route("/<int:metric_id>", methods=["DELETE"])
def delete(metric_id):
    g = _admin_guard()
    if g:
        return g
    ok = semantic_layer.delete_metric(metric_id)
    return (jsonify({"ok": True}), 200) if ok else (jsonify({"error": "Bulunamadı"}), 404)
