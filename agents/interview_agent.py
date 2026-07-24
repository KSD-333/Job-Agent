"""
Agent 7 — Interview Prep Agent

Triggered separately from the main pipeline (see build_interview_graph in
graph_flow/graph.py), when a company's tracker status flips to
"Interview". Generates a comprehensive question set tailored to that
specific role/JD across multiple categories:
    - Language/framework specific (e.g. Java, Android, Kotlin)
    - Data Structures & Algorithms
    - System Design
    - Behavioral
    - Coding Problems

All questions are grounded in the actual JD + resume skills, not generic
interview prep.
"""

import json
import os

from graph_flow.state import CareerAgentState
from utils.llm_json import call_groq_json

REPORTS_DIR = "reports"
HISTORY_DIR = "database/history"
RESUME_JSON_PATH = "resumes/resume.json"
PROMPT_TEMPLATE_PATH = "prompts/interview_prep.md"


def load_job_context(company: str) -> dict:
    """Load the stored JD and resume data for a specific company.
    Returns a dict with 'job_description', 'resume_json', 'company'."""
    context = {"company": company, "job_description": "", "resume_json": {}}

    # Load job description from history
    jd_path = os.path.join(HISTORY_DIR, company, "jd.txt")
    if os.path.exists(jd_path):
        with open(jd_path, "r", encoding="utf-8") as f:
            context["job_description"] = f.read().strip()
    else:
        # Try with sanitized company name
        import re
        safe_company = re.sub(r"[^A-Za-z0-9_-]", "_", company)
        alt_path = os.path.join(HISTORY_DIR, safe_company, "jd.txt")
        if os.path.exists(alt_path):
            with open(alt_path, "r", encoding="utf-8") as f:
                context["job_description"] = f.read().strip()

    # Load resume JSON
    if os.path.exists(RESUME_JSON_PATH):
        with open(RESUME_JSON_PATH, "r", encoding="utf-8") as f:
            context["resume_json"] = json.load(f)

    # Load metadata if available
    metadata_path = os.path.join(HISTORY_DIR, company, "metadata.json")
    if os.path.exists(metadata_path):
        with open(metadata_path, "r", encoding="utf-8") as f:
            context["metadata"] = json.load(f)

    return context


def generate_question_set(job_context: dict) -> dict:
    """LLM call to Groq producing categorized interview questions
    grounded in the actual JD + resume skills."""
    with open(PROMPT_TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = f.read()

    # Extract key info for the prompt
    resume = job_context.get("resume_json", {})
    skills = resume.get("skills", [])
    experience = resume.get("experience", [])

    experience_summary = "; ".join(
        f"{e.get('title', '')} at {e.get('company', '')} "
        f"({e.get('start_date', '')} - {e.get('end_date', '')})"
        for e in experience
    ) or "No experience listed."

    projects_summary = "; ".join(
        f"{p.get('name', '')}: {p.get('description', '')}"
        for p in resume.get("projects", [])
    ) or "No projects listed."

    prompt = (
        template
        .replace("{company}", job_context.get("company", ""))
        .replace("{job_description}", job_context.get("job_description", "")[:2000])
        .replace("{skills}", ", ".join(skills))
        .replace("{experience_summary}", experience_summary)
        .replace("{projects_summary}", projects_summary)
    )

    result = call_groq_json(prompt)

    # Validate the expected structure
    expected_keys = [
        "language_specific", "dsa", "system_design",
        "behavioral", "coding_problems",
    ]
    for key in expected_keys:
        if key not in result:
            result[key] = []

    return result


def write_report(company: str, questions: dict) -> str:
    """Save the interview prep report as JSON and as a readable Markdown file."""
    os.makedirs(REPORTS_DIR, exist_ok=True)

    import re
    safe_company = re.sub(r"[^A-Za-z0-9_-]", "_", company)

    # JSON report
    json_path = os.path.join(REPORTS_DIR, f"{safe_company}_interview_prep.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(questions, f, indent=2)

    # Markdown report for easy reading
    md_path = os.path.join(REPORTS_DIR, f"{safe_company}_interview_prep.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# Interview Prep — {company}\n\n")

        section_titles = {
            "language_specific": "🔧 Language & Framework Specific",
            "dsa": "📊 Data Structures & Algorithms",
            "system_design": "🏗️ System Design",
            "behavioral": "🗣️ Behavioral",
            "coding_problems": "💻 Coding Problems",
        }

        for key, title in section_titles.items():
            items = questions.get(key, [])
            if items:
                f.write(f"## {title}\n\n")
                for i, item in enumerate(items, 1):
                    if isinstance(item, dict):
                        q = item.get("question", item.get("title", str(item)))
                        hint = item.get("hint", item.get("approach", ""))
                        f.write(f"{i}. **{q}**\n")
                        if hint:
                            f.write(f"   - *Hint: {hint}*\n")
                    else:
                        f.write(f"{i}. {item}\n")
                f.write("\n")

    print(f"  [interview] Reports saved: {json_path}, {md_path}")
    return json_path


def run_interview_agent(state: CareerAgentState) -> dict:
    """LangGraph node for the standalone interview-prep graph.
    Expects state['interview_company'] to be set by the caller."""
    company = state.get("interview_company")
    if not company:
        return {"errors": ["interview_agent: no interview_company set in state"]}

    try:
        print(f"  [interview] Generating prep for: {company}")
        context = load_job_context(company)

        if not context.get("job_description"):
            return {"errors": [
                f"interview_agent[{company}]: No job description found. "
                f"Make sure the company has been tracked first "
                f"(check database/history/{company}/jd.txt)."
            ]}

        questions = generate_question_set(context)
        write_report(company, questions)
        return {"interview_questions": questions}

    except Exception as e:
        return {"errors": [f"interview_agent[{company}]: {e}"]}
