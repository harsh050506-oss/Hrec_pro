import os
from datetime import datetime, timedelta
from functools import wraps

import bcrypt
import jwt
from bson import ObjectId
from flask import request, jsonify, g

from .db import init_db

SECRET_KEY = os.getenv("HREC_SECRET_KEY", "dev-secret")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    if not hashed:
        return False
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_token(user_id: str, role: str) -> str:
    payload = {
        "user_id": user_id,
        "role": role,
        "exp": datetime.utcnow() + timedelta(days=1),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def create_jwt(user_id: str, role: str) -> str:
    return create_token(user_id, role)


def decode_token(token: str):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def require_auth(roles=None):
    roles = roles or []

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            auth_header = request.headers.get("Authorization", "").strip()

            if not auth_header.startswith("Bearer "):
                return jsonify({"error": "Missing or invalid Authorization header"}), 401

            raw_token = auth_header.split(" ", 1)[1].strip()
            payload = decode_token(raw_token)
            if not payload:
                return jsonify({"error": "Invalid or expired token"}), 401

            user_id = str(payload.get("user_id") or "").strip()
            role = str(payload.get("role") or "").strip()

            if not user_id:
                return jsonify({"error": "Invalid token payload"}), 401

            if roles and role not in roles:
                return jsonify({"error": "Forbidden"}), 403

            db = init_db()
            user_doc = db.users.find_one({"_id": ObjectId(user_id)})
            if not user_doc:
                return jsonify({"error": "User not found"}), 401

            g.user = {
                "_id": str(user_doc["_id"]),
                "name": user_doc.get("name", ""),
                "email": user_doc.get("email", ""),
                "role": user_doc.get("role", role),
            }

            return fn(*args, **kwargs)

        return wrapper

    return decorator