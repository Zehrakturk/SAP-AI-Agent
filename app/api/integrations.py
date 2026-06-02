"""
app/api/integrations.py

Entegrasyon yonetimi API'si (MSSQL)

Tablolar:
  integrations        — id, name, description, wsdl_url, service_method, username, password, is_active
  integration_schemas — id, integration_id, schema_text, target_table, updated_at
  integration_vectors — id, integration_id, qdrant_point_id, chunk_text
  integration_params  — id, integration_id, param_name, param_type, is_required, default_value, description

Endpoint'ler:
  GET    /api/v1/integrations/             — listele
  POST   /api/v1/integrations/             — yeni ekle
  GET    /api/v1/integrations/<id>         — detay (sema + parametre + vektor bilgisi)
  PUT    /api/v1/integrations/<id>         — guncelle
  DELETE /api/v1/integrations/<id>         — devre disi birak (is_active=0)
  POST   /api/v1/integrations/<id>/schema  — sema kaydet / guncelle
  GET    /api/v1/integrations/<id>/params  — parametreleri listele
  POST   /api/v1/integrations/<id>/params  — parametre ekle
  POST   /api/v1/integrations/<id>/index   — Qdrant'a (yeniden) indexle
  GET    /api/v1/integrations/<id>/index-status — indexleme durumu
  POST   /api/v1/integrations/index-all    — tum entegrasyonlari indexle
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.services.db import get_connection, rows_as_dicts

integrations_bp = Blueprint("integrations", __name__)


# -----------------------------------------------------------------------------
# Yardimci: pyodbc Row -> dict
# -----------------------------------------------------------------------------

def _to_dict(cursor, row) -> dict:
    cols = [d[0] for d in cursor.description]
    return dict(zip(cols, row))


# =============================================================================
# LIST / CREATE
# =============================================================================

@integrations_bp.route("/", methods=["GET"])
def list_integrations():
    """
    Tum entegrasyonlari listeler.
    Liste görünümünde password ve extra_config DETAY çekilmez (hız + güvenlik).
    Detay /<id> endpoint'inden alınır.
    """
    conn   = get_connection()
    cursor = conn.cursor()
    try:
        # Yeni kolonlar mevcut mu kontrol et (geriye uyum)
        cursor.execute(
            "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'integrations'"
        )
        cols = {r[0].lower() for r in cursor.fetchall()}

        select_cols = ["id", "name", "description", "wsdl_url",
                       "service_method", "username", "is_active", "created_at"]
        if "service_type" in cols: select_cols.append("service_type")
        if "auth_type"    in cols: select_cols.append("auth_type")

        cols_sql = ", ".join(f"i.[{c}]" for c in select_cols)
        cursor.execute(f"""
            SELECT {cols_sql},
                   (SELECT COUNT(*) FROM integration_vectors iv
                    WHERE iv.integration_id = i.id) AS vector_count
            FROM   integrations i
            ORDER  BY i.id
        """)
        rows = [_to_dict(cursor, r) for r in cursor.fetchall()]
        return jsonify(rows)
    finally:
        conn.close()


@integrations_bp.route("/", methods=["POST"])
def create_integration():
    """Yeni entegrasyon ekler."""
    data = request.get_json(force=True)
    if not data.get("name"):
        return jsonify({"error": "name alani zorunlu."}), 400

    conn   = get_connection()
    cursor = conn.cursor()

    # Opsiyonel kolonlar (service_type, auth_type, extra_config) — geriye uyum
    cursor.execute(
        "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='integrations'"
    )
    have = {r[0] for r in cursor.fetchall()}

    cols = ["name", "description", "wsdl_url", "service_method", "username", "password", "is_active"]
    vals = [
        data["name"],
        data.get("description", ""),
        data.get("wsdl_url", ""),
        data.get("service_method", ""),
        data.get("username", ""),
        data.get("password", ""),
        int(data.get("is_active", 1)),
    ]
    if "service_type" in have and data.get("service_type"):
        cols.append("service_type"); vals.append(data["service_type"])
    if "auth_type" in have and data.get("auth_type"):
        cols.append("auth_type"); vals.append(data["auth_type"])
    if "extra_config" in have and data.get("extra_config") is not None:
        import json as _json
        cols.append("extra_config")
        vals.append(_json.dumps(data["extra_config"], ensure_ascii=False))

    placeholders = ",".join("?" * len(cols))
    cursor.execute(
        f"INSERT INTO integrations ({', '.join(cols)}) "
        f"OUTPUT INSERTED.id VALUES ({placeholders})",
        vals,
    )
    new_id = int(cursor.fetchone()[0])
    conn.commit()
    conn.close()
    return jsonify({"id": new_id, "message": "Entegrasyon olusturuldu."}), 201


# =============================================================================
# GET / UPDATE / DELETE
# =============================================================================

@integrations_bp.route("/<int:integration_id>", methods=["GET"])
def get_integration(integration_id):
    """Detay: entegrasyon + semalari + parametreleri + indexleme durumu."""
    conn   = get_connection()
    cursor = conn.cursor()

    # Ana kayit
    cursor.execute("SELECT * FROM integrations WHERE id = ?", (integration_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Bulunamadi."}), 404
    result = _to_dict(cursor, row)

    # Semalar
    cursor.execute(
        "SELECT * FROM integration_schemas WHERE integration_id = ?",
        (integration_id,),
    )
    result["schemas"] = [_to_dict(cursor, r) for r in cursor.fetchall()]

    # Parametreler
    cursor.execute(
        "SELECT * FROM integration_params WHERE integration_id = ? ORDER BY id",
        (integration_id,),
    )
    result["params"] = [_to_dict(cursor, r) for r in cursor.fetchall()]

    # Vektor / index bilgisi
    cursor.execute(
        "SELECT COUNT(*) AS vector_count FROM integration_vectors WHERE integration_id = ?",
        (integration_id,),
    )
    result["vector_count"] = cursor.fetchone()[0]

    conn.close()
    return jsonify(result)


@integrations_bp.route("/<int:integration_id>", methods=["PUT"])
def update_integration(integration_id):
    """Baglanti bilgilerini gunceller."""
    data    = request.get_json(force=True)
    allowed = ["name", "description", "wsdl_url", "service_method",
               "username", "password", "is_active"]

    fields = [f"{k} = ?" for k in allowed if k in data]
    values = [data[k] for k in allowed if k in data]

    if not fields:
        return jsonify({"error": "Guncellenecek alan yok."}), 400

    values.append(integration_id)
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"UPDATE integrations SET {', '.join(fields)} WHERE id = ?", values
    )
    conn.commit()
    conn.close()
    return jsonify({"message": "Guncellendi."})


@integrations_bp.route("/<int:integration_id>", methods=["DELETE"])
def delete_integration(integration_id):
    """Entegrasyonu devre disi birakir (soft delete)."""
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE integrations SET is_active = 0 WHERE id = ?", (integration_id,)
    )
    conn.commit()
    conn.close()
    return jsonify({"message": "Entegrasyon devre disi birakildi."})


# =============================================================================
# SCHEMA
# =============================================================================

@integrations_bp.route("/<int:integration_id>/schema", methods=["POST"])
def upsert_schema(integration_id):
    """
    Entegrasyon icin sema metni kaydeder veya gunceller.
    Body: { "target_table": "shipments", "schema_text": "Kolon aciklamalari..." }
    """
    data         = request.get_json(force=True)
    target_table = (data.get("target_table") or "").strip()
    schema_text  = (data.get("schema_text")  or "").strip()

    if not target_table or not schema_text:
        return jsonify({"error": "target_table ve schema_text zorunlu."}), 400

    conn   = get_connection()
    cursor = conn.cursor()

    # Var mi?
    cursor.execute(
        "SELECT id FROM integration_schemas WHERE integration_id = ? AND target_table = ?",
        (integration_id, target_table),
    )
    existing = cursor.fetchone()

    if existing:
        cursor.execute(
            "UPDATE integration_schemas SET schema_text = ?, updated_at = GETDATE() "
            "WHERE integration_id = ? AND target_table = ?",
            (schema_text, integration_id, target_table),
        )
    else:
        cursor.execute(
            "INSERT INTO integration_schemas (integration_id, target_table, schema_text) "
            "VALUES (?, ?, ?)",
            (integration_id, target_table, schema_text),
        )

    conn.commit()
    conn.close()
    return jsonify({
        "message": "Sema kaydedildi. Qdrant'a indexlemek icin /index endpoint'ini cagirin."
    })


# =============================================================================
# PARAMS
# =============================================================================

@integrations_bp.route("/<int:integration_id>/params", methods=["GET"])
def list_params(integration_id):
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM integration_params WHERE integration_id = ? ORDER BY id",
        (integration_id,),
    )
    rows = [_to_dict(cursor, r) for r in cursor.fetchall()]
    conn.close()
    return jsonify(rows)


@integrations_bp.route("/<int:integration_id>/params", methods=["POST"])
def add_param(integration_id):
    """
    Body: { "param_name": "I_BEGDA", "param_type": "date",
            "is_required": true, "default_value": "", "description": "..." }
    """
    data       = request.get_json(force=True)
    param_name = (data.get("param_name") or "").strip()
    if not param_name:
        return jsonify({"error": "param_name zorunlu."}), 400

    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO integration_params
            (integration_id, param_name, param_type, is_required, default_value, description)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        integration_id,
        param_name,
        data.get("param_type", "string"),
        int(data.get("is_required", 0)),
        data.get("default_value", ""),
        data.get("description", ""),
    ))
    cursor.execute("SELECT SCOPE_IDENTITY() AS id")
    new_id = int(cursor.fetchone()[0])
    conn.commit()
    conn.close()
    return jsonify({"id": new_id, "message": "Parametre eklendi."}), 201


# =============================================================================
# QDRANT INDEX
# =============================================================================

@integrations_bp.route("/<int:integration_id>/index", methods=["POST"])
def index_to_qdrant(integration_id):
    """Bu entegrasyonun semalarini Qdrant'a (yeniden) indexler."""
    from app.services.qdrant_indexer import index_integration
    try:
        count = index_integration(integration_id)
        return jsonify({"message": f"{count} chunk Qdrant'a indexlendi.", "count": count})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@integrations_bp.route("/<int:integration_id>/index-status", methods=["GET"])
