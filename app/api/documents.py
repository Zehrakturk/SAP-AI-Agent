"""
app/api/documents.py — PDF belge yönetimi (firma bazında).

Endpoint'ler (prefix /api/v1/documents):
  POST   /            — PDF yükle (multipart 'file') → indexle
  GET    /            — firma belgeleri listesi
  DELETE /<id>        — belgeyi sil (firma sahipliği kontrollü)
  POST   /ask         — belgelerden doğrudan soru-cevap (test/manuel)
"""

from __future__ import annotations

from flask import Blueprint, request, jsonify

from app.services.tenant import company_from_request, user_id_from_request
from app.services import doc_rag

documents_bp = Blueprint("documents", __name__)


@documents_bp.route("/", methods=["POST"])
def upload_document():
    company = company_from_request(request)
    user_id = user_id_from_request(request)

    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "PDF dosyası gerekli (form alanı: 'file')."}), 400
    if not f.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Yalnızca PDF desteklenir."}), 400

    # admin (ALL) yüklerken firma seçebilir; aksi halde kendi firması
    if company == "ALL":
        company = request.form.get("company") or "ALL"

    try:
        result = doc_rag.index_pdf(f.read(), f.filename, company, uploaded_by=user_id)
    except Exception as e:
        return jsonify({"error": f"İndeksleme hatası: {e}"}), 500

    if result.get("status") == "error":
        return jsonify(result), 422
    return jsonify(result), 201


@documents_bp.route("/", methods=["GET"])
def list_docs():
    company = company_from_request(request)
    return jsonify({"items": doc_rag.list_documents(company)})


@documents_bp.route("/<int:document_id>", methods=["DELETE"])
def delete_doc(document_id):
    company = company_from_request(request)
    ok = doc_rag.delete_document(document_id, company)
    if not ok:
        return jsonify({"error": "Belge bulunamadı veya yetki yok."}), 404
    return jsonify({"ok": True})


@documents_bp.route("/ask", methods=["POST"])
def ask_docs():
    """Belgelerden doğrudan soru-cevap (yönlendirme dışı manuel kullanım)."""
    company  = company_from_request(request)
    question = (request.get_json(force=True) or {}).get("question", "").strip()
    if not question:
        return jsonify({"error": "Soru boş olamaz."}), 400
    return jsonify(doc_rag.answer_question(question, company))
