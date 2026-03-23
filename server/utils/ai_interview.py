import random


DEFAULT_QUESTION_BANK = {
    "general": [
        "Tell me about yourself and your recent work.",
        "Describe a challenging problem you solved and how you approached it.",
        "How do you prioritize tasks when everything feels urgent?",
        "What does great teamwork look like to you?",
    ],
    "hr": [
        "How would you handle a conflict between two employees?",
        "Describe your experience with interviewing and evaluation criteria.",
        "How do you ensure fairness and reduce bias in hiring?",
    ],
    "engineering": [
        "Explain a system you designed. What trade-offs did you make?",
        "How do you test and monitor production systems?",
        "Tell me about a time you improved performance or reliability.",
    ],
}


def generate_questions(job_title: str, job_skills: list[str], n: int = 6) -> list[str]:
    title = (job_title or "").lower()
    skills = [s.lower() for s in (job_skills or [])]

    pool = list(DEFAULT_QUESTION_BANK["general"])
    if "hr" in title or "recruit" in title:
        pool += DEFAULT_QUESTION_BANK["hr"]
    if any(s in skills for s in ["python", "javascript", "mongodb", "sql", "ml", "nlp", "flask", "docker", "kubernetes"]):
        pool += DEFAULT_QUESTION_BANK["engineering"]

    random.shuffle(pool)
    uniq = []
    for q in pool:
        if q not in uniq:
            uniq.append(q)
    return uniq[: max(3, min(n, 12))]


def score_answer_basic(answer: str, expected_keywords: list[str] | None = None) -> int:
    """
    Simple baseline scoring:
    - length-based heuristic
    - keyword hits (if provided)
    """
    answer = (answer or "").strip()
    if not answer:
        return 0
    score = 30
    if len(answer) > 80:
        score += 20
    if len(answer) > 200:
        score += 10

    expected_keywords = expected_keywords or []
    low = answer.lower()
    hits = sum(1 for k in expected_keywords if k.lower() in low)
    score += min(40, hits * 10)
    return max(0, min(100, int(score)))


def score_answer_basic_with_feedback(answer: str, expected_keywords: list[str] | None = None) -> dict:
    """
    Local fallback that returns both a numeric score and short feedback.
    """
    expected_keywords = expected_keywords or []
    answer = (answer or "").strip()
    if not answer:
        return {"score": 0, "feedback": "No answer provided. Please respond with a clear example aligned to the role."}

    low = answer.lower()
    matched = [k for k in expected_keywords if k.lower() in low]
    missing = [k for k in expected_keywords if k.lower() not in low]

    score = score_answer_basic(answer, expected_keywords=expected_keywords)

    if matched and missing:
        feedback = (
            f"Good coverage of {', '.join(matched[:4])}. "
            f"To improve, add specifics about: {', '.join(missing[:4])}."
        )
    elif matched:
        feedback = f"Strong alignment with required skills ({', '.join(matched[:5])}). Consider adding more depth and measurable outcomes."
    else:
        feedback = (
            "Your answer is a bit generic. Include concrete examples and explicitly address required skills like: "
            f"{', '.join(expected_keywords[:5])}."
        )

    return {"score": score, "feedback": feedback}


def generate_questions_hybrid(job_title: str, job_description: str, job_skills: list[str], n: int = 6) -> list[str]:
    """
    Generates interview questions using OpenAI when possible, otherwise local fallback.
    """
    try:
        from .ai_openai import generate_interview_questions_with_openai

        qs = generate_interview_questions_with_openai(
            job_title=job_title or "",
            job_description=job_description or "",
            job_skills=job_skills or [],
            n=n,
        )
        if qs:
            return qs
    except Exception:
        pass

    # Local fallback ignores job_description but uses title+skills to pick from the existing bank.
    return generate_questions(job_title=job_title or "", job_skills=job_skills or [], n=n)


def score_answer_hybrid(job_title: str, job_description: str, job_skills: list[str], question: str, answer: str) -> dict:
    """
    Scores an individual interview answer and returns {score, feedback}.
    """
    expected_keywords = job_skills or []
    try:
        from .ai_openai import score_interview_answer_with_openai

        data = score_interview_answer_with_openai(
            job_title=job_title or "",
            job_description=job_description or "",
            job_skills=expected_keywords,
            question=question or "",
            answer=answer or "",
        )
        if data:
            return {"score": int(data.get("score") or 0), "feedback": str(data.get("feedback") or "").strip()}
    except Exception:
        pass

    # Local fallback.
    res = score_answer_basic_with_feedback(answer, expected_keywords=expected_keywords)
    return {"score": int(res.get("score") or 0), "feedback": str(res.get("feedback") or "").strip()}


def _recommendation_from_score(score: int) -> str:
    if score >= 75:
        return "shortlist"
    if score >= 50:
        return "review"
    return "reject"


def generate_interview_final_local(
    *,
    job_title: str,
    job_skills: list[str],
    questions: list[dict],
    total_score: int | None,
    resume_score: int | None,
) -> dict:
    job_skills_lower = [s.lower() for s in (job_skills or []) if s]
    total_score = int(total_score) if total_score is not None else None

    answered = [q for q in (questions or []) if (q.get("a") or "").strip() and q.get("score") is not None]

    # Find evidence in answers (very lightweight keyword evidence).
    all_answers = " ".join([str(q.get("a") or "") for q in answered]).lower()
    evidenced_skills = [s for s in job_skills_lower if s in all_answers]
    missing_skills = [s for s in job_skills_lower if s not in evidenced_skills]

    strengths = evidenced_skills[:6]
    weaknesses = missing_skills[:6]

    avg = total_score if total_score is not None else 0
    combined = None
    if resume_score is not None and total_score is not None:
        combined = int(round((int(resume_score) * 0.4) + (int(total_score) * 0.6)))
    reco = _recommendation_from_score(combined if combined is not None else avg)

    strengths_line = ", ".join(str(x) for x in strengths) if strengths else "relevant strengths"
    weaknesses_line = ", ".join(str(x) for x in weaknesses) if weaknesses else "no major gaps detected"

    final_summary = (
        f"For the {job_title} role, the candidate shows an overall interview score of "
        f"{avg if total_score is not None else 'N/A'}%. Evidence-based skills include {strengths_line}. "
        f"Likely gaps: {weaknesses_line}. Overall recommendation: {reco}."
    )

    return {"final_summary": final_summary, "final_recommendation": reco}


def generate_interview_final_hybrid(
    *,
    job_title: str,
    job_description: str,
    job_skills: list[str],
    questions: list[dict],
    total_score: int | None,
    resume_score: int | None = None,
) -> dict:
    """
    Produces the final interview summary + recommendation.
    """
    try:
        from .ai_openai import generate_interview_final_with_openai

        data = generate_interview_final_with_openai(
            job_title=job_title or "",
            job_description=job_description or "",
            job_skills=job_skills or [],
            questions=questions or [],
            total_score=total_score,
            resume_score=resume_score,
        )
        if data and data.get("final_summary"):
            rec = str(data.get("final_recommendation") or "").strip().lower()
            if rec not in {"shortlist", "review", "reject"}:
                rec = "review"
            return {
                "final_summary": str(data.get("final_summary") or "").strip(),
                "final_recommendation": rec,
            }
    except Exception:
        pass

    return generate_interview_final_local(
        job_title=job_title or "",
        job_skills=job_skills or [],
        questions=questions or [],
        total_score=total_score,
        resume_score=resume_score,
    )

