from bson import ObjectId
from flask import Blueprint, jsonify, request, g

from utils.db import init_db
from utils.security import require_auth
from utils.serialize import doc_to_json
from utils.validation import require_fields, as_list, now_utc

jobs_bp = Blueprint("jobs", __name__)


@jobs_bp.get("")
@require_auth(roles=["HR", "Candidate", "Employee"])
def list_jobs():
    db = init_db()
    q = (request.args.get("q") or "").strip()
    query = {}
    if q:
        query = {"$text": {"$search": q}}
    jobs = list(db.jobs.find(query).sort("created_at", -1).limit(200))
    return jsonify({"jobs": [doc_to_json(j) for j in jobs]})


@jobs_bp.post("")
@require_auth(roles=["HR"])
def create_job():
    data = request.get_json(force=True, silent=True) or {}
    err = require_fields(data, ["title", "description"])
    if err:
        return jsonify({"error": err}), 400

    job = {
        "title": (data["title"] or "").strip(),
        "description": (data["description"] or "").strip(),
        "skills": as_list(data.get("skills")),
        "created_by": ObjectId(g.user["_id"]),
        "created_at": now_utc(),
    }

    db = init_db()
    res = db.jobs.insert_one(job)
    job["_id"] = res.inserted_id
    return jsonify({"job": doc_to_json(job)}), 201


@jobs_bp.get("/<job_id>")
@require_auth(roles=["HR", "Candidate", "Employee"])
def get_job(job_id):
    db = init_db()
    job = db.jobs.find_one({"_id": ObjectId(job_id)})
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify({"job": doc_to_json(job)})


@jobs_bp.patch("/<job_id>")
@require_auth(roles=["HR"])
def update_job(job_id):
    data = request.get_json(force=True, silent=True) or {}
    updates = {}
    for k in ["title", "description"]:
        if k in data and isinstance(data[k], str):
            updates[k] = data[k].strip()
    if "skills" in data:
        updates["skills"] = as_list(data.get("skills"))

    if not updates:
        return jsonify({"error": "No updates"}), 400

    db = init_db()
    db.jobs.update_one({"_id": ObjectId(job_id)}, {"$set": updates})
    job = db.jobs.find_one({"_id": ObjectId(job_id)})
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify({"job": doc_to_json(job)})


@jobs_bp.delete("/<job_id>")
@require_auth(roles=["HR"])
def delete_job(job_id):
    db = init_db()
    res = db.jobs.delete_one({"_id": ObjectId(job_id)})
    if res.deleted_count == 0:
        return jsonify({"error": "Job not found"}), 404
    return jsonify({"ok": True})

