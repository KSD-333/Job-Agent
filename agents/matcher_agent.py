"""
Agent 3 — Resume Match Agent

Scores each normalized job against the candidate's resume using three
independent signals, combined into a single 0-100 score:

    40% skill overlap      — fuzzy string matching (rapidfuzz), cheap & deterministic
    30% keyword overlap    — semantic similarity via the resume's FAISS index (Agent 1)
    30% experience fit     — LLM judgment on seniority/domain match

Skill and keyword overlap never call the LLM, so most of the scoring cost
is avoided — the LLM is only used for the one signal that genuinely needs
judgment (seniority/domain fit).
"""

from typing import List, Tuple

from rapidfuzz import fuzz, process

from graph_flow.state import CareerAgentState, Job, MatchResult
from agents.resume_agent import retrieve_relevant_chunks
from utils.llm_json import call_groq_json

SKILL_MATCH_THRESHOLD = 80  # rapidfuzz similarity score (0-100) to count as a match
EXPERIENCE_FIT_PROMPT_PATH = "prompts/experience_fit.md"

WEIGHTS = {"skills": 0.4, "keywords": 0.3, "experience": 0.3}


def skill_overlap_score(resume_skills: List[str], job_skills: List[str]) -> Tuple[float, List[str], List[str]]:
    """Fuzzy-match each job-required skill against the resume's skill list.
    Returns (score_0_100, matched_job_skills, missing_job_skills)."""
    if not job_skills:
        return 100.0, [], []  # nothing required -> trivially satisfied

    if not resume_skills:
        return 0.0, [], list(job_skills)

    matched, missing = [], []
    for job_skill in job_skills:
        best = process.extractOne(job_skill, resume_skills, scorer=fuzz.WRatio)
        if best and best[1] >= SKILL_MATCH_THRESHOLD:
            matched.append(job_skill)
        else:
            missing.append(job_skill)

    score = round(100.0 * len(matched) / len(job_skills), 1)
    return score, matched, missing


def keyword_overlap_score(resume_json: dict, job_description: str) -> float:
    """Semantic similarity between the job description and the resume's
    embedded chunks, via the FAISS index built by the Resume Agent. Falls
    back to 0 if no index exists yet (resume agent hasn't run)."""
    if not job_description:
        return 0.0

    try:
        results = retrieve_relevant_chunks(job_description, top_k=3)
    except FileNotFoundError:
        return 0.0

    if not results:
        return 0.0

    avg_score = sum(r["score"] for r in results) / len(results)
    return round(max(0.0, min(1.0, avg_score)) * 100, 1)


def experience_fit_score(resume_json: dict, job: Job) -> float:
    """LLM call judging seniority/domain fit. Returns 0-100."""
    experience = resume_json.get("experience", [])
    experience_summary = "; ".join(
        f"{e.get('title', '')} at {e.get('company', '')} "
        f"({e.get('start_date', '')} - {e.get('end_date', '')})"
        for e in experience
    ) or "No experience listed."

    with open(EXPERIENCE_FIT_PROMPT_PATH, "r") as f:
        template = f.read()

    prompt = (
        template
        .replace("{experience_summary}", experience_summary)
        .replace("{job_title}", job.get("role", ""))
        .replace("{company}", job.get("company", ""))
        .replace("{job_description}", job.get("description", ""))
    )

    result = call_groq_json(prompt)
    score = result.get("score", 0)
    try:
        return float(max(0, min(100, score)))
    except (TypeError, ValueError):
        return 0.0


def run_matcher_agent(state: CareerAgentState) -> dict:
    """LangGraph node. Scores every normalized job against resume_json.
    A job that fails the LLM-dependent experience score (e.g. missing
    GROQ_API_KEY) still gets scored on skills+keywords, with experience
    treated as 0 and the failure logged — a partial score beats dropping
    the job silently."""
    resume_json = state.get("resume_json", {})
    jobs = state.get("normalized_jobs", [])

    matches: List[MatchResult] = []
    errors: List[str] = []

    for job in jobs:
        skill_score, matched, missing = skill_overlap_score(
            resume_json.get("skills", []), job.get("skills", [])
        )
        kw_score = keyword_overlap_score(resume_json, job.get("description", ""))

        try:
            exp_score = experience_fit_score(resume_json, job)
        except (RuntimeError, ValueError) as e:
            errors.append(f"matcher_agent[{job.get('company')}]: {e}")
            exp_score = 0.0

        final_score = round(
            WEIGHTS["skills"] * skill_score
            + WEIGHTS["keywords"] * kw_score
            + WEIGHTS["experience"] * exp_score,
            1,
        )

        matches.append({
            "job_id": job.get("job_id", ""),
            "company": job.get("company", ""),
            "role": job.get("role", ""),
            "score": final_score,
            "matched_skills": matched,
            "missing_skills": missing,
            "keyword_overlap": kw_score,
            "experience_fit": exp_score,
        })

    return {"matches": matches, "errors": errors}
