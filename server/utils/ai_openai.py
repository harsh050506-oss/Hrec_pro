import json
import re
from typing import Any

from .config import get_openai_key, get_openai_model


def _safe_truncate(text: str, max_chars: int = 12000) -> str:
    text = text or ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars].strip()


def _extract_first_json_object(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    # Remove code fences if the model wraps JSON.
    text = re.sub(r"^```(?:json)?\\s*", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"```\\s*$", "", text.strip())

    try:
        return json.loads(text)
    except Exception:
        pass

    # Best-effort: find the first `{` and the last `}` and try again.
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    candidate = text[start : end + 1]
    try:
        return json.loads(candidate)
    except Exception:
        return None


def _openai_available() -> bool:
    key = (get_openai_key() or "").strip()
    if not key:
        return False
    try:
        import openai  # noqa: F401

        return True
    except Exception:
        return False


def _chat_complete_json(messages: list[dict[str, str]], max_tokens: int = 900) -> dict[str, Any] | None:
    """
    Calls OpenAI Chat Completions and parses JSON.
    Never raises: returns None on any failure.
    """
    if not _openai_available():
        return None

    try:
        from openai import OpenAI  # type: ignore

        client = OpenAI(api_key=get_openai_key())
        model = get_openai_model()

        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.2,
            max_tokens=max_tokens,
        )

        content = (resp.choices[0].message.content or "").strip()
        return _extract_first_json_object(content)
    except Exception:
        return None


def analyze_resume_with_openai(
    *,
    resume_text: str,
    job_title: str,
    job_description: str,
    job_skills: list[str],
    tfidf_score: int,
) -> dict[str, Any] | None:
    """
    Returns a dict like:
      {
        "extracted_skills": [...],
        "experience_level": "...",
        "strengths": [...],
        "weaknesses": [...],
        "missing_requirements": [...],
        "ai_summary": "...",
        "recommendation": "shortlist|review|reject"
      }
    Returns None if OpenAI is unavailable or fails.
    """
    resume_text = _safe_truncate(resume_text, 12000)
    job_description = _safe_truncate(job_description, 6000)
    job_skills = [s for s in (job_skills or []) if s]

    system = (
        "You are an expert HR analyst. You must respond with valid JSON only (no markdown). "
        "The JSON must match the requested schema."
    )

    user = {
        "task": "Resume analysis for hiring decisions",
        "inputs": {
            "resume_text": resume_text,
            "job_title": job_title,
            "job_description": job_description,
            "required_skills": job_skills,
            "tfidf_score": tfidf_score,
        },
        "instructions": [
            "Extract likely skills that are evidenced in the resume.",
            "Summarize candidate experience level (e.g., entry/junior/mid/senior) and cite why using resume signals.",
            "List strengths (skills or achievements strongly supported by the resume).",
            "List weaknesses (skills that seem missing or weak vs the required skills).",
            "List missing_requirements (specific required skills from required_skills that are not evidenced).",
            "Write a short HR-friendly evaluation paragraph.",
            "Set recommendation to one of: shortlist, review, reject.",
            "Be conservative: do not invent experience not present in the resume.",
            "Return JSON only with the schema keys exactly as listed below.",
        ],
        "schema": {
            "extracted_skills": ["string"],
            "experience_level": "string",
            "strengths": ["string"],
            "weaknesses": ["string"],
            "missing_requirements": ["string"],
            "ai_summary": "string",
            "recommendation": "shortlist|review|reject",
        },
    }

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(user)},
    ]
    data = _chat_complete_json(messages=messages, max_tokens=900)
    if not data:
        return None

    # Normalize expected keys and sanitize recommendation.
    rec = (data.get("recommendation") or "").strip().lower()
    if rec not in {"shortlist", "review", "reject"}:
        rec = "review"
    data["recommendation"] = rec

    def _list_of_strings(v: Any) -> list[str]:
        if not isinstance(v, list):
            return []
        out: list[str] = []
        for x in v:
            if isinstance(x, str) and x.strip():
                out.append(x.strip())
        return out

    data["extracted_skills"] = _list_of_strings(data.get("extracted_skills"))
    data["strengths"] = _list_of_strings(data.get("strengths"))
    data["weaknesses"] = _list_of_strings(data.get("weaknesses"))
    data["missing_requirements"] = _list_of_strings(data.get("missing_requirements"))
    data["experience_level"] = str(data.get("experience_level") or "").strip()
    data["ai_summary"] = str(data.get("ai_summary") or "").strip()
    return data


