"""
FastAPI entrypoint exposing the Career Agent pipeline.

Run:
    uvicorn app:app --reload

Endpoints:
    POST /run-pipeline        -> runs the full main graph once
    POST /interview-prep      -> runs the interview-prep graph for one company
    POST /tracker/status      -> manually update a company's tracker status
    GET  /analytics           -> returns the latest analytics snapshot
    GET  /learning            -> returns the latest learning report
    GET  /health              -> health check
"""

import json
import os

# pyrefly: ignore [missing-import]
from fastapi import FastAPI
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from graph_flow.graph import build_graph, build_interview_graph
from agents.tracker_agent import update_status

app = FastAPI(title="AI Career Agent", version="1.0.0")

# Allow Streamlit dashboard to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

main_graph = build_graph()
interview_graph = build_interview_graph()


class PipelineRequest(BaseModel):
    resume_path: str = "resumes/master_resume.pdf"
    match_threshold: float = 70.0


class InterviewRequest(BaseModel):
    company: str


class StatusUpdateRequest(BaseModel):
    company: str
    status: str  # Applied | Interview | Rejected | Offer


@app.post("/run-pipeline")
def run_pipeline(req: PipelineRequest):
    initial_state = {
        "resume_path": req.resume_path,
        "match_threshold": req.match_threshold,
        "errors": [],
    }
    final_state = main_graph.invoke(initial_state)
    return {
        "qualified_matches": final_state.get("qualified_matches", []),
        "analytics": final_state.get("analytics", {}),
        "missing_skill_report": final_state.get("missing_skill_report", {}),
        "learning_report": final_state.get("learning_report", {}),
        "errors": final_state.get("errors", []),
    }


@app.post("/interview-prep")
def run_interview_prep(req: InterviewRequest):
    final_state = interview_graph.invoke({
        "interview_company": req.company,
        "errors": [],
    })
    return {
        "interview_questions": final_state.get("interview_questions", {}),
        "errors": final_state.get("errors", []),
    }


@app.post("/tracker/status")
def set_status(req: StatusUpdateRequest):
    update_status(req.company, req.status)

    result = {"ok": True, "company": req.company, "status": req.status}

    # Auto-trigger interview prep when status becomes Interview
    if req.status == "Interview":
        try:
            prep_state = interview_graph.invoke({
                "interview_company": req.company,
                "errors": [],
            })
            result["interview_questions"] = prep_state.get("interview_questions", {})
        except Exception as e:
            result["interview_prep_error"] = str(e)

    return result


@app.get("/analytics")
def get_analytics():
    """Return the latest analytics from reports."""
    result = {"analytics": {}, "learning_report": {}, "missing_skill_report": {}}

    # Try loading from reports
    learning_path = "reports/learning_report.json"
    if os.path.exists(learning_path):
        with open(learning_path, "r") as f:
            result["learning_report"] = json.load(f)

    # Load latest digest
    digest_path = "reports/latest_digest.txt"
    if os.path.exists(digest_path):
        with open(digest_path, "r") as f:
            result["latest_digest"] = f.read()

    return result


@app.get("/learning")
def get_learning():
    """Return the latest learning report."""
    path = "reports/learning_report.json"
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return {"message": "No learning report available. Run the pipeline first."}


@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}
