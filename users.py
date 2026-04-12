from flask import Blueprint, request, jsonify
from datetime import date
from app.models.store import USERS

users_bp = Blueprint("users", __name__)


def _safe(user: dict) -> dict:
    """Return user dict without password."""
    return {k: v for k, v in user.items() if k != "password"}


@users_bp.route("/", methods=["GET"])
def list_users():
    role = request.args.get("role", "")
    dept = request.args.get("department", "")
    q    = request.args.get("q", "").lower()

    result = USERS
    if role:
        result = [u for u in result if u["role"] == role]
    if dept:
        result = [u for u in result if u["department"] == dept]
    if q:
        result = [u for u in result if q in u["username"].lower() or q in u["name"].lower()]

    return jsonify([_safe(u) for u in result])


@users_bp.route("/<int:user_id>", methods=["GET"])
def get_user(user_id):
    user = next((u for u in USERS if u["id"] == user_id), None)
    if not user:
        return jsonify({"detail": "User not found"}), 404
    return jsonify(_safe(user))


@users_bp.route("/", methods=["POST"])
def create_user():
    data = request.get_json(force=True)

    required = ["username", "name", "role", "department"]
    for field in required:
        if not data.get(field):
            return jsonify({"detail": f"'{field}' is required."}), 400

    if any(u["username"] == data["username"] for u in USERS):
        return jsonify({"detail": "Username already exists."}), 409

    new_user = {
        "id":         max(u["id"] for u in USERS) + 1,
        "username":   data["username"],
        "password":   data.get("password", "changeme"),
        "name":       data["name"],
        "role":       data["role"],
        "department": data["department"],
        "status":     data.get("status", "active"),
        "created_at": str(date.today()),
        "last_login": "Never",
    }
    USERS.append(new_user)
    return jsonify(_safe(new_user)), 201


@users_bp.route("/<int:user_id>", methods=["PUT"])
def update_user(user_id):
    user = next((u for u in USERS if u["id"] == user_id), None)
    if not user:
        return jsonify({"detail": "User not found"}), 404

    data = request.get_json(force=True)
    for field in ["name", "role", "department", "status"]:
        if field in data:
            user[field] = data[field]

    return jsonify(_safe(user))


@users_bp.route("/<int:user_id>", methods=["DELETE"])
def delete_user(user_id):
    global USERS
    user = next((u for u in USERS if u["id"] == user_id), None)
    if not user:
        return jsonify({"detail": "User not found"}), 404
    USERS = [u for u in USERS if u["id"] != user_id]
    return jsonify({"message": f"User {user_id} deleted."})


@users_bp.route("/<int:user_id>/role", methods=["PATCH"])
def assign_role(user_id):
    user = next((u for u in USERS if u["id"] == user_id), None)
    if not user:
        return jsonify({"detail": "User not found"}), 404
    data = request.get_json(force=True)
    user["role"] = data.get("role", user["role"])
    return jsonify(_safe(user))


@users_bp.route("/<int:user_id>/department", methods=["PATCH"])
def assign_department(user_id):
    user = next((u for u in USERS if u["id"] == user_id), None)
    if not user:
        return jsonify({"detail": "User not found"}), 404
    data = request.get_json(force=True)
    user["department"] = data.get("department", user["department"])
    return jsonify(_safe(user))