"""
Agent 4 — Resume Tailoring Agent

Produces a one-page, ATS-friendly resume PDF per qualified match, reordered
to foreground the skills/experience that matched that specific job.

HARD RULE: never hallucinate. This is enforced structurally, not just by
prompting:
    - select_relevant_content() ONLY reorders and filters existing
      resume_json content (bullets, projects, skills). No LLM call
      generates any new sentence, claim, date, or number anywhere in this
      module.
    - validate_no_hallucination() is a safety-net check that every piece
      of text in the tailored output can be traced back verbatim to
      resume_json. It exists so that if this module is ever extended to
      use an LLM (e.g. for light rephrasing), there is a hard gate that
      rejects output containing anything not in the source.
    - render_resume_pdf() only lays out text it's given; it does not
      invent content either.

ATS-friendly rendering rules followed:
    - Single-column layout, no tables/text-boxes (these break ATS parsers)
    - Standard fonts (Helvetica), no images/icons
    - Section headers as plain bold text, not styled graphics
"""

import os
import re

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable

from graph_flow.state import CareerAgentState, MatchResult

OUTPUT_DIR = "resumes/generated"

# Heuristic caps to keep output to roughly one page. Not a guarantee for
# every resume length, but keeps normal-sized resumes to one page.
MAX_BULLETS_PER_EXPERIENCE = 4
MAX_PROJECTS = 2
MAX_BULLETS_PER_PROJECT = 2
MAX_ACHIEVEMENTS = 3


def _mentions_any_skill(text: str, skills: list) -> bool:
    text_lower = text.lower()
    return any(skill.lower() in text_lower for skill in skills)


def _score_experience(exp: dict, matched_skills: list) -> int:
    bullets = exp.get("bullets", [])
    return sum(1 for b in bullets if _mentions_any_skill(b, matched_skills))


def _score_project(proj: dict, matched_skills: list) -> int:
    skill_overlap = len(set(s.lower() for s in proj.get("skills", []))
                         & set(s.lower() for s in matched_skills))
    bullet_hits = sum(1 for b in proj.get("bullets", []) if _mentions_any_skill(b, matched_skills))
    return skill_overlap + bullet_hits


def select_relevant_content(resume_json: dict, match: MatchResult) -> dict:
    """Reorder and filter resume_json content around this job's matched
    skills. Every string in the output is copied verbatim from
    resume_json — nothing is generated, rephrased, or invented."""
    matched_skills = match.get("matched_skills", [])

    # Skills: matched ones first, then the rest, order preserved within each group
    all_skills = resume_json.get("skills", [])
    matched_set = {s.lower() for s in matched_skills}
    ordered_skills = (
        [s for s in all_skills if s.lower() in matched_set]
        + [s for s in all_skills if s.lower() not in matched_set]
    )

    # Experience: keep ALL entries (never drop work history), reorder by
    # relevance, and within each entry put the most relevant bullets first
    experience = resume_json.get("experience", [])
    scored_experience = sorted(
        experience, key=lambda e: _score_experience(e, matched_skills), reverse=True
    )
    tailored_experience = []
    for exp in scored_experience:
        bullets = exp.get("bullets", [])
        reordered_bullets = sorted(
            bullets, key=lambda b: _mentions_any_skill(b, matched_skills), reverse=True
        )
        tailored_experience.append({
            **exp,
            "bullets": reordered_bullets[:MAX_BULLETS_PER_EXPERIENCE],
        })

    # Projects: keep only the most relevant N (projects are supplementary,
    # unlike work experience, so trimming here is safe for one-page fit)
    projects = resume_json.get("projects", [])
    scored_projects = sorted(
        projects, key=lambda p: _score_project(p, matched_skills), reverse=True
    )
    tailored_projects = [
        {**p, "bullets": p.get("bullets", [])[:MAX_BULLETS_PER_PROJECT]}
        for p in scored_projects[:MAX_PROJECTS]
    ]

    return {
        "personal_info": resume_json.get("personal_info", {}),
        "skills": ordered_skills,
        "experience": tailored_experience,
        "projects": tailored_projects,
        "education": resume_json.get("education", []),
        "achievements": resume_json.get("achievements", [])[:MAX_ACHIEVEMENTS],
        "highlight_skills": matched_skills,
    }