def index_status(integration_id):
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM integration_vectors WHERE integration_id = ?",
        (integration_id,),
    )
    count = cursor.fetchone()[0]
    conn.close()
    return jsonify({"integration_id": integration_id, "vector_count": count})


@integrations_bp.route("/index-all", methods=["POST"])
def index_all():
    """Tum aktif entegrasyonlari Qdrant'a indexler."""
    from app.services.qdrant_indexer import index_all_integrations
    try:
        result = index_all_integrations()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =============================================================================
# ON-DEMAND FETCH
# =============================================================================

@integrations_bp.route("/<int:integration_id>/fetch", methods=["POST"])
def fetch_on_demand(integration_id):
    """
    Entegrasyonu belirtilen parametrelerle çalıştırır, MSSQL'e yazar.
    Body: { "start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD", "force": false }
    """
    from app.services.fetchers import fetch_integration as _fetch
    data  = request.get_json(force=True) or {}
    force = data.get("force", False)
    extracted = {
        "start_date": data.get("start_date"),
        "end_date"  : data.get("end_date"),
    }
    try:
        result = _fetch(integration_id, extracted, force=force)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =============================================================================
# TEMPLATES (Sprint 2.1) — Hazır konnektör şablonları
# =============================================================================

_INTEGRATION_TEMPLATES = [
    {
        "key"         : "sap_soap_shipments",
        "name"        : "SAP SOAP — Sevkiyat / Lojistik",
        "category"    : "SAP",
        "icon"        : "🚚",
        "description" : "SAP RFC/SOAP üzerinden sevkiyat servisi. ISTART_DATE / IFINISH_DATE parametreli.",
        "fields": {
            "service_type"  : "SOAP",
            "auth_type"     : "BASIC",
            "service_method": "ZGetShipments",
            "wsdl_url"      : "http://<sap-host>:8000/sap/bc/srt/wsdl/...?sap-client=100",
            "username"      : "",
            "extra_config"  : {"date_format": "iso"},
        },
        "params": [
            {"param_name": "ISTART_DATE",  "param_type": "date10", "is_required": True,  "default_value": "", "description": "Başlangıç tarihi (YYYY-MM-DD)"},
            {"param_name": "IFINISH_DATE", "param_type": "date10", "is_required": True,  "default_value": "", "description": "Bitiş tarihi (YYYY-MM-DD)"},
        ],
    },
    {
        "key"         : "rest_sales_bearer",
        "name"        : "REST API — Satış Verisi (Bearer Token)",
        "category"    : "REST",
        "icon"        : "🛒",
        "description" : "Generic REST GET endpoint. Bearer token ile satış/sipariş çekme şablonu.",
        "fields": {
            "service_type"  : "REST",
            "auth_type"     : "BEARER",
            "wsdl_url"      : "https://erp.example.com/api/sales",
            "service_method": "",
            "username"      : "",
            "extra_config"  : {
                "http_method"   : "GET",
                "data_key"      : "items",
                "param_template": {"from": "{start_date}", "to": "{end_date}"}
            },
        },
        "params": [
            {"param_name": "start_date", "param_type": "date", "is_required": True, "default_value": "", "description": "Başlangıç"},
            {"param_name": "end_date",   "param_type": "date", "is_required": True, "default_value": "", "description": "Bitiş"},
        ],
    },
    {
        "key"         : "rest_crm_apikey",
        "name"        : "REST API — CRM (API Key)",
        "category"    : "CRM",
        "icon"        : "👥",
        "description" : "HubSpot/Pipedrive benzeri CRM. Header'da API key, JSON list response.",
        "fields": {
            "service_type"  : "REST",
            "auth_type"     : "APIKEY",
            "wsdl_url"      : "https://api.hubapi.com/crm/v3/objects/deals",
            "service_method": "",
            "username"      : "",
            "extra_config"  : {
                "http_method"   : "GET",
                "data_key"      : "results",
                "api_key_header": "Authorization",
                "api_key_prefix": "Bearer "
            },
        },
        "params": [
            {"param_name": "limit", "param_type": "int", "is_required": False, "default_value": "100", "description": "Sayfa boyutu"},
        ],
    },
    {
        "key"         : "odata_sap_sd",
        "name"        : "OData — SAP S/4 Sales (SD)",
        "category"    : "SAP",
        "icon"        : "💼",
        "description" : "SAP S/4HANA OData servisi (örn. API_SALES_ORDER). $filter ile tarih aralığı.",
        "fields": {
            "service_type"  : "ODATA",
            "auth_type"     : "BASIC",
            "wsdl_url"      : "https://<s4-host>/sap/opu/odata/sap/API_SALES_ORDER_SRV/A_SalesOrder",
            "service_method": "",
            "username"      : "",
            "extra_config"  : {
                "data_key": "d.results",
                "filter_template": "CreationDate ge datetime'{start_date}T00:00:00' and CreationDate le datetime'{end_date}T23:59:59'"
            },
        },
        "params": [
            {"param_name": "start_date", "param_type": "date", "is_required": True, "default_value": "", "description": "Oluşturma başlangıcı"},
            {"param_name": "end_date",   "param_type": "date", "is_required": True, "default_value": "", "description": "Oluşturma bitişi"},
        ],
    },
    {
        "key"         : "custom_rest_blank",
        "name"        : "Boş — Özel REST",
        "category"    : "Custom",
        "icon"        : "🔧",
        "description" : "Sıfırdan başla. Tüm alanları manuel doldur.",
        "fields": {
            "service_type": "REST", "auth_type": "NONE", "wsdl_url": "",
            "service_method": "", "username": "", "extra_config": {},
        },
        "params": [],
    },
]


@integrations_bp.route("/templates", methods=["GET"])
def list_templates():
    """Hazır konnektör şablonlarını listeler — UI dropdown'ı için."""
    return jsonify(_INTEGRATION_TEMPLATES)


@integrations_bp.route("/<int:integration_id>/fetch-log", methods=["GET"])
def fetch_log(integration_id):
    """Bu entegrasyon için daha önce çekilmiş tarih aralıklarını listeler."""
    conn   = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT param_hash, params_json, rows_written, fetched_at
            FROM   fetch_log
            WHERE  integration_id = ?
            ORDER  BY fetched_at DESC
        """, (integration_id,))
        rows = [_to_dict(cursor, r) for r in cursor.fetchall()]
        return jsonify(rows)
    except Exception:
        return jsonify([])
    finally:
        conn.close()
