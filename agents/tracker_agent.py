"""
Agent 8 — Application Tracker Agent

Appends one row per qualified match to database/applications.csv and
snapshots the artifacts (resume, cover letter, JD, contact info) into a
per-company folder under database/history/{company}/.

CSV columns: Company, Role, Match, Applied, Status, Resume, CoverLetter

TODO:
    - update_status(): a separate manual/CLI entrypoint for you to flip a
      row's Status (Applied -> Interview -> Rejected/Offer) as things
      progress in real life — this is what should trigger the Interview
      Agent and feed the Analytics Agent
"""

import csv
import os
import shutil
from datetime import date

from graph_flow.state import CareerAgentState

APPLICATIONS_CSV = "database/applications.csv"
HISTORY_DIR = "database/history"
CSV_FIELDS = ["Company", "Role", "Match", "Applied", "Status", "Resume", "CoverLetter"]


def _ensure_csv_header():
    if not os.path.exists(APPLICATIONS_CSV):
        os.makedirs(os.path.dirname(APPLICATIONS_CSV), exist_ok=True)
        with open(APPLICATIONS_CSV, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=CSV_FIELDS).writeheader()


def append_application_row(row: dict):
    _ensure_csv_header()
    with open(APPLICATIONS_CSV, "a", newline="") as f:
        csv.DictWriter(f, fieldnames=CSV_FIELDS).writerow(row)


def snapshot_company_artifacts(company: str, resume_path: str, cover_letter_path: str, job_description: str):
    company_dir = os.path.join(HISTORY_DIR, company)
    os.makedirs(company_dir, exist_ok=True)

    if resume_path and os.path.exists(resume_path):
        shutil.copy(resume_path, os.path.join(company_dir, "resume.pdf"))
    if cover_letter_path and os.path.exists(cover_letter_path):
        shutil.copy(cover_letter_path, os.path.join(company_dir, "cover.docx"))
    with open(os.path.join(company_dir, "jd.txt"), "w") as f:
        f.write(job_description or "")


def update_status(company: str, new_status: str):
    """Manual entrypoint: call this (e.g. from a CLI or the Streamlit
    dashboard) when a company's status changes. Rewrites the matching row
    in applications.csv."""
    if not os.path.exists(APPLICATIONS_CSV):
        return
    rows = []
    with open(APPLICATIONS_CSV, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["Company"] == company:
                row["Status"] = new_status
            rows.append(row)
    with open(APPLICATIONS_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def run_tracker_agent(state: CareerAgentState) -> dict:
    """LangGraph node. Writes a tracker row + artifact snapshot per qualified match."""
    matches = state.get("qualified_matches", [])
    tailored_resumes = state.get("tailored_resumes", {})
    cover_letters = state.get("cover_letters", {})
    jobs_by_id = {j.get("job_id"): j for j in state.get("normalized_jobs", [])}

    tracker_rows = []
    today = date.today().isoformat()

    for match in matches:
        company = match["company"]
        job = jobs_by_id.get(match.get("job_id"), {})
        resume_path = tailored_resumes.get(company, "")
        cover_letter_path = cover_letters.get(company, "")

        row = {
            "Company": company,
            "Role": match.get("role", ""),
            "Match": f"{match.get('score', 0)}%",
            "Applied": today,
            "Status": "Applied",
            "Resume": resume_path,
            "CoverLetter": cover_letter_path,
        }
        append_application_row(row)
        snapshot_company_artifacts(company, resume_path, cover_letter_path, job.get("description", ""))
        tracker_rows.append(row)

    return {"tracker_rows": tracker_rows}
