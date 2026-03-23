from bson import ObjectId
from flask import Blueprint, jsonify, request, g

from utils.notifications import create_notification
from utils.db import init_db
from utils.security import require_auth
from utils.serialize import doc_to_json
from utils.validation import require_fields, now_utc

performance_bp = Blueprint("performance", __name__)


def compute_performance_score(tasks_completed: int, tasks_pending: int, hr_rating: int) -> int:
    tasks_completed = max(0, int(tasks_completed))
    tasks_pending = max(0, int(tasks_pending))
    hr_rating = max(0, min(100, int(hr_rating)))

    denom = max(1, tasks_completed + tasks_pending)
    completion_rate = tasks_completed / denom
    score = int(round(60 * completion_rate + 40 * (hr_rating / 100.0)))
    return max(0, min(100, score))


@performance_bp.get("")
@require_auth(roles=["HR", "Employee"])
def list_performance():
    db = init_db()
    query = {}

    if g.user["role"] == "Employee":
        query["employee_id"] = ObjectId(g.user["_id"])

    items = list(db.performance.find(query).sort("updated_at", -1).limit(200))

    emp_ids = list({p["employee_id"] for p in items if p.get("employee_id")})
    emps = {u["_id"]: u for u in db.users.find({"_id": {"$in": emp_ids}})}

    out = []
    for p in items:
        row = doc_to_json(p)
        emp = emps.get(p.get("employee_id"))
        row["employee"] = {
            "id": str(emp["_id"]),
            "name": emp.get("name", ""),
            "email": emp.get("email", ""),
        } if emp else None
        out.append(row)

    return jsonify({"performance": out})


@performance_bp.post("/update")
@require_auth(roles=["HR"])
def update_employee_performance():
    data = request.get_json(force=True, silent=True) or {}
    err = require_fields(data, ["employee_id", "hr_rating"])
    if err:
        return jsonify({"error": err}), 400

    db = init_db()
    emp = db.users.find_one({"_id": ObjectId(data["employee_id"]), "role": "Employee"})
    if not emp:
        return jsonify({"error": "Employee not found"}), 404

    completed = db.tasks.count_documents({"employee_id": emp["_id"], "status": "Completed"})
    pending = db.tasks.count_documents({"employee_id": emp["_id"], "status": "Pending"})
    hr_rating = int(max(0, min(100, int(data["hr_rating"]))))
    feedback = (data.get("feedback") or "").strip()
    score = compute_performance_score(completed, pending, hr_rating)

    doc = db.performance.find_one({"employee_id": emp["_id"]})

    payload = {
        "employee_id": emp["_id"],
        "tasks_completed": int(completed),
        "tasks_pending": int(pending),
        "hr_rating": hr_rating,
        "score": score,
        "feedback": feedback,
        "updated_at": now_utc(),
        "updated_by": ObjectId(g.user["_id"]),
    }

    if doc:
        db.performance.update_one({"_id": doc["_id"]}, {"$set": payload})
        doc = db.performance.find_one({"_id": doc["_id"]})

        create_notification(
            emp["_id"],
            "Performance Updated",
            f"Your performance score is now {doc.get('score', 0)}. Feedback: {doc.get('feedback', '') or 'No feedback'}",
            "info",
        )

        return jsonify({"performance": doc_to_json(doc)})

    payload["created_at"] = now_utc()
    res = db.performance.insert_one(payload)
    payload["_id"] = res.inserted_id

    create_notification(
        emp["_id"],
        "Performance Updated",
        f"Your performance score is now {payload.get('score', 0)}. Feedback: {payload.get('feedback', '') or 'No feedback'}",
        "info",
    )

    return jsonify({"performance": doc_to_json(payload)}), 201