import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def normalize_text(text: str) -> str:
    text = text or ""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s\+\#\.\-\/&]", " ", text)
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
    return int(round(max(0.0, min(1.0, float(sim))) * 100))


# Canonical skill -> aliases
SKILL_ALIASES = {
    # tech
    "python": ["python"],
    "java": ["java"],
    "javascript": ["javascript", "js"],
    "typescript": ["typescript", "ts"],
    "c": [" c "],
    "c++": ["c++", "cpp"],
    "c#": ["c#", "csharp"],
    "php": ["php"],
    "ruby": ["ruby"],
    "go": ["go", "golang"],
    "rust": ["rust"],
    "swift": ["swift"],
    "kotlin": ["kotlin"],
    "html": ["html"],
    "css": ["css"],
    "react": ["react", "reactjs", "react.js"],
    "angular": ["angular"],
    "vue": ["vue", "vuejs"],
    "node": ["node", "nodejs", "node.js"],
    "express": ["express", "expressjs"],
    "flask": ["flask"],
    "django": ["django"],
    "fastapi": ["fastapi"],
    "spring boot": ["spring boot", "springboot"],
    "laravel": ["laravel"],
    "mongodb": ["mongodb", "mongo db", "mongo"],
    "mysql": ["mysql"],
    "postgresql": ["postgresql", "postgres"],
    "sql": ["sql"],
    "sqlite": ["sqlite"],
    "oracle": ["oracle"],
    "firebase": ["firebase"],
    "redis": ["redis"],
    "docker": ["docker"],
    "kubernetes": ["kubernetes", "k8s"],
    "aws": ["aws", "amazon web services"],
    "azure": ["azure"],
    "gcp": ["gcp", "google cloud", "google cloud platform"],
    "linux": ["linux"],
    "git": ["git"],
    "github": ["github"],
    "api": ["api", "apis", "rest api", "restful api"],
    "graphql": ["graphql"],
    "microservices": ["microservices", "microservice"],
    "machine learning": ["machine learning", "ml"],
    "deep learning": ["deep learning"],
    "nlp": ["nlp", "natural language processing"],
    "tensorflow": ["tensorflow"],
    "pytorch": ["pytorch"],
    "pandas": ["pandas"],
    "numpy": ["numpy"],
    "power bi": ["power bi", "powerbi"],
    "tableau": ["tableau"],
    "excel": ["excel", "microsoft excel"],

    # data / analytics
    "data analysis": ["data analysis", "data analytics"],
    "data science": ["data science"],
    "statistics": ["statistics"],
    "etl": ["etl"],

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
    "analytics": ["analytics", "web analytics", "marketing analytics"],

    # sales / business
    "crm": ["crm", "customer relationship management"],
    "sales": ["sales", "sales executive", "sales management"],
    "negotiation": ["negotiation", "negotiation skills"],
    "lead generation": ["lead generation"],
    "client management": ["client management", "client handling"],
    "customer service": ["customer service"],
    "business development": ["business development"],

    # hr / operations
    "hr": ["hr", "human resources"],
    "recruitment": ["recruitment", "talent acquisition", "hiring"],
    "payroll": ["payroll"],

    # generic professional
    "communication skills": ["communication", "communication skills"],
    "leadership": ["leadership"],
    "teamwork": ["teamwork"],
    "problem solving": ["problem solving"],
    "time management": ["time management"],
    "project management": ["project management"],
}


def _contains_phrase(text: str, phrase: str) -> bool:
    text = f" {normalize_text(text)} "
    phrase = f" {normalize_text(phrase)} "
    return phrase in text


def normalize_skill_list(items):
    cleaned = []
    seen = set()
    for item in items or []:
        val = normalize_text(str(item or ""))
        if val and val not in seen:
            cleaned.append(val)
            seen.add(val)
    return cleaned


