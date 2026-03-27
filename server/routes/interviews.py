from bson import ObjectId
from flask import Blueprint, jsonify, request, g

from utils.ai_interview import (
    generate_questions_hybrid,
    score_answer_hybrid,
    generate_interview_final_hybrid,
)
from utils.db import init_db
from utils.security import require_auth
from utils.serialize import doc_to_json
from utils.validation import require_fields, now_utc

interviews_bp = Blueprint("interviews", __name__)


def apply_fair_score_boost(answer, raw_score):
    score = int(raw_score or 0)
    words = len((answer or "").strip().split())

    # fair boost for detailed answers
    if words > 20 and score < 50:
        score += 10
    elif words > 10 and score < 40:
        score += 5

    return min(score, 100)


def decide_final_recommendation(total_score):
    total_score = int(total_score or 0)

    # minimum rejection threshold = below 30 only
    if total_score >= 50:
        return "Accepted"
    elif total_score >= 30:
        return "Review"
    else:
        return "Rejected"


@interviews_bp.post("/start")
@require_auth(roles=["Candidate"])
def start_interview():
    data = request.get_json(force=True, silent=True) or {}
    err = require_fields(data, ["application_id"])
    if err:
        return jsonify({"error": err}), 400

    db = init_db()
    app = db.applications.find_one({"_id": ObjectId(data["application_id"])})
    if not app or str(app["candidate_id"]) != g.user["_id"]:
        return jsonify({"error": "Application not found"}), 404

    job = db.jobs.find_one({"_id": app["job_id"]})
    if not job:
        return jsonify({"error": "Job missing"}), 400

    questions = generate_questions_hybrid(
        job.get("title", ""),
        job.get("description", ""),
        job.get("skills", []),
    )

    interview = {
        "application_id": app["_id"],
        "job_id": app["job_id"],
        "candidate_id": app["candidate_id"],
        "questions": [{"q": q, "a": "", "score": None, "feedback": None} for q in questions],
        "status": "InProgress",
        "total_score": None,
        "created_at": now_utc(),
        "updated_at": now_utc(),
    }

    existing = db.interviews.find_one({"application_id": app["_id"]})
    if existing:
        return jsonify({"interview": doc_to_json(existing)})

    res = db.interviews.insert_one(interview)
    interview["_id"] = res.inserted_id
    return jsonify({"interview": doc_to_json(interview)}), 201


@interviews_bp.post("/answer")
@require_auth(roles=["Candidate"])
def submit_answer():
    data = request.get_json(force=True, silent=True) or {}
    err = require_fields(data, ["interview_id", "index", "answer"])
    if err:
        return jsonify({"error": err}), 400

    idx = int(data["index"])
    db = init_db()
    interview = db.interviews.find_one({"_id": ObjectId(data["interview_id"])})
    if not interview or str(interview["candidate_id"]) != g.user["_id"]:
        return jsonify({"error": "Interview not found"}), 404

    questions = interview.get("questions", [])
    if idx < 0 or idx >= len(questions):
        return jsonify({"error": "Invalid index"}), 400

    job = db.jobs.find_one({"_id": interview["job_id"]}) or {}
    expected = job.get("skills", [])

    question_text = (questions[idx] or {}).get("q", "")
    answer_text = (data["answer"] or "").strip()

    res = score_answer_hybrid(
        job_title=job.get("title", ""),
        job_description=job.get("description", ""),
        job_skills=expected,
        question=question_text,
        answer=answer_text,
    )

    raw_score = int(res.get("score") or 0)
    score = apply_fair_score_boost(answer_text, raw_score)
    feedback = str(res.get("feedback") or "")

    # helpful feedback override for detailed answers that still scored low
    if len(answer_text.split()) > 20 and score >= 30 and not feedback:
        feedback = "Answer is detailed and relevant, but can be improved with more direct role-specific points."

    questions[idx]["a"] = answer_text
    questions[idx]["score"] = score
    questions[idx]["feedback"] = feedback

    scored = [q.get("score") for q in questions if q.get("score") is not None]
    total = int(round(sum(scored) / len(scored))) if scored else None

    db.interviews.update_one(
        {"_id": interview["_id"]},
        {"$set": {"questions": questions, "total_score": total, "updated_at": now_utc()}},
    )

    interview = db.interviews.find_one({"_id": interview["_id"]})
    return jsonify({"interview": doc_to_json(interview)})


@interviews_bp.post("/finish")
@require_auth(roles=["Candidate"])
def finish():
    data = request.get_json(force=True, silent=True) or {}
    err = require_fields(data, ["interview_id"])
    if err:
        return jsonify({"error": err}), 400

    db = init_db()
    interview = db.interviews.find_one({"_id": ObjectId(data["interview_id"])})
    if not interview or str(interview["candidate_id"]) != g.user["_id"]:
        return jsonify({"error": "Interview not found"}), 404

    db.interviews.update_one(
        {"_id": interview["_id"]},
        {"$set": {"status": "Completed", "updated_at": now_utc()}},
    )
    interview = db.interviews.find_one({"_id": interview["_id"]})

    job = db.jobs.find_one({"_id": interview["job_id"]}) or {}
    app = db.applications.find_one({"_id": interview.get("application_id")}) if interview.get("application_id") else None
    resume_score = app.get("resume_score") if app else None

    total_score = int(interview.get("total_score") or 0)

    final = generate_interview_final_hybrid(
        job_title=job.get("title", ""),
        job_description=job.get("description", ""),
        job_skills=job.get("skills", []),
        questions=interview.get("questions", []),
        total_score=total_score,
        resume_score=resume_score,
    )

    final_summary = final.get("final_summary", "") or ""
    final_recommendation = decide_final_recommendation(total_score)

    # Make summary align with your minimum-score rule
    if total_score >= 50:
        prefix = "Candidate performed well overall."
    elif total_score >= 30:
        prefix = "Candidate shows potential and should be reviewed, not rejected."
    else:
        prefix = "Candidate needs improvement before moving ahead."

    if final_summary:
        final_summary = f"{prefix} {final_summary}"
    else:
        final_summary = prefix

    db.interviews.update_one(
        {"_id": interview["_id"]},
        {
            "$set": {
                "final_summary": final_summary,
                "final_recommendation": final_recommendation,
                "updated_at": now_utc(),
            }
        },
    )
    interview = db.interviews.find_one({"_id": interview["_id"]})

    if interview.get("application_id"):
        db.applications.update_one(
            {"_id": interview["application_id"]},
            {
                "$set": {
                    "interview.score": interview.get("total_score"),
                    "interview.final_summary": interview.get("final_summary"),
                    "interview.final_recommendation": interview.get("final_recommendation"),
                    "updated_at": now_utc(),
                }
            },
        )

    return jsonify({"interview": doc_to_json(interview)})


@interviews_bp.get("")
@require_auth(roles=["HR", "Candidate"])
def list_interviews():
    db = init_db()
    query = {}

    if g.user["role"] == "Candidate":
        query["candidate_id"] = ObjectId(g.user["_id"])

    items = list(db.interviews.find(query).sort("created_at", -1).limit(200))
    return jsonify({"interviews": [doc_to_json(i) for i in items]})