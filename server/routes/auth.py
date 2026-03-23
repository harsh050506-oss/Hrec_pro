from flask import Blueprint, request, jsonify
from pymongo.errors import DuplicateKeyError

from utils.db import init_db
from utils.security import hash_password, verify_password, create_jwt

auth_bp = Blueprint("auth", __name__)


def _normalize_role(role: str) -> str:
    role = (role or "Candidate").strip()
    if role.lower() == "hr":
        return "HR"
    if role.lower() == "employee":
        return "Employee"
    return "Candidate"


@auth_bp.post("/register")
def register():
    data = request.get_json(force=True, silent=True) or {}

    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "").strip()
    role = _normalize_role(data.get("role") or "Candidate")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    db = init_db()

    user_doc = {
        "name": name,
        "email": email,
        "password": hash_password(password),
        "role": role,
    }

    try:
        result = db.users.insert_one(user_doc)
    except DuplicateKeyError:
        return jsonify({"error": "Email already registered"}), 409
    except Exception as e:
        return jsonify({"error": f"Registration failed: {str(e)}"}), 500

    created = db.users.find_one({"_id": result.inserted_id})

    token = create_jwt(str(created["_id"]), created["role"])

    return jsonify(
        {
            "token": token,
            "user": {
                "id": str(created["_id"]),
                "name": created.get("name", ""),
                "email": created.get("email", ""),
                "role": created.get("role", "Candidate"),
            },
        }
    ), 201


@auth_bp.post("/login")
def login():
    data = request.get_json(force=True, silent=True) or {}

    email = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "").strip()

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    db = init_db()
    user = db.users.find_one({"email": email})

    if not user:
        return jsonify({"error": "Invalid email or password"}), 401

    # Google-created account
    if not user.get("password"):
        return jsonify({"error": "This account uses Google login. Please continue with Google."}), 401

    if not verify_password(password, user["password"]):
        return jsonify({"error": "Invalid email or password"}), 401

    token = create_jwt(str(user["_id"]), user["role"])

    return jsonify(
        {
            "token": token,
            "user": {
                "id": str(user["_id"]),
                "name": user.get("name", ""),
                "email": user.get("email", ""),
                "role": user.get("role", "Candidate"),
            },
        }
    ), 200