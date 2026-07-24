"""
Agent 11 — Learning Agent

Analyzes all match results to detect trending missing skills across job
listings and recommends learning priorities. This is the feedback loop
that improves your job search over time.

Logic:
    1. Aggregate missing_skills from all qualified matches
    2. Rank by frequency (Docker requested by 50 companies → top priority)
    3. Cross-reference with known skill categories for time estimates
    4. Generate a prioritized learning plan saved to reports/

This agent runs at the end of the pipeline and also examines historical
data from past pipeline runs (via applications.csv).
"""

import csv
import json
import os
from collections import Counter
from datetime import date

from graph_flow.state import CareerAgentState

REPORTS_DIR = "reports"
APPLICATIONS_CSV = "database/applications.csv"

# Estimated learning times by skill category (in days).
# These are rough heuristics; the user can adjust.
SKILL_LEARNING_ESTIMATES = {
    # DevOps / Cloud
    "docker": 3,
    "kubernetes": 7,
    "aws": 14,
    "azure": 14,
    "gcp": 14,
    "terraform": 5,
    "ci/cd": 3,
    "jenkins": 3,
    "github actions": 2,

    # Backend frameworks
    "spring boot": 7,
    "django": 7,
    "flask": 3,
    "fastapi": 3,
    ".net": 10,
    "node.js": 5,
    "express": 3,
    "nest.js": 5,

    # Frontend
    "react": 7,
    "angular": 10,
    "vue": 5,
    "next.js": 5,
    "typescript": 5,

    # Mobile
    "flutter": 7,
    "react native": 7,
    "jetpack compose": 5,
    "swiftui": 7,
    "kotlin": 5,

    # Data / ML
    "python": 5,
    "pandas": 3,
    "sql": 5,
    "nosql": 3,
    "mongodb": 3,
    "postgresql": 5,
    "redis": 2,
    "kafka": 5,
    "spark": 7,

    # Architecture
    "microservices": 5,
    "system design": 14,
    "rest apis": 3,
    "graphql": 3,
    "grpc": 3,

    # Testing
    "unit testing": 3,
    "integration testing": 3,
    "selenium": 3,
    "jest": 2,

    # General
    "git": 2,
    "linux": 5,
    "agile": 2,
    "scrum": 2,
    "jira": 1,
    "data structures": 14,
    "algorithms": 14,
    "problem solving": 14,
}

# Skill category groupings for the report
SKILL_CATEGORIES = {
    "Cloud & DevOps": [
        "docker", "kubernetes", "aws", "azure", "gcp", "terraform",
        "ci/cd", "jenkins", "github actions",
    ],
    "Backend": [
        "spring boot", "django", "flask", "fastapi", ".net", "node.js",
        "express", "nest.js", "go", "java", "c#",
    ],
    "Frontend": [
        "react", "angular", "vue", "next.js", "typescript",
        "javascript", "html/css", "tailwind",
    ],
    "Mobile": [
        "flutter", "react native", "jetpack compose", "swiftui",
        "android", "ios", "kotlin", "swift", "dart",
    ],
    "Data & Infrastructure": [
        "sql", "nosql", "mongodb", "postgresql", "mysql", "redis",
        "kafka", "rabbitmq", "elasticsearch",
    ],
    "CS Fundamentals": [
        "data structures", "algorithms", "system design",
        "problem solving", "design patterns",
    ],
}


def _estimate_days(skill: str) -> int:
    """Estimate learning days for a skill. Uses the lookup table,
    falls back to 5 days for unknown skills."""
    return SKILL_LEARNING_ESTIMATES.get(skill.lower(), 5)


def _categorize_skill(skill: str) -> str:
    """Determine which category a skill belongs to."""
    skill_lower = skill.lower()
    for category, skills_list in SKILL_CATEGORIES.items():
        if skill_lower in skills_list:
            return category
    return "Other"


def analyze_missing_skills(state: CareerAgentState) -> dict:
    """Aggregate missing skills from current pipeline run + historical data."""
    missing_counter = Counter()

    # 1. Current run's qualified matches
    for match in state.get("qualified_matches", []):
        for skill in match.get("missing_skills", []):
            missing_counter[skill] += 1

    # 2. Historical: also count from all matches (not just qualified)
    for match in state.get("matches", []):
        for skill in match.get("missing_skills", []):
            missing_counter[skill] += 1

    return dict(missing_counter)