def generate_interview_questions_with_openai(
    *,
    job_title: str,
    job_description: str,
    job_skills: list[str],
    n: int = 6,
) -> list[str] | None:
    """
    Returns a list of question strings, or None on failure.
    """
    job_description = _safe_truncate(job_description, 6000)
    job_skills = [s for s in (job_skills or []) if s]
    system = (
        "You are an interview designer. Return valid JSON only (no markdown). "
        "The JSON must match the requested schema."
    )

    user = {
        "task": "Generate dynamic interview questions",
        "inputs": {
            "job_title": job_title,
            "job_description": job_description,
            "required_skills": job_skills,
            "n_questions": n,
        },
        "instructions": [
            "Generate questions that test both general and skill-specific competency.",
            "Include behavioral questions relevant to the role.",
            "Keep each question concise and specific (1-2 sentences max).",
            "Return JSON only: {\"questions\": [\"...\", ...]}",
        ],
        "schema": {"questions": ["string"]},
    }

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(user)},
    ]
    data = _chat_complete_json(messages=messages, max_tokens=900)
    if not data:
        return None
    qs = data.get("questions")
    if not isinstance(qs, list):
        return None
    out: list[str] = []
    for q in qs:
        if isinstance(q, str) and q.strip():
            out.append(q.strip())
    if not out:
        return None
    return out[: max(3, min(int(n), 12))]


def score_interview_answer_with_openai(
    *,
    job_title: str,
    job_description: str,
    job_skills: list[str],
    question: str,
    answer: str,
) -> dict[str, Any] | None:
    """
    Returns: { "score": int(0-100), "feedback": "string" }
    Returns None on failure.
    """
    job_description = _safe_truncate(job_description, 4000)
    answer = _safe_truncate(answer, 6000)
    job_skills = [s for s in (job_skills or []) if s]

    system = (
        "You are an interview coach. Score the answer from 0 to 100 and give short constructive feedback. "
        "Return valid JSON only (no markdown) with keys score and feedback."
    )

    user = {
        "task": "Score interview answer",
        "inputs": {
            "job_title": job_title,
            "job_description": job_description,
            "required_skills": job_skills,
            "question": question,
            "answer": answer,
        },
        "instructions": [
            "Score based on relevance to the question and evidence of required skills.",
            "Feedback should be 1-2 short sentences (HR-friendly but practical).",
            "If answer is vague, explain what specifics are missing.",
        ],
        "schema": {"score": "number 0-100", "feedback": "string"},
    }

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(user)},
    ]
    data = _chat_complete_json(messages=messages, max_tokens=400)
    if not data:
        return None
    try:
        score = int(round(float(data.get("score"))))
    except Exception:
        score = 0
    score = max(0, min(100, score))
    feedback = str(data.get("feedback") or "").strip()
    if not feedback:
        feedback = "Solid attempt. Add clearer examples and align more directly with the required skills."
    return {"score": score, "feedback": feedback}


def generate_interview_final_with_openai(
    *,
    job_title: str,
    job_description: str,
    job_skills: list[str],
    questions: list[dict[str, Any]],
    total_score: int | None,
    resume_score: int | None = None,
) -> dict[str, Any] | None:
    """
    Returns:
      { "final_summary": "...", "final_recommendation": "shortlist|review|reject" }
    """
    job_description = _safe_truncate(job_description, 4000)
    job_skills = [s for s in (job_skills or []) if s]

    # Keep prompt small by only including essentials.
    compact_questions: list[dict[str, Any]] = []
    for q in questions or []:
        compact_questions.append(
            {
                "q": (q.get("q") or "").strip(),
                "a": _safe_truncate(str(q.get("a") or ""), 2000),
                "score": q.get("score"),
                "feedback": _safe_truncate(str(q.get("feedback") or ""), 600),
            }
        )

    system = (
        "You are an expert HR interviewer. Produce a concise overall evaluation for hiring. "
        "Return valid JSON only (no markdown) matching the schema."
    )

    user = {
        "task": "Generate final interview evaluation",
        "inputs": {
            "job_title": job_title,
            "job_description": job_description,
            "required_skills": job_skills,
            "resume_score": resume_score,
            "interview_total_score": total_score,
            "answers": compact_questions,
        },
        "instructions": [
            "Write a short overall candidate summary referencing strengths/weaknesses seen across answers.",
            "Decide final_recommendation: shortlist, review, reject.",
            "Be conservative and do not invent evidence.",
            "Return JSON only.",
        ],
        "schema": {
            "final_summary": "string",
            "final_recommendation": "shortlist|review|reject",
        },
    }

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(user)},
    ]
    data = _chat_complete_json(messages=messages, max_tokens=900)
    if not data:
        return None

    rec = (data.get("final_recommendation") or "").strip().lower()
    if rec not in {"shortlist", "review", "reject"}:
        rec = "review"
    data["final_recommendation"] = rec
    data["final_summary"] = str(data.get("final_summary") or "").strip()
    return data

