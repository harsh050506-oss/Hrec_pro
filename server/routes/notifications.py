import smtplib
from email.message import EmailMessage

from bson import ObjectId
from flask import Blueprint, jsonify, request, g

from utils.db import init_db
from utils.security import require_auth
from utils.serialize import doc_to_json
from utils.validation import require_fields, now_utc

notifications_bp = Blueprint("notifications", __name__)


def _smtp_send_placeholder(to_email: str, subject: str, body: str) -> tuple[bool, str]:
    """
    SMTP placeholder: set env vars to enable:
    - HREC_SMTP_HOST, HREC_SMTP_PORT, HREC_SMTP_USER, HREC_SMTP_PASS, HREC_SMTP_FROM
    """
    import os

    host = os.getenv("HREC_SMTP_HOST", "")
    port = int(os.getenv("HREC_SMTP_PORT", "587"))
    user = os.getenv("HREC_SMTP_USER", "")
    pw = os.getenv("HREC_SMTP_PASS", "")
    from_email = os.getenv("HREC_SMTP_FROM", user)

    if not host or not user or not pw or not from_email:
        return False, "SMTP not configured (placeholder)"

    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        with smtplib.SMTP(host, port, timeout=10) as s:
            s.starttls()
            s.login(user, pw)
            s.send_message(msg)
        return True, "sent"
    except Exception as e:
        return False, str(e)


@notifications_bp.get("")
@require_auth(roles=["HR", "Candidate", "Employee"])
def list_notifications():
    db = init_db()
    items = list(
        db.notifications
        .find({"user_id": ObjectId(g.user["_id"])})
        .sort("created_at", -1)
        .limit(200)
    )
    return jsonify({"notifications": [doc_to_json(n) for n in items]})


@notifications_bp.post("")
@require_auth(roles=["HR"])
def create_notification_route():
    data = request.get_json(force=True, silent=True) or {}
    err = require_fields(data, ["user_id", "title", "message"])
    if err:
        return jsonify({"error": err}), 400

    db = init_db()
    user = db.users.find_one({"_id": ObjectId(data["user_id"])})
    if not user:
        return jsonify({"error": "User not found"}), 404

    doc = {
        "user_id": user["_id"],
        "title": (data["title"] or "").strip(),
        "message": (data["message"] or "").strip(),
        "kind": (data.get("kind") or data.get("type") or "info").strip(),
        "read": False,
        "created_at": now_utc(),
    }

    res = db.notifications.insert_one(doc)
    doc["_id"] = res.inserted_id

    if data.get("send_email"):
        ok, detail = _smtp_send_placeholder(user["email"], doc["title"], doc["message"])
        db.notifications.update_one(
            {"_id": doc["_id"]},
            {"$set": {"email": {"attempted": True, "ok": ok, "detail": detail}}},
        )

    return jsonify({"notification": doc_to_json(doc)}), 201


@notifications_bp.post("/<notif_id>/read")
@require_auth(roles=["HR", "Candidate", "Employee"])
def mark_read(notif_id):
    db = init_db()
    doc = db.notifications.find_one({"_id": ObjectId(notif_id)})
    if not doc or str(doc["user_id"]) != g.user["_id"]:
        return jsonify({"error": "Not found"}), 404

    db.notifications.update_one({"_id": doc["_id"]}, {"$set": {"read": True}})
    doc = db.notifications.find_one({"_id": doc["_id"]})

    return jsonify({"notification": doc_to_json(doc)})