"""
LangGraph orchestration for the AI Career Agent pipeline.

Flow:
  START
    -> resume_node          (Agent 1: Resume Knowledge Agent, skipped if already embedded)
    -> discovery_node       (Agent 2: Job Discovery)
    -> normalize_node       (dedupe / clean scraped jobs)
    -> match_node           (Agent 3: Resume Match)
    -> filter_node          (keep only matches >= threshold)
    -> tailor_node          (Agent 4: Resume Tailoring)
    -> cover_letter_node    (Agent 5: Cover Letter)
    -> recruiter_node       (Agent 6: Recruiter Research)
    -> tracker_node         (Agent 8: Application Tracker)
    -> analytics_node       (Agent 10: Analytics)
    -> learning_node        (Agent 11: Learning — skill gap detection)
    -> notification_node    (Agent 9: Notification)
    -> END

Agent 7 (Interview Prep) runs as a separate, event-triggered graph:
  - interview_graph runs when a company status flips to "Interview" in the tracker
"""

import os
import sys

# Add the project root to sys.path so that 'python graph_flow/graph.py' works
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from langgraph.graph import StateGraph, START, END

from graph_flow.state import CareerAgentState

from agents.resume_agent import run_resume_agent
from agents.discovery_agent import run_discovery_agent
from agents.matcher_agent import run_matcher_agent
from agents.tailor_agent import run_tailor_agent
from agents.cover_letter_agent import run_cover_letter_agent
from agents.recruiter_agent import run_recruiter_agent
from agents.tracker_agent import run_tracker_agent
from agents.interview_agent import run_interview_agent
from agents.email_agent import run_notification_agent
from agents.learning_agent import run_learning_agent


def normalize_node(state: CareerAgentState) -> dict:
    """Dedupe jobs across sources by (company, role, location) and drop
    postings missing a description, before they hit the match agent."""
    seen = set()
    normalized = []
    for job in state.get("raw_jobs", []):
        key = (job.get("company", "").lower(), job.get("role", "").lower())
        if key in seen or not job.get("description"):
            continue
        seen.add(key)
        normalized.append(job)
    print(f"  [normalize] {len(state.get('raw_jobs', []))} raw -> {len(normalized)} unique jobs")
    return {"normalized_jobs": normalized}


def filter_node(state: CareerAgentState) -> dict:
    """Keep only matches at or above match_threshold (default 70)."""
    threshold = state.get("match_threshold", 70.0)
    qualified = [m for m in state.get("matches", []) if m["score"] >= threshold]
    print(f"  [filter] {len(state.get('matches', []))} matches -> {len(qualified)} qualified (>= {threshold}%)")
    return {"qualified_matches": qualified}


def analytics_node(state: CareerAgentState) -> dict:
    """Agent 10: roll up funnel counts + skill-gap stats from tracker_rows."""
    rows = state.get("tracker_rows", [])
    applied = len(rows)
    interview = sum(1 for r in rows if r.get("status") == "Interview")
    rejected = sum(1 for r in rows if r.get("status") == "Rejected")
    offer = sum(1 for r in rows if r.get("status") == "Offer")

    missing = {}
    for m in state.get("qualified_matches", []):
        for skill in m.get("missing_skills", []):
            missing[skill] = missing.get(skill, 0) + 1
    top_missing = dict(sorted(missing.items(), key=lambda kv: kv[1], reverse=True)[:10])

    analytics = {
        "applied": applied,
        "interview": interview,
        "rejected": rejected,
        "offer": offer,
        "total_matches": len(state.get("matches", [])),
        "qualified_matches": len(state.get("qualified_matches", [])),
    }

    print(f"  [analytics] Applied: {applied}, Qualified: {analytics['qualified_matches']}")

    return {
        "analytics": analytics,
        "missing_skill_report": top_missing,
    }


def build_graph():
    """Build the main linear pipeline graph."""
    graph = StateGraph(CareerAgentState)

    graph.add_node("resume", run_resume_agent)
    graph.add_node("discovery", run_discovery_agent)
    graph.add_node("normalize", normalize_node)
    graph.add_node("match", run_matcher_agent)
    graph.add_node("filter", filter_node)
    graph.add_node("tailor", run_tailor_agent)
    graph.add_node("cover_letter", run_cover_letter_agent)
    graph.add_node("recruiter", run_recruiter_agent)
    graph.add_node("tracker", run_tracker_agent)
    graph.add_node("analytics", analytics_node)
    graph.add_node("learning", run_learning_agent)
    graph.add_node("notification", run_notification_agent)

    graph.add_edge(START, "resume")
    graph.add_edge("resume", "discovery")
    graph.add_edge("discovery", "normalize")
    graph.add_edge("normalize", "match")
    graph.add_edge("match", "filter")
    graph.add_edge("filter", "tailor")
    graph.add_edge("tailor", "cover_letter")
    graph.add_edge("cover_letter", "recruiter")
    graph.add_edge("recruiter", "tracker")
    graph.add_edge("tracker", "analytics")
    graph.add_edge("analytics", "learning")
    graph.add_edge("learning", "notification")
    graph.add_edge("notification", END)

    return graph.compile()


def build_interview_graph():
    """Separate single-node graph triggered when a tracker status becomes
    'Interview' for a given company (Agent 7)."""
    graph = StateGraph(CareerAgentState)
    graph.add_node("interview_prep", run_interview_agent)
    graph.add_edge(START, "interview_prep")
    graph.add_edge("interview_prep", END)
    return graph.compile()


if __name__ == "__main__":
    print("=" * 60)
    print("  AI Career Agent Pipeline")
    print("=" * 60)
    print()

    app = build_graph()

    initial_state: CareerAgentState = {
        "resume_path": "resumes/master_resume.pdf",
        "match_threshold": 70.0,
        "errors": [],
    }

    print("Starting pipeline...\n")
    final_state = app.invoke(initial_state)

    print()
    print("=" * 60)
    print("  Pipeline Results")
    print("=" * 60)
    print(f"  Jobs discovered:    {len(final_state.get('normalized_jobs', []))}")
    print(f"  Total matches:      {len(final_state.get('matches', []))}")
    print(f"  Qualified matches:  {len(final_state.get('qualified_matches', []))}")
    print(f"  Tailored resumes:   {len(final_state.get('tailored_resumes', {}))}")
    print(f"  Cover letters:      {len(final_state.get('cover_letters', {}))}")
    print(f"  Contacts found:     {len(final_state.get('contacts', {}))}")
    print(f"  Analytics:          {final_state.get('analytics', {})}")

    # Show qualified matches
    qualified = final_state.get("qualified_matches", [])
    if qualified:
        print(f"\n  Top matches:")
        for m in sorted(qualified, key=lambda m: m["score"], reverse=True)[:5]:
            print(f"    {m['score']}% — {m['company']} — {m['role']}")

    # Show learning recommendations
    learning = final_state.get("learning_report", {})
    if learning.get("top_missing_skills"):
        print(f"\n  Top missing skills: {', '.join(learning['top_missing_skills'][:5])}")
        print(f"  Est. learning time: ~{learning.get('estimated_total_learning_days', 0)} days")

    if final_state.get("errors"):
        print(f"\n  Warnings/Errors ({len(final_state['errors'])}):")
        for err in final_state["errors"]:
            print(f"    [!] {err}")

    print()
