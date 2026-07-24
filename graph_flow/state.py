"""
Shared state definition for the AI Career Agent LangGraph pipeline.

Every node in graph.py receives the full CareerAgentState and returns a
partial dict of the keys it updates. LangGraph merges these automatically.
"""

from typing import TypedDict, List, Dict, Optional, Annotated
import operator


class Job(TypedDict, total=False):
    company: str
    role: str
    location: Optional[str]
    skills: List[str]
    salary: Optional[str]
    description: str
    source: str          # linkedin | naukri | wellfound | greenhouse | lever | yc | careers_page | local
    url: Optional[str]
    posted_at: Optional[str]
    job_id: str           # stable hash used across the pipeline


class MatchResult(TypedDict, total=False):
    job_id: str
    company: str
    role: str
    score: float                 # 0-100
    matched_skills: List[str]
    missing_skills: List[str]
    keyword_overlap: float
    experience_fit: float


class ContactInfo(TypedDict, total=False):
    company: str
    hiring_manager: Optional[str]
    recruiter: Optional[str]
    email: Optional[str]
    linkedin_url: Optional[str]
    source: str


class CareerAgentState(TypedDict, total=False):
    # --- Resume Knowledge Agent ---
    resume_path: str
    resume_json: Dict
    resume_embeddings_ready: bool

    # --- Job Discovery ---
    raw_jobs: List[Job]
    normalized_jobs: List[Job]

    # --- Matching ---
    match_threshold: float          # e.g. 70.0
    matches: List[MatchResult]
    qualified_matches: List[MatchResult]   # matches >= threshold

    # --- Tailoring / Cover letters ---
    tailored_resumes: Dict[str, str]     # company -> resume filepath
    cover_letters: Dict[str, str]        # company -> cover letter filepath

    # --- Recruiter research ---
    contacts: Dict[str, ContactInfo]     # company -> contact info

    # --- Tracker ---
    tracker_rows: List[Dict]             # rows appended to applications.csv

    # --- Interview prep (triggered separately, not in the main linear flow) ---
    interview_company: Optional[str]
    interview_questions: Optional[Dict]

    # --- Analytics / Learning ---
    analytics: Dict
    missing_skill_report: Dict
    learning_report: Dict                # Agent 11: skill gap analysis + recommendations

    # --- Notifications ---
    notifications_sent: bool

    # errors accumulate across nodes instead of overwriting
    errors: Annotated[List[str], operator.add]