def generate_learning_report(missing_skills: dict, total_jobs: int) -> dict:
    """Generate a prioritized learning report from aggregated missing skills."""
    if not missing_skills:
        return {
            "generated_at": date.today().isoformat(),
            "total_jobs_analyzed": total_jobs,
            "message": "No missing skills detected — your resume covers all job requirements!",
            "recommendations": [],
        }

    # Sort by frequency (most requested first)
    sorted_skills = sorted(missing_skills.items(), key=lambda x: x[1], reverse=True)

    recommendations = []
    for skill, count in sorted_skills[:15]:  # top 15
        demand_pct = round(100.0 * count / max(total_jobs, 1), 1)
        est_days = _estimate_days(skill)
        category = _categorize_skill(skill)

        # Priority scoring: frequency × demand percentage
        priority_score = count * demand_pct

        recommendations.append({
            "skill": skill,
            "requested_by": count,
            "demand_percentage": demand_pct,
            "estimated_days": est_days,
            "category": category,
            "priority": "HIGH" if demand_pct >= 40 else ("MEDIUM" if demand_pct >= 20 else "LOW"),
            "priority_score": round(priority_score, 1),
        })

    # Sort by priority score
    recommendations.sort(key=lambda x: x["priority_score"], reverse=True)

    # Category summary
    category_counts = Counter()
    for rec in recommendations:
        category_counts[rec["category"]] += rec["requested_by"]

    report = {
        "generated_at": date.today().isoformat(),
        "total_jobs_analyzed": total_jobs,
        "total_skill_gaps": len(missing_skills),
        "top_missing_skills": [r["skill"] for r in recommendations[:5]],
        "estimated_total_learning_days": sum(r["estimated_days"] for r in recommendations[:5]),
        "category_summary": dict(category_counts.most_common()),
        "recommendations": recommendations,
    }

    return report


def save_learning_report(report: dict) -> str:
    """Save the learning report as JSON and readable Markdown."""
    os.makedirs(REPORTS_DIR, exist_ok=True)

    # JSON
    json_path = os.path.join(REPORTS_DIR, "learning_report.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    # Markdown
    md_path = os.path.join(REPORTS_DIR, "learning_report.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# 📚 Learning Recommendations\n\n")
        f.write(f"*Generated: {report.get('generated_at', 'N/A')}*\n\n")
        f.write(f"**Jobs analyzed:** {report.get('total_jobs_analyzed', 0)}\n")
        f.write(f"**Skill gaps found:** {report.get('total_skill_gaps', 0)}\n")

        top = report.get("top_missing_skills", [])
        if top:
            f.write(f"**Top missing:** {', '.join(top)}\n")
            f.write(f"**Est. learning time (top 5):** ~{report.get('estimated_total_learning_days', 0)} days\n\n")

        # Category summary
        cat_summary = report.get("category_summary", {})
        if cat_summary:
            f.write("## 📊 By Category\n\n")
            f.write("| Category | Demand |\n")
            f.write("|----------|--------|\n")
            for cat, count in cat_summary.items():
                f.write(f"| {cat} | {count} requests |\n")
            f.write("\n")

        # Detailed recommendations
        recs = report.get("recommendations", [])
        if recs:
            f.write("## 🎯 Prioritized Learning Plan\n\n")
            for i, rec in enumerate(recs, 1):
                priority_emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(
                    rec["priority"], "⚪"
                )
                f.write(
                    f"{i}. {priority_emoji} **{rec['skill']}** — "
                    f"requested by {rec['requested_by']} companies "
                    f"({rec['demand_percentage']}%) — "
                    f"~{rec['estimated_days']} days to learn "
                    f"[{rec['category']}]\n"
                )

    print(f"  [learning] Reports saved: {json_path}, {md_path}")
    return json_path


def run_learning_agent(state: CareerAgentState) -> dict:
    """LangGraph node. Analyzes skill gaps and generates learning
    recommendations. Runs after analytics in the main pipeline."""
    try:
        missing_skills = analyze_missing_skills(state)
        total_jobs = len(state.get("normalized_jobs", []))
        report = generate_learning_report(missing_skills, total_jobs)
        save_learning_report(report)

        print(f"  [learning] {report.get('total_skill_gaps', 0)} skill gaps found")
        if report.get("top_missing_skills"):
            print(f"  [learning] Top missing: {', '.join(report['top_missing_skills'][:5])}")

        return {"learning_report": report}

    except Exception as e:
        return {"errors": [f"learning_agent: {e}"]}