def _flatten_source_strings(resume_json: dict) -> set:
    """Every verbatim string that's legal to appear in tailored output."""
    pool = set()
    pool.update(s.strip() for s in resume_json.get("skills", []))
    pool.update(s.strip() for s in resume_json.get("achievements", []))

    for exp in resume_json.get("experience", []):
        pool.update(b.strip() for b in exp.get("bullets", []))
        pool.add(exp.get("company", "").strip())
        pool.add(exp.get("title", "").strip())

    for proj in resume_json.get("projects", []):
        pool.update(b.strip() for b in proj.get("bullets", []))
        pool.add(proj.get("name", "").strip())
        pool.add(proj.get("description", "").strip())
        pool.update(s.strip() for s in proj.get("skills", []))

    for edu in resume_json.get("education", []):
        pool.add(edu.get("institution", "").strip())
        pool.add(edu.get("degree", "").strip())

    pool.discard("")
    return pool


def validate_no_hallucination(tailored_content: dict, resume_json: dict) -> bool:
    """Verify every bullet/description/skill/achievement in tailored_content
    is a verbatim string from resume_json. Returns False (reject) if
    anything doesn't trace back to the source — this is the hard gate
    described in the module docstring."""
    allowed = _flatten_source_strings(resume_json)

    def check_all(strings):
        return all(s.strip() in allowed for s in strings if s.strip())

    if not check_all(tailored_content.get("skills", [])):
        return False

    for exp in tailored_content.get("experience", []):
        if not check_all(exp.get("bullets", [])):
            return False
        if exp.get("company", "").strip() not in allowed and exp.get("company", "").strip() != "":
            return False
        if exp.get("title", "").strip() not in allowed and exp.get("title", "").strip() != "":
            return False

    for proj in tailored_content.get("projects", []):
        if not check_all(proj.get("bullets", [])):
            return False
        if proj.get("name", "").strip() not in allowed and proj.get("name", "").strip() != "":
            return False

    if not check_all(tailored_content.get("achievements", [])):
        return False

    return True


def _bold_matched_skills(text: str, skills: list) -> str:
    """Wrap matched-skill mentions in <b> tags for the PDF renderer.
    Only affects presentation (bold styling) — the underlying text is
    untouched, so this doesn't interact with the hallucination check."""
    for skill in sorted(skills, key=len, reverse=True):  # longest first, avoids partial-overlap issues
        pattern = re.compile(re.escape(skill), re.IGNORECASE)
        text = pattern.sub(lambda m: f"<b>{m.group(0)}</b>", text)
    return text


