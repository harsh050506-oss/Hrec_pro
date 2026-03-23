import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def normalize_text(text: str) -> str:
    text = text or ""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s\+\#\.\-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tfidf_match_score(resume_text: str, job_text: str) -> int:
    resume_text = normalize_text(resume_text)
    job_text = normalize_text(job_text)
    if not resume_text or not job_text:
        return 0
    vect = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), max_features=4000)
    tfidf = vect.fit_transform([resume_text, job_text])
    sim = cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0]
    score = int(round(max(0.0, min(1.0, float(sim))) * 100))
    return score


def extract_basic_entities(text: str) -> dict:
    """
    Lightweight heuristic extraction for demo/learning:
    - skills: looks for common skill tokens (can be expanded)
    - education/experience: simple keyword-based snippets
    """
    text = text or ""
    low = text.lower()

    skill_bank = [
        "python",
        "flask",
        "django",
        "javascript",
        "typescript",
        "react",
        "node",
        "mongodb",
        "sql",
        "docker",
        "kubernetes",
        "aws",
        "azure",
        "gcp",
        "ml",
        "nlp",
        "tensorflow",
        "pytorch",
        "pandas",
        "numpy",
        "excel",
        "hr",
        "recruitment",
        "communication",
    ]

    skills = sorted({s for s in skill_bank if re.search(rf"\b{re.escape(s)}\b", low)})

    edu_snips = []
    for kw in ["bachelor", "master", "phd", "degree", "university", "college"]:
        if kw in low:
            edu_snips.append(kw)

    exp_snips = []
    for kw in ["experience", "years", "worked", "project", "intern", "employment"]:
        if kw in low:
            exp_snips.append(kw)

    return {"skills": skills, "education": sorted(set(edu_snips)), "experience": sorted(set(exp_snips))}


def _recommendation_from_score(score: int) -> str:
    if score >= 75:
        return "shortlist"
    if score >= 50:
        return "review"
    return "reject"


def _infer_experience_level(entities: dict) -> str:
    low = " ".join([str(entities.get("experience") or []), str(entities.get("education") or [])]).lower()
    # Very lightweight inference (demo/learning); OpenAI can replace this when available.
    if any(k in low for k in ["intern"]):
        return "Entry-level (intern/early experience)"
    if any(k in low for k in ["experience", "worked", "employment", "years"]):
        # Split mid vs senior heuristics with keyword presence.
        if any(k in low for k in ["senior", "lead", "manager"]):
            return "Senior (substantial hands-on experience)"
        return "Mid-level (measurable experience)"
    if entities.get("education"):
        return "Junior (education-forward with limited explicit experience)"
    return "Unknown/early career (limited signals in resume text)"


def _local_resume_analysis(
    *, resume_text: str, job_title: str, job_description: str, job_skills: list[str], tfidf_score: int, extracted: dict
) -> dict:
    resume_skills = set(extracted.get("skills") or [])
    job_skills_lower = [s.lower() for s in (job_skills or [])]

    # Strengths: skill overlap.
    overlap = []
    for s in job_skills_lower:
        if any(rs == s for rs in [x.lower() for x in resume_skills]):
            overlap.append(s)
    strengths = [s for s in overlap[:5]]

    # Weaknesses/missing requirements: required skills not evidenced in extracted skills.
    missing = [s for s in job_skills_lower if s not in strengths]
    # Keep the list short and readable.
    weaknesses = missing[:6]
    missing_requirements = weaknesses[:6]

    experience_level = _infer_experience_level(extracted)

    # Compose HR-friendly paragraph.
    strengths_line = ", ".join([str(x) for x in strengths]) if strengths else "relevant skills where applicable"
    weaknesses_line = ", ".join([str(x) for x in weaknesses]) if weaknesses else "no major gaps detected from the required skills list"

    ai_summary = (
        f"Overall resume-job fit looks {tfidf_score}% by TF-IDF signals. "
        f"The candidate appears {experience_level.lower()} for the role of {job_title}. "
        f"Key strengths include: {strengths_line}. "
        f"Potential gaps/missing requirements: {weaknesses_line}. "
        f"Based on this, the recommendation is { _recommendation_from_score(tfidf_score) }."
    )

    return {
        "score": int(tfidf_score),
        "extracted_skills": sorted(list(resume_skills))[:10],
        "experience_level": experience_level,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "missing_requirements": missing_requirements,
        "ai_summary": ai_summary,
        "recommendation": _recommendation_from_score(tfidf_score),
    }


def analyze_resume_hybrid(
    *,
    resume_text: str,
    job_title: str,
    job_description: str,
    job_skills: list[str],
    tfidf_score: int | None = None,
    extracted: dict | None = None,
) -> dict:
    """
    Hybrid resume analysis:
    - Always computes/uses the existing TF-IDF cosine similarity score.
    - Optionally calls OpenAI to produce richer HR outputs.
    - Never raises: falls back to local analysis on any OpenAI failure.
    """
    extracted = extracted or extract_basic_entities(resume_text)

    if tfidf_score is None:
        job_text = f"{job_title or ''}\n{job_description or ''}\n{' '.join(job_skills or [])}"
        tfidf_score = tfidf_match_score(resume_text, job_text)

    local = _local_resume_analysis(
        resume_text=resume_text,
        job_title=job_title,
        job_description=job_description,
        job_skills=job_skills,
        tfidf_score=int(tfidf_score),
        extracted=extracted,
    )

    try:
        from .ai_openai import analyze_resume_with_openai

        # OpenAI enrichment is optional.
        openai_data = analyze_resume_with_openai(
            resume_text=resume_text,
            job_title=job_title,
            job_description=job_description,
            job_skills=job_skills,
            tfidf_score=int(tfidf_score),
        )
        if not openai_data:
            return {**local, "extracted": extracted}

        # Combine: keep the original TF-IDF numeric score, replace AI fields.
        return {
            "score": int(tfidf_score),
            "extracted": extracted,
            "extracted_skills": openai_data.get("extracted_skills") or local["extracted_skills"],
            "experience_level": openai_data.get("experience_level") or local["experience_level"],
            "strengths": openai_data.get("strengths") or local["strengths"],
            "weaknesses": openai_data.get("weaknesses") or local["weaknesses"],
            "missing_requirements": openai_data.get("missing_requirements") or local["missing_requirements"],
            "ai_summary": openai_data.get("ai_summary") or local["ai_summary"],
            "recommendation": openai_data.get("recommendation") or local["recommendation"],
        }
    except Exception:
        # Any unexpected errors must fall back to local logic.
        return {**local, "extracted": extracted}

