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
    Lightweight heuristic extraction:
    - detects skills from a broader skill bank
    - supports common aliases and marketing/domain skills
    """
    text = text or ""
    low = normalize_text(text)

    # canonical skill : aliases/patterns
    skill_aliases = {
        # tech
        "python": ["python"],
        "flask": ["flask"],
        "django": ["django"],
        "javascript": ["javascript", "js"],
        "typescript": ["typescript", "ts"],
        "react": ["react", "reactjs", "react.js"],
        "node": ["node", "nodejs", "node.js"],
        "mongodb": ["mongodb", "mongo db", "mongo"],
        "sql": ["sql", "mysql", "postgresql", "postgres"],
        "docker": ["docker"],
        "kubernetes": ["kubernetes", "k8s"],
        "aws": ["aws", "amazon web services"],
        "azure": ["azure"],
        "gcp": ["gcp", "google cloud"],
        "ml": ["ml", "machine learning"],
        "nlp": ["nlp", "natural language processing"],
        "tensorflow": ["tensorflow"],
        "pytorch": ["pytorch"],
        "pandas": ["pandas"],
        "numpy": ["numpy"],
        "excel": ["excel", "microsoft excel"],
        "power bi": ["power bi", "powerbi"],
        "tableau": ["tableau"],
        "java": ["java"],
        "html": ["html"],
        "css": ["css"],
        "api": ["api", "rest api", "restful api"],

        # HR / management
        "hr": ["hr", "human resources"],
        "recruitment": ["recruitment", "talent acquisition", "hiring"],
        "communication": ["communication"],

        # marketing
        "seo": ["seo", "search engine optimization"],
        "sem": ["sem", "search engine marketing"],
        "social media": ["social media", "social media marketing"],
        "google ads": ["google ads", "google adwords", "adwords"],
        "content creation": ["content creation", "content writing", "content marketing"],
        "digital marketing": ["digital marketing"],
        "branding": ["branding", "brand management"],
        "campaign management": ["campaign management", "campaigns"],
        "email marketing": ["email marketing"],
        "market research": ["market research"],
        "analytics": ["analytics", "marketing analytics", "web analytics"],
    }

    skills = []
    for canonical, aliases in skill_aliases.items():
        for alias in aliases:
            if re.search(rf"\b{re.escape(alias)}\b", low):
                skills.append(canonical)
                break

    skills = sorted(set(skills))

    edu_snips = []
    for kw in [
        "bachelor", "master", "phd", "degree", "university", "college",
        "bba", "bsc", "msc", "mba", "be", "btech", "mtech"
    ]:
        if re.search(rf"\b{re.escape(kw)}\b", low):
            edu_snips.append(kw)

    exp_snips = []
    for kw in [
        "experience", "years", "worked", "project", "intern", "employment",
        "specialist", "manager", "lead", "executive", "developer", "analyst"
    ]:
        if re.search(rf"\b{re.escape(kw)}\b", low):
            exp_snips.append(kw)

    return {
        "skills": skills,
        "education": sorted(set(edu_snips)),
        "experience": sorted(set(exp_snips))
    }


def _recommendation_from_score(score: int) -> str:
    if score >= 75:
        return "shortlist"
    if score >= 50:
        return "review"
    return "reject"


def _infer_experience_level(entities: dict) -> str:
    low = " ".join([
        str(entities.get("experience") or []),
        str(entities.get("education") or [])
    ]).lower()

    if any(k in low for k in ["intern"]):
        return "Entry-level (intern/early experience)"
    if any(k in low for k in ["experience", "worked", "employment", "years", "specialist", "analyst", "developer"]):
        if any(k in low for k in ["senior", "lead", "manager"]):
            return "Senior (substantial hands-on experience)"
        return "Mid-level (measurable experience)"
    if entities.get("education"):
        return "Junior (education-forward with limited explicit experience)"
    return "Unknown/early career (limited signals in resume text)"


def _local_resume_analysis(
    *,
    resume_text: str,
    job_title: str,
    job_description: str,
    job_skills: list[str],
    tfidf_score: int,
    extracted: dict
) -> dict:
    resume_skills = set((extracted.get("skills") or []))
    job_skills_lower = [str(s).lower().strip() for s in (job_skills or []) if str(s).strip()]

    overlap = []
    for s in job_skills_lower:
        if s in [x.lower() for x in resume_skills]:
            overlap.append(s)

    strengths = overlap[:5]
    missing = [s for s in job_skills_lower if s not in strengths]
    weaknesses = missing[:6]
    missing_requirements = missing[:6]

    experience_level = _infer_experience_level(extracted)

    strengths_line = ", ".join([str(x) for x in strengths]) if strengths else "relevant skills where applicable"
    weaknesses_line = ", ".join([str(x) for x in weaknesses]) if weaknesses else "no major gaps detected from the required skills list"

    ai_summary = (
        f"Overall resume-job fit looks {tfidf_score}% by TF-IDF signals. "
        f"The candidate appears {experience_level.lower()} for the role of {job_title}. "
        f"Key strengths include: {strengths_line}. "
        f"Potential gaps/missing requirements: {weaknesses_line}. "
        f"Based on this, the recommendation is {_recommendation_from_score(tfidf_score)}."
    )

    return {
        "score": int(tfidf_score),
        "extracted_skills": sorted(list(resume_skills))[:12],
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
    - Uses TF-IDF score
    - Uses improved local extraction
    - Optionally enriches with OpenAI
    - Always falls back safely
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

        openai_data = analyze_resume_with_openai(
            resume_text=resume_text,
            job_title=job_title,
            job_description=job_description,
            job_skills=job_skills,
            tfidf_score=int(tfidf_score),
        )

        if not openai_data:
            return {**local, "extracted": extracted}

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
        return {**local, "extracted": extracted}