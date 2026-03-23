from utils.notifications import create_notification
from bson import ObjectId
from flask import Blueprint, jsonify, request, g

from models.constants import APPLICATION_STATUS
from utils.ai_resume import tfidf_match_score
from utils.db import init_db
from utils.security import require_auth
from utils.serialize import doc_to_json
from utils.validation import require_fields, now_utc

applications_bp = Blueprint("applications", __name__)


@applications_bp.get("")
@require_auth(roles=["HR", "Candidate"])
def list_applications():
    db = init_db()

    role = g.user["role"]
    query = {}
    if role == "Candidate":
        query["candidate_id"] = ObjectId(g.user["_id"])

    status = (request.args.get("status") or "").strip()
    if status in APPLICATION_STATUS:
        query["status"] = status

    job_id = (request.args.get("job_id") or "").strip()
    if job_id:
        query["job_id"] = ObjectId(job_id)

    min_score = (request.args.get("min_score") or "").strip()
    if min_score.isdigit():
        query["resume_score"] = {"$gte": int(min_score)}

    apps = list(db.applications.find(query).sort("created_at", -1).limit(300))

    job_ids = list({a["job_id"] for a in apps})
    cand_ids = list({a["candidate_id"] for a in apps})
    jobs = {j["_id"]: j for j in db.jobs.find({"_id": {"$in": job_ids}})}
    users = {u["_id"]: u for u in db.users.find({"_id": {"$in": cand_ids}})}

    out = []
    skill = (request.args.get("skill") or "").strip().lower()
    for a in apps:
      row = doc_to_json(a)
      job = jobs.get(a["job_id"])
      cand = users.get(a["candidate_id"])
      row["job"] = doc_to_json(job) if job else None
      row["candidate"] = {
          "id": str(cand["_id"]),
          "email": cand["email"],
          "name": cand.get("name", ""),
      } if cand else None

      if skill:
          job_skills = [s.lower() for s in (job or {}).get("skills", [])]
          if skill not in job_skills:
              continue

      out.append(row)

    return jsonify({"applications": out})


@applications_bp.post("")
@require_auth(roles=["Candidate"])
def apply():
    data = request.get_json(force=True, silent=True) or {}
    err = require_fields(data, ["job_id"])
    if err:
        return jsonify({"error": err}), 400

    db = init_db()
    job = db.jobs.find_one({"_id": ObjectId(data["job_id"])})
    if not job:
        return jsonify({"error": "Job not found"}), 404

    application = {
        "job_id": job["_id"],
        "candidate_id": ObjectId(g.user["_id"]),
        "status": "Pending",
        "resume_id": None,
        "resume_score": 0,
        "interview": {"scheduled_at": None, "notes": "", "score": None},
        "created_at": now_utc(),
        "updated_at": now_utc(),
    }

    try:
        res = db.applications.insert_one(application)
    except Exception:
        return jsonify({"error": "Already applied for this job"}), 409

    application["_id"] = res.inserted_id
    return jsonify({"application": doc_to_json(application)}), 201


@applications_bp.patch("/<app_id>/status")
@require_auth(roles=["HR"])
def set_status(app_id):
    data = request.get_json(force=True, silent=True) or {}
    status = (data.get("status") or "").strip()

    if status not in APPLICATION_STATUS:
        return jsonify({"error": "Invalid status"}), 400

    db = init_db()

    app = db.applications.find_one({"_id": ObjectId(app_id)})
    if not app:
        return jsonify({"error": "Application not found"}), 404

    db.applications.update_one(
        {"_id": ObjectId(app_id)},
        {"$set": {"status": status, "updated_at": now_utc()}},
    )

    app = db.applications.find_one({"_id": ObjectId(app_id)})

    candidate_id = app.get("candidate_id")
    if candidate_id:
        if status == "Accepted":
            create_notification(
                candidate_id,
                "Application Accepted 🎉",
                "Congratulations! Your application has been accepted.",
                "success",
            )
        elif status == "Rejected":
            create_notification(
                candidate_id,
                "Application Rejected ❌",
                "Your application was not selected this time.",
                "danger",
            )
        elif status == "Pending":
            create_notification(
                candidate_id,
                "Application Update",
                "Your application is currently under review.",
                "info",
            )

    return jsonify({"application": doc_to_json(app)})


@applications_bp.post("/<app_id>/schedule")
@require_auth(roles=["HR"])
def schedule_interview(app_id):
    data = request.get_json(force=True, silent=True) or {}
    err = require_fields(data, ["scheduled_at"])
    if err:
        return jsonify({"error": err}), 400

    db = init_db()

    app = db.applications.find_one({"_id": ObjectId(app_id)})
    if not app:
        return jsonify({"error": "Application not found"}), 404

    db.applications.update_one(
        {"_id": ObjectId(app_id)},
        {"$set": {"interview.scheduled_at": data["scheduled_at"], "updated_at": now_utc()}},
    )

    app = db.applications.find_one({"_id": ObjectId(app_id)})

    candidate_id = app.get("candidate_id")
    if candidate_id:
        create_notification(
            candidate_id,
            "Interview Scheduled 📅",
            f"Your interview is scheduled at {data['scheduled_at']}",
            "info",
        )

    return jsonify({"application": doc_to_json(app)})


@applications_bp.post("/<app_id>/recompute-score")
@require_auth(roles=["HR"])
def recompute_score(app_id):
    db = init_db()
    app = db.applications.find_one({"_id": ObjectId(app_id)})
    if not app:
        return jsonify({"error": "Application not found"}), 404
    if not app.get("resume_id"):
        return jsonify({"error": "No resume attached"}), 400

    resume = db.resumes.find_one({"_id": ObjectId(app["resume_id"])})
    job = db.jobs.find_one({"_id": app["job_id"]})
    if not resume or not job:
        return jsonify({"error": "Resume/job missing"}), 400

    score = tfidf_match_score(
        resume.get("text", ""),
        f"{job.get('title','')}\n{job.get('description','')}\n{' '.join(job.get('skills',[]))}"
    )

    db.applications.update_one(
        {"_id": ObjectId(app_id)},
        {"$set": {"resume_score": score, "updated_at": now_utc()}},
    )

    app = db.applications.find_one({"_id": ObjectId(app_id)})
    return jsonify({"application": doc_to_json(app)})