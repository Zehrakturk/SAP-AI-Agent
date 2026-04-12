
from flask import Blueprint, request, jsonify
from app.models.store import USERS

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["POST"])
def login():
    data     = request.get_json(force=True)
    username = data.get("username", "").strip()
    password = data.get("password", "")

    user = next((u for u in USERS if u["username"] == username and u["password"] == password), None)

    if not user:
        return jsonify({"detail": "Invalid username or password."}), 401

    # In production: issue a real JWT here.
    # For demo we return a simple token string.
    token = f"demo-token-{user['id']}-{user['role']}"

    return jsonify({
        "access_token": token,
        "token_type":   "bearer",
        "user": {
            "id":         user["id"],
            "username":   user["username"],
            "name":       user["name"],
            "role":       user["role"],
            "department": user["department"],
        },
    })


@auth_bp.route("/logout", methods=["POST"])
def logout():
    return jsonify({"message": "Logged out."})


@auth_bp.route("/me", methods=["GET"])
def me():
    """Decode token and return current user (simplified demo)."""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token.startswith("demo-token-"):
        return jsonify({"detail": "Unauthorized"}), 401

    try:
        user_id = int(token.split("-")[2])
    except (IndexError, ValueError):
        return jsonify({"detail": "Invalid token"}), 401

    user = next((u for u in USERS if u["id"] == user_id), None)
    if not user:
        return jsonify({"detail": "User not found"}), 404

    return jsonify({
        "id":         user["id"],
        "username":   user["username"],
        "name":       user["name"],
        "role":       user["role"],
        "department": user["department"],
    })