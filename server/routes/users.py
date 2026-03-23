from bson import ObjectId
from flask import Blueprint, jsonify, request

from utils.db import init_db
from utils.security import require_auth
from utils.serialize import doc_to_json

users_bp = Blueprint("users", __name__)


@users_bp.get("")
@require_auth(roles=["HR"])
def list_users():
    db = init_db()
    role = (request.args.get("role") or "").strip()
    q = (request.args.get("q") or "").strip().lower()
    query = {}
    if role:
        query["role"] = role
    if q:
        query["$or"] = [{"email": {"$regex": q}}, {"name": {"$regex": q}}]

    users = list(db.users.find(query).sort("created_at", -1).limit(300))
    out = []
    for u in users:
        j = doc_to_json(u)
        j.pop("password_hash", None)
        out.append(j)
    return jsonify({"users": out})


@users_bp.get("/<user_id>")
@require_auth(roles=["HR"])
def get_user(user_id):
    db = init_db()
    u = db.users.find_one({"_id": ObjectId(user_id)})
    if not u:
        return jsonify({"error": "User not found"}), 404
    j = doc_to_json(u)
    j.pop("password_hash", None)
    return jsonify({"user": j})

