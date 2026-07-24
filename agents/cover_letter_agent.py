"""
Agent 5 — Cover Letter Agent

Generates a distinct .docx cover letter per company, grounded in
resume_json + the specific job description so each letter references real
projects/skills rather than generic filler.

Uses the call_groq_json pattern from the matcher agent for the LLM call,
then renders the prose into a clean, professional .docx via python-docx.
"""

import json
import os
import re
from datetime import date

from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

from graph_flow.state import CareerAgentState, MatchResult
from utils.llm_json import call_groq_json

OUTPUT_DIR = "cover_letters"
PROMPT_TEMPLATE_PATH = "prompts/cover_letter.md"


def draft_cover_letter_text(resume_json: dict, match: MatchResult, job_description: str) -> str:
    """LLM call to draft the letter body grounded in real resume content.
    Returns the cover letter text as a string."""
    with open(PROMPT_TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = f.read()

    # Build a concise resume summary for the prompt (don't send the entire thing)
    resume_summary = {
        "name": resume_json.get("personal_info", {}).get("name", ""),
        "skills": resume_json.get("skills", []),
        "experience": [
            {
                "title": exp.get("title", ""),
                "company": exp.get("company", ""),
                "bullets": exp.get("bullets", [])[:3],  # top 3 bullets per role
            }
            for exp in resume_json.get("experience", [])[:3]  # top 3 roles
        ],
        "projects": [
            {
                "name": proj.get("name", ""),
                "description": proj.get("description", ""),
            }
            for proj in resume_json.get("projects", [])[:2]  # top 2 projects
        ],
    }

    prompt = (
        template
        .replace("{resume_json}", json.dumps(resume_summary, indent=2))
        .replace("{job_description}", job_description[:2000])  # cap JD length
        .replace("{matched_skills}", ", ".join(match.get("matched_skills", [])))
    )

    result = call_groq_json(prompt)

    # Handle both {cover_letter: "..."} and {"letter": "..."} patterns
    letter_text = (
        result.get("cover_letter")
        or result.get("letter")
        or result.get("body")
        or result.get("text")
        or ""
    )

    if not letter_text:
        # If the model returned the full text as a single key, try the first string value
        for v in result.values():
            if isinstance(v, str) and len(v) > 100:
                letter_text = v
                break

    if not letter_text:
        raise ValueError("LLM returned empty cover letter text")

    return letter_text


def render_cover_letter_docx(company: str, role: str, letter_text: str, personal_info: dict) -> str:
    """Render letter_text into a clean, professional .docx file.
    Returns the output filepath."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    safe_company = re.sub(r"[^A-Za-z0-9_-]", "_", company)
    path = os.path.join(OUTPUT_DIR, f"{safe_company}.docx")

    doc = Document()

    # Page margins
    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)

    # ── Header: Candidate name ──
    name = personal_info.get("name", "")
    if name:
        name_para = doc.add_paragraph()
        name_para.alignment = WD_ALIGN_PARAGRAPH.LEFT
        name_run = name_para.add_run(name)
        name_run.font.size = Pt(16)
        name_run.font.bold = True
        name_run.font.color.rgb = RGBColor(0x1A, 0x1A, 0x2E)

    # ── Contact line ──
    contact_parts = [
        personal_info.get("email", ""),
        personal_info.get("phone", ""),
        personal_info.get("location", ""),
    ]
    contact_line = " | ".join(p for p in contact_parts if p)
    if contact_line:
        contact_para = doc.add_paragraph()
        contact_para.alignment = WD_ALIGN_PARAGRAPH.LEFT
        contact_run = contact_para.add_run(contact_line)
        contact_run.font.size = Pt(9)
        contact_run.font.color.rgb = RGBColor(0x55, 0x55, 0x55)

    # ── LinkedIn / GitHub ──
    links = []
    if personal_info.get("linkedin"):
        links.append(personal_info["linkedin"])
    if personal_info.get("github"):
        links.append(personal_info["github"])
    if links:
        links_para = doc.add_paragraph()
        links_para.alignment = WD_ALIGN_PARAGRAPH.LEFT
        links_run = links_para.add_run(" | ".join(links))
        links_run.font.size = Pt(9)
        links_run.font.color.rgb = RGBColor(0x33, 0x66, 0x99)

    # ── Horizontal rule ──
    doc.add_paragraph("_" * 60)

    # ── Date ──
    date_para = doc.add_paragraph()
    date_para.alignment = WD_ALIGN_PARAGRAPH.LEFT
    date_run = date_para.add_run(date.today().strftime("%B %d, %Y"))
    date_run.font.size = Pt(10)

    # ── Regarding line ──
    re_para = doc.add_paragraph()
    re_run = re_para.add_run(f"RE: Application for {role} at {company}")
    re_run.font.size = Pt(10)
    re_run.font.bold = True

    # ── Greeting ──
    doc.add_paragraph()
    greeting = doc.add_paragraph()
    greeting_run = greeting.add_run("Dear Hiring Manager,")
    greeting_run.font.size = Pt(11)

    # ── Letter body ──
    # Split into paragraphs on double newlines or single newlines
    paragraphs = re.split(r"\n\n+", letter_text.strip())
    for para_text in paragraphs:
        # Clean up any single newlines within a paragraph
        clean_text = para_text.strip().replace("\n", " ")
        if clean_text:
            para = doc.add_paragraph()
            para_run = para.add_run(clean_text)
            para_run.font.size = Pt(11)
            # Set paragraph spacing
            para.paragraph_format.space_after = Pt(6)

    # ── Sign-off ──
    doc.add_paragraph()
    signoff = doc.add_paragraph()
    signoff_run = signoff.add_run("Sincerely,")
    signoff_run.font.size = Pt(11)

    if name:
        name_signoff = doc.add_paragraph()
        name_signoff_run = name_signoff.add_run(name)
        name_signoff_run.font.size = Pt(11)
        name_signoff_run.font.bold = True

    doc.save(path)
    return path


def run_cover_letter_agent(state: CareerAgentState) -> dict:
    """LangGraph node. Generates one cover letter per qualified match."""
    resume_json = state.get("resume_json", {})
    matches = state.get("qualified_matches", [])
    jobs_by_id = {j.get("job_id"): j for j in state.get("normalized_jobs", [])}

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    cover_letters = {}
    errors = []

    personal_info = resume_json.get("personal_info", {})

    for match in matches:
        company = match["company"]
        role = match.get("role", "")
        job = jobs_by_id.get(match.get("job_id"), {})

        try:
            text = draft_cover_letter_text(
                resume_json, match, job.get("description", "")
            )
            path = render_cover_letter_docx(company, role, text, personal_info)
            cover_letters[company] = path
            print(f"  [cover_letter] Generated: {path}")
        except Exception as e:
            errors.append(f"cover_letter_agent[{company}]: {e}")

    return {"cover_letters": cover_letters, "errors": errors}
