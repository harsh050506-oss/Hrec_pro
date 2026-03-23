from bson import ObjectId
from flask import Blueprint, jsonify, request, g

from models.constants import TASK_STATUS
from utils.db import init_db
from utils.security import require_auth
from utils.serialize import doc_to_json
from utils.validation import require_fields, now_utc

tasks_bp = Blueprint("tasks", __name__)


@tasks_bp.get("")
@require_auth(roles=["HR", "Employee"])
def list_tasks():
    db = init_db()
    query = {}
    if g.user["role"] == "Employee":
        query["employee_id"] = ObjectId(g.user["_id"])

    status = (request.args.get("status") or "").strip()
    if status in TASK_STATUS:
        query["status"] = status

    items = list(db.tasks.find(query).sort("created_at", -1).limit(300))

    emp_ids = list({t["employee_id"] for t in items})
    emps = {u["_id"]: u for u in db.users.find({"_id": {"$in": emp_ids}})}
    out = []
    for t in items:
        row = doc_to_json(t)
        emp = emps.get(t["employee_id"])
        row["employee"] = {"id": str(emp["_id"]), "email": emp["email"], "name": emp.get("name", "")} if emp else None
        out.append(row)
    return jsonify({"tasks": out})


@tasks_bp.post("")
@require_auth(roles=["HR"])
def create_task():
    data = request.get_json(force=True, silent=True) or {}
    err = require_fields(data, ["employee_id", "title"])
    if err:
        return jsonify({"error": err}), 400

    db = init_db()
    emp = db.users.find_one({"_id": ObjectId(data["employee_id"]), "role": "Employee"})
    if not emp:
        return jsonify({"error": "Employee not found"}), 404

    task = {
        "employee_id": emp["_id"],
        "title": (data["title"] or "").strip(),
        "description": (data.get("description") or "").strip(),
        "status": "Pending",
        "assigned_by": ObjectId(g.user["_id"]),
        "hr_feedback": "",
        "created_at": now_utc(),
        "updated_at": now_utc(),
    }
    res = db.tasks.insert_one(task)
    task["_id"] = res.inserted_id
    return jsonify({"task": doc_to_json(task)}), 201


@tasks_bp.patch("/<task_id>")
@require_auth(roles=["HR", "Employee"])
def update_task(task_id):
    data = request.get_json(force=True, silent=True) or {}
    db = init_db()
    task = db.tasks.find_one({"_id": ObjectId(task_id)})
    if not task:
        return jsonify({"error": "Task not found"}), 404

    # Employees can only update their own tasks and only status
    if g.user["role"] == "Employee":
        if str(task["employee_id"]) != g.user["_id"]:
            return jsonify({"error": "Forbidden"}), 403
        status = (data.get("status") or "").strip()
        if status and status in TASK_STATUS:
            db.tasks.update_one({"_id": task["_id"]}, {"$set": {"status": status, "updated_at": now_utc()}})
        else:
            return jsonify({"error": "Invalid status"}), 400
    else:
        updates = {}
        if "title" in data and isinstance(data["title"], str):
            updates["title"] = data["title"].strip()
        if "description" in data and isinstance(data["description"], str):
            updates["description"] = data["description"].strip()
        if "status" in data and (data["status"] or "").strip() in TASK_STATUS:
            updates["status"] = data["status"].strip()
        if "hr_feedback" in data and isinstance(data["hr_feedback"], str):
            updates["hr_feedback"] = data["hr_feedback"].strip()
        if updates:
            updates["updated_at"] = now_utc()
            db.tasks.update_one({"_id": task["_id"]}, {"$set": updates})

    task = db.tasks.find_one({"_id": ObjectId(task_id)})
    return jsonify({"task": doc_to_json(task)})