def _extract_skills_section(text: str) -> list[str]:
    """
    Pull comma-separated or line-separated skills from the Skills section directly.
    """
    raw = text or ""
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    captured = []

    for i, line in enumerate(lines):
        low = normalize_text(line)
        if low in {"skills", "technical skills", "key skills", "core skills"}:
            # take next 1-4 non-heading lines
            for nxt in lines[i + 1:i + 5]:
                nxt_low = normalize_text(nxt)
                if nxt_low in {"experience", "education", "projects", "objective", "summary"}:
                    break
                captured.append(nxt)

    tokens = []
    for chunk in captured:
        parts = re.split(r"[,/|•\-]", chunk)
        for part in parts:
            p = normalize_text(part)
            if len(p) >= 2:
                tokens.append(p)

    return normalize_skill_list(tokens)


def extract_basic_entities(text: str) -> dict:
    text = text or ""
    low = normalize_text(text)

    found_skills = []

    # 1) alias bank
    for canonical, aliases in SKILL_ALIASES.items():
        for alias in aliases:
            if _contains_phrase(low, alias):
                found_skills.append(canonical)
                break

    # 2) direct skills section extraction
    section_skills = _extract_skills_section(text)
    found_skills.extend(section_skills)

    skills = normalize_skill_list(found_skills)

    edu_snips = []
    for kw in [
        "bachelor", "master", "phd", "degree", "university", "college",
        "bba", "bsc", "msc", "mba", "be", "btech", "mtech", "bcom"
    ]:
        if _contains_phrase(low, kw):
            edu_snips.append(kw)

    exp_snips = []
    for kw in [
        "experience", "years", "worked", "project", "intern", "employment",
        "specialist", "manager", "lead", "executive", "developer", "analyst"
    ]:
        if _contains_phrase(low, kw):
            exp_snips.append(kw)

    return {
        "skills": skills,
        "education": sorted(set(edu_snips)),
        "experience": sorted(set(exp_snips)),
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

    if "intern" in low:
        return "Entry-level (intern/early experience)"
    if any(k in low for k in ["experience", "worked", "employment", "years", "specialist", "analyst", "developer"]):
        if any(k in low for k in ["senior", "lead", "manager"]):
            return "Senior (substantial hands-on experience)"
        return "Mid-level (measurable experience)"
    if entities.get("education"):
        return "Junior (education-forward with limited explicit experience)"
    return "Unknown/early career (limited signals in resume text)"


def _local_resume_analysis(
    *, resume_text: str, job_title: str, job_description: str, job_skills: list[str], tfidf_score: int, extracted: dict
) -> dict:
    resume_skills = set(normalize_skill_list(extracted.get("skills") or []))
    job_skills_lower = normalize_skill_list(job_skills or [])

    overlap = []
    for s in job_skills_lower:
        if s in resume_skills:
            overlap.append(s)
            continue
        # if exact required skill phrase exists anywhere in resume text, count it too
        if _contains_phrase(resume_text, s):
            overlap.append(s)

    strengths = overlap[:6]
    missing = [s for s in job_skills_lower if s not in overlap]
    weaknesses = missing[:6]
    missing_requirements = missing[:6]

    experience_level = _infer_experience_level(extracted)

    strengths_line = ", ".join(strengths) if strengths else "relevant skills where applicable"
    weaknesses_line = ", ".join(weaknesses) if weaknesses else "no major gaps detected from the required skills list"

    ai_summary = (
        f"Overall resume-job fit looks {tfidf_score}% by TF-IDF signals. "
        f"The candidate appears {experience_level.lower()} for the role of {job_title}. "
        f"Key strengths include: {strengths_line}. "
        f"Potential gaps/missing requirements: {weaknesses_line}. "
        f"Based on this, the recommendation is {_recommendation_from_score(tfidf_score)}."
    )

    return {
        "score": int(tfidf_score),
        "extracted_skills": sorted(list(resume_skills))[:20],
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