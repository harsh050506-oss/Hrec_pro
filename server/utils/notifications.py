from datetime import datetime
from bson import ObjectId

from .db import init_db


def create_notification(user_id, title, message, ntype="info"):
    db = init_db()

    notification = {
        "user_id": ObjectId(user_id) if isinstance(user_id, str) else user_id,
        "title": str(title or "").strip(),
        "message": str(message or "").strip(),
        "type": str(ntype or "info").strip(),
        "read": False,
        "created_at": datetime.utcnow(),
    }

    db.notifications.insert_one(notification)
    return notification