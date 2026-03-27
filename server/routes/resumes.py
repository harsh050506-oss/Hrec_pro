import os
import uuid

from bson import ObjectId
from flask import Blueprint, jsonify, request, current_app, g
from utils.emailer import send_email
from utils.ai_resume import tfidf_match_score, extract_basic_entities, analyze_resume_hybrid
from utils.db import init_db
from utils.files import read_resume_text
from utils.security import require_auth
from utils.serialize import doc_to_json
from utils.validation import require_fields, now_utc

resumes_bp = Blueprint("resumes", __name__)


def normalize_skill_list(items):
    cleaned = []
    seen = set()
    for item in items or []:
        val = str(item or "").strip().lower()
        if val and val not in seen:
            cleaned.append(val)
            seen.add(val)
    return cleaned


@resumes_bp.post("/upload")
@require_auth(roles=["Candidate"])
def upload_resume():
    form_job_id = (request.form.get("job_id") or "").strip()
    if not form_job_id:
        return jsonify({"error": "Missing job_id"}), 400

    if "file" not in request.files:
        return jsonify({"error": "Missing file"}), 400

    f = request.files["file"]
    if not f or not f.filename:
        return jsonify({"error": "Invalid file"}), 400

    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in [".pdf", ".docx"]:
        return jsonify({"error": "Only PDF or DOCX supported"}), 400

    upload_dir = current_app.config["UPLOAD_DIR"]
    safe_name = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(upload_dir, safe_name)
    f.save(path)

    text = read_resume_text(path)
    entities = extract_basic_entities(text)

    db = init_db()
    job = db.jobs.find_one({"_id": ObjectId(form_job_id)})
    if not job:
        return jsonify({"error": "Job not found"}), 404

    job_text = f"{job.get('title','')}\n{job.get('description','')}\n{' '.join(job.get('skills', []))}"
    score = tfidf_match_score(text, job_text)

    analysis = analyze_resume_hybrid(
        resume_text=text,
        job_title=job.get("title", ""),
        job_description=job.get("description", ""),
        job_skills=job.get("skills", []),
        tfidf_score=score,
        extracted=entities,
    )

    # =========================
    # ROBUST SKILL HANDLING
    # =========================
    required_skills = normalize_skill_list(job.get("skills", []))
    extracted_skills = normalize_skill_list(analysis.get("extracted_skills", []))

    required_set = set(required_skills)
    extracted_set = set(extracted_skills)

    # ALSO match directly from resume text so new skills still work
    resume_text_l = (text or "").lower()

    matched_required = set()
    for skill in required_set:
        if skill in extracted_set or skill in resume_text_l:
            matched_required.add(skill)

    match_percent = round((len(matched_required) / len(required_set)) * 100) if required_set else 0
    missing_requirements = sorted(list(required_set - matched_required))

    # =========================
    # RECOMMENDATION LOGIC
    # =========================
    if required_set and required_set.issubset(matched_required):
        score = max(score, 75)
        recommendation = "accept"
    elif match_percent >= 60:
        score = max(score, 45)
        recommendation = "review"
    else:
        recommendation = "reject"

    # Prefer strengths from actual matched skills
    strengths = sorted(list(matched_required))[:6]
    weaknesses = missing_requirements[:6]

    ai_summary = analysis.get("ai_summary", "")
    if recommendation == "accept":
        ai_summary = (
            f"The resume covers all required skills for this job. "
            f"Matched required skills: {', '.join(sorted(matched_required)) or 'none'}. "
            f"Overall fit is acceptable."
        )
    elif recommendation == "review":
        ai_summary = (
            f"The resume matches {match_percent}% of the required skills. "
            f"Matched skills: {', '.join(sorted(matched_required)) or 'none'}. "
            f"Missing requirements: {', '.join(missing_requirements) or 'none'}. "
            f"This profile should be reviewed further."
        )
    else:
        ai_summary = (
            f"The resume matches only {match_percent}% of the required skills. "
            f"Matched skills: {', '.join(sorted(matched_required)) or 'none'}. "
            f"Missing requirements: {', '.join(missing_requirements) or 'none'}. "
            f"Current fit is below the required threshold."
        )

    resume_doc = {
        "candidate_id": ObjectId(g.user["_id"]),
        "job_id": job["_id"],
        "filename": f.filename,
        "stored_name": safe_name,
        "path": path,
        "text": text,
        "extracted": entities,
        "score": score,
        "ai_extracted_skills": sorted(list(extracted_set)),
        "ai_experience_level": analysis.get("experience_level", ""),
        "ai_strengths": strengths,
        "ai_weaknesses": weaknesses,
        "ai_missing_requirements": missing_requirements,
        "ai_summary": ai_summary,
        "recommendation": recommendation,
        "created_at": now_utc(),
    }

    res = db.resumes.insert_one(resume_doc)
    resume_doc["_id"] = res.inserted_id

    # Attach to application if exists
    app = db.applications.find_one({
        "job_id": job["_id"],
        "candidate_id": ObjectId(g.user["_id"])
    })

    if app:
        db.applications.update_one(
            {"_id": app["_id"]},
            {
                "$set": {
                    "resume_id": resume_doc["_id"],
                    "resume_score": score,
                    "resume_ai_extracted_skills": sorted(list(extracted_set)),
                    "resume_ai_experience_level": analysis.get("experience_level", ""),
                    "resume_ai_strengths": strengths,
                    "resume_ai_weaknesses": weaknesses,
                    "resume_ai_summary": ai_summary,
                    "resume_recommendation": recommendation,
                    "updated_at": now_utc(),
                }
            },
        )

    # =========================
    # EMAIL NOTIFICATION
    # =========================
    user = db.users.find_one({"_id": ObjectId(g.user["_id"])})

    if user and user.get("email"):
        send_email(
            current_app.mail,
            user["email"],
            "Resume Uploaded Successfully 🚀",
            f"""
Hi {user.get('name','User')},

Your resume has been successfully uploaded and analyzed.

📊 Score: {score}%
🧠 AI Recommendation: {recommendation}

Keep improving and best of luck!

— HREC Team
"""
        )

    return (
        jsonify(
            {
                "resume": doc_to_json(resume_doc),
                "score": score,
                "extracted_skills": sorted(list(extracted_set)),
                "ai_summary": ai_summary,
                "recommendation": recommendation,
            }
        ),
        201,
    )


@resumes_bp.get("")
@require_auth(roles=["HR", "Candidate"])
def list_resumes():
    db = init_db()
    query = {}

    if g.user["role"] == "Candidate":
        query["candidate_id"] = ObjectId(g.user["_id"])

    job_id = (request.args.get("job_id") or "").strip()
    if job_id:
        query["job_id"] = ObjectId(job_id)

    res = list(db.resumes.find(query).sort("created_at", -1).limit(200))
    return jsonify({"resumes": [doc_to_json(r) for r in res]})


@resumes_bp.post("/score")
@require_auth(roles=["HR", "Candidate"])
def score_text():
    data = request.get_json(force=True, silent=True) or {}
    err = require_fields(data, ["resume_text", "job_text"])
    if err:
        return jsonify({"error": err}), 400

    score = tfidf_match_score(data["resume_text"], data["job_text"])
    return jsonify({"score": score})