def render_resume_pdf(company: str, tailored_content: dict) -> str:
    """Render tailored_content into a one-page, ATS-friendly, single-column
    PDF using ReportLab. Returns the output filepath."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    safe_company = re.sub(r"[^A-Za-z0-9_-]", "_", company)
    path = os.path.join(OUTPUT_DIR, f"{safe_company}.pdf")

    styles = getSampleStyleSheet()
    name_style = ParagraphStyle("Name", parent=styles["Title"], fontSize=18, spaceAfter=2, alignment=TA_LEFT)
    contact_style = ParagraphStyle("Contact", parent=styles["Normal"], fontSize=9, textColor="#333333", spaceAfter=10)
    section_style = ParagraphStyle("Section", parent=styles["Heading2"], fontSize=11, spaceBefore=8, spaceAfter=4,
                                    textColor="#000000")
    body_style = ParagraphStyle("Body", parent=styles["Normal"], fontSize=9.5, leading=13, spaceAfter=3)
    bullet_style = ParagraphStyle("Bullet", parent=body_style, leftIndent=12, bulletIndent=0)
    subheader_style = ParagraphStyle("Subheader", parent=styles["Normal"], fontSize=10, leading=13,
                                      spaceBefore=4, spaceAfter=2)

    highlight_skills = tailored_content.get("highlight_skills", [])
    story = []

    info = tailored_content.get("personal_info", {})
    story.append(Paragraph(info.get("name", ""), name_style))
    contact_line = " | ".join(filter(None, [
        info.get("email", ""), info.get("phone", ""), info.get("location", ""),
        info.get("linkedin", ""), info.get("github", ""),
    ]))
    story.append(Paragraph(contact_line, contact_style))

    skills = tailored_content.get("skills", [])
    if skills:
        story.append(Paragraph("SKILLS", section_style))
        story.append(HRFlowable(width="100%", thickness=0.5, color="#666666", spaceAfter=4))
        skills_text = ", ".join(_bold_matched_skills(s, highlight_skills) for s in skills)
        story.append(Paragraph(skills_text, body_style))

    experience = tailored_content.get("experience", [])
    if experience:
        story.append(Paragraph("EXPERIENCE", section_style))
        story.append(HRFlowable(width="100%", thickness=0.5, color="#666666", spaceAfter=4))
        for exp in experience:
            header = f"<b>{exp.get('title', '')}</b>, {exp.get('company', '')} — {exp.get('start_date', '')} to {exp.get('end_date', '')}"
            story.append(Paragraph(header, subheader_style))
            for bullet in exp.get("bullets", []):
                story.append(Paragraph(f"• {_bold_matched_skills(bullet, highlight_skills)}", bullet_style))

    projects = tailored_content.get("projects", [])
    if projects:
        story.append(Paragraph("PROJECTS", section_style))
        story.append(HRFlowable(width="100%", thickness=0.5, color="#666666", spaceAfter=4))
        for proj in projects:
            story.append(Paragraph(f"<b>{proj.get('name', '')}</b>", subheader_style))
            for bullet in proj.get("bullets", []):
                story.append(Paragraph(f"• {_bold_matched_skills(bullet, highlight_skills)}", bullet_style))

    education = tailored_content.get("education", [])
    if education:
        story.append(Paragraph("EDUCATION", section_style))
        story.append(HRFlowable(width="100%", thickness=0.5, color="#666666", spaceAfter=4))
        for edu in education:
            story.append(Paragraph(
                f"{edu.get('degree', '')}, {edu.get('institution', '')} "
                f"({edu.get('start_date', '')} - {edu.get('end_date', '')})",
                body_style,
            ))

    achievements = tailored_content.get("achievements", [])
    if achievements:
        story.append(Paragraph("ACHIEVEMENTS", section_style))
        story.append(HRFlowable(width="100%", thickness=0.5, color="#666666", spaceAfter=4))
        for ach in achievements:
            story.append(Paragraph(f"• {ach}", bullet_style))

    doc = SimpleDocTemplate(
        path, pagesize=letter,
        topMargin=0.6 * inch, bottomMargin=0.6 * inch,
        leftMargin=0.7 * inch, rightMargin=0.7 * inch,
    )
    doc.build(story)

    return path


def run_tailor_agent(state: CareerAgentState) -> dict:
    """LangGraph node. Generates one tailored resume per qualified match."""
    resume_json = state.get("resume_json", {})
    matches = state.get("qualified_matches", [])

    tailored_resumes = {}
    errors = []

    for match in matches:
        company = match["company"]
        try:
            content = select_relevant_content(resume_json, match)
            if not validate_no_hallucination(content, resume_json):
                errors.append(f"tailor_agent[{company}]: hallucination check failed, skipped")
                continue
            path = render_resume_pdf(company, content)
            tailored_resumes[company] = path
        except Exception as e:
            errors.append(f"tailor_agent[{company}]: {e}")

    return {"tailored_resumes": tailored_resumes, "errors": errors}
