"""
Agent 2 — Job Discovery Agent

Scrapes/queries job sources and returns a flat list of Job dicts.
Each source gets its own fetch_* function so sources can be added,
disabled, or rate-limited independently.

Working sources:
    - fetch_local_jobs(): reads manually-saved JSON files from jobs/ folder
    - fetch_greenhouse_jobs(): public Greenhouse Job Board API
    - fetch_lever_jobs(): public Lever postings API
    - fetch_remotive_jobs(): free Remotive.com API (no auth needed)

Higher-risk sources (behind config flags, require careful handling):
    - LinkedIn / Naukri / Wellfound: gated behind explicit opt-in flags
"""

import hashlib
import json
import os
import glob
from typing import List

import requests

from graph_flow.state import CareerAgentState, Job
from utils.config import (
    ENABLE_LINKEDIN_SCRAPING,
    ENABLE_NAUKRI_SCRAPING,
    ENABLE_WELLFOUND_SCRAPING,
)

# ──────────────────────────────────────────────────────────────────────
# Configuration: companies/boards to query. Edit these lists or move
# them to a config file once the list grows.
# ──────────────────────────────────────────────────────────────────────
TARGET_GREENHOUSE_BOARDS = [
    # Add Greenhouse board tokens here, e.g.:
    # "stripe", "airbnb", "figma", "notion"
]

TARGET_LEVER_COMPANIES = [
    # Add Lever company slugs here, e.g.:
    # "netflix", "twitch"
]

# Remotive categories to search (see https://remotive.com/api/remote-jobs?category=software-dev)
REMOTIVE_CATEGORIES = ["software-dev"]

# Local JSON files directory
LOCAL_JOBS_DIR = "jobs"

REQUEST_TIMEOUT = 15  # seconds


def _job_id(company: str, role: str) -> str:
    """Stable hash for deduplication across pipeline runs."""
    return hashlib.sha256(f"{company}:{role}".encode()).hexdigest()[:16]


# ──────────────────────────────────────────────────────────────────────
# Source: Local JSON files (always available, great for testing)
# ──────────────────────────────────────────────────────────────────────
def fetch_local_jobs() -> List[Job]:
    """Read job listings from JSON files in the jobs/ directory.
    Each file can be a single Job object or an array of Job objects."""
    jobs = []
    pattern = os.path.join(LOCAL_JOBS_DIR, "*.json")

    for filepath in glob.glob(pattern):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Handle both single object and array
            entries = data if isinstance(data, list) else [data]

            for entry in entries:
                job: Job = {
                    "company": entry.get("company", "Unknown"),
                    "role": entry.get("role", "Unknown"),
                    "location": entry.get("location"),
                    "skills": entry.get("skills", []),
                    "salary": entry.get("salary"),
                    "description": entry.get("description", ""),
                    "source": "local",
                    "url": entry.get("url"),
                    "posted_at": entry.get("posted_at"),
                    "job_id": "",  # assigned later
                }
                jobs.append(job)
        except (json.JSONDecodeError, KeyError) as e:
            print(f"  [discovery] Skipping malformed file {filepath}: {e}")

    return jobs


# ──────────────────────────────────────────────────────────────────────
# Source: Greenhouse Job Board API (public, no auth needed)
# https://developers.greenhouse.io/job-board.html
# ──────────────────────────────────────────────────────────────────────
def fetch_greenhouse_jobs(board_tokens: List[str]) -> List[Job]:
    """GET https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true
    for each board token and map into Job dicts."""
    jobs = []

    for token in board_tokens:
        try:
            url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
            resp = requests.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()

            for posting in data.get("jobs", []):
                # Extract location from first location object
                location = None
                locations = posting.get("location", {})
                if isinstance(locations, dict):
                    location = locations.get("name")

                # Extract skills from content (basic keyword extraction)
                content = posting.get("content", "")
                # Strip HTML tags for the description
                import re
                clean_desc = re.sub(r"<[^>]+>", " ", content)
                clean_desc = re.sub(r"\s+", " ", clean_desc).strip()

                job: Job = {
                    "company": token.replace("-", " ").title(),
                    "role": posting.get("title", "Unknown"),
                    "location": location,
                    "skills": [],  # Greenhouse doesn't have a structured skills field
                    "salary": None,
                    "description": clean_desc[:3000],  # cap length
                    "source": "greenhouse",
                    "url": posting.get("absolute_url"),
                    "posted_at": posting.get("updated_at", "")[:10],
                    "job_id": "",
                }
                jobs.append(job)

        except requests.RequestException as e:
            print(f"  [discovery] Greenhouse board '{token}' failed: {e}")

    return jobs


# ──────────────────────────────────────────────────────────────────────
# Source: Lever Postings API (public, no auth needed)
# https://github.com/lever/postings-api
# ──────────────────────────────────────────────────────────────────────
def fetch_lever_jobs(company_slugs: List[str]) -> List[Job]:
    """GET https://api.lever.co/v0/postings/{slug}?mode=json
    for each company slug and map into Job dicts."""
    jobs = []

    for slug in company_slugs:
        try:
            url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
            resp = requests.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            postings = resp.json()

            if not isinstance(postings, list):
                continue

            for posting in postings:
                # Extract location
                categories = posting.get("categories", {})
                location = categories.get("location")

                # Description from the lists
                desc_parts = []
                for section in posting.get("lists", []):
                    desc_parts.append(section.get("text", ""))
                    for item in section.get("content", "").split("<li>"):
                        import re
                        clean = re.sub(r"<[^>]+>", "", item).strip()
                        if clean:
                            desc_parts.append(clean)

                # Also add the description/additional fields
                import re
                additional = posting.get("additional", "")
                clean_additional = re.sub(r"<[^>]+>", " ", additional).strip()
                if clean_additional:
                    desc_parts.append(clean_additional)

                description = " ".join(desc_parts)[:3000]

                job: Job = {
                    "company": slug.replace("-", " ").title(),
                    "role": posting.get("text", "Unknown"),
                    "location": location,
                    "skills": [],
                    "salary": None,
                    "description": description,
                    "source": "lever",
                    "url": posting.get("hostedUrl"),
                    "posted_at": None,
                    "job_id": "",
                }
                jobs.append(job)

        except requests.RequestException as e:
            print(f"  [discovery] Lever company '{slug}' failed: {e}")

    return jobs


# ──────────────────────────────────────────────────────────────────────
# Source: Remotive.com API (free, no auth, good for demo/testing)
# https://remotive.com/api/remote-jobs
# ──────────────────────────────────────────────────────────────────────
def fetch_remotive_jobs(categories: List[str] = None, limit: int = 20) -> List[Job]:
    """Query the free Remotive API for remote job listings."""
    jobs = []
    categories = categories or REMOTIVE_CATEGORIES

    for category in categories:
        try:
            url = f"https://remotive.com/api/remote-jobs?category={category}&limit={limit}"
            resp = requests.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()

            for posting in data.get("jobs", []):
                import re

                # Clean HTML from description
                raw_desc = posting.get("description", "")
                clean_desc = re.sub(r"<[^>]+>", " ", raw_desc)
                clean_desc = re.sub(r"\s+", " ", clean_desc).strip()

                # Extract tags as skills
                tags = posting.get("tags", [])

                job: Job = {
                    "company": posting.get("company_name", "Unknown"),
                    "role": posting.get("title", "Unknown"),
                    "location": posting.get("candidate_required_location", "Remote"),
                    "skills": tags if isinstance(tags, list) else [],
                    "salary": posting.get("salary"),
                    "description": clean_desc[:3000],
                    "source": "remotive",
                    "url": posting.get("url"),
                    "posted_at": posting.get("publication_date", "")[:10],
                    "job_id": "",
                }
                jobs.append(job)

        except requests.RequestException as e:
            print(f"  [discovery] Remotive category '{category}' failed: {e}")

    return jobs


# ──────────────────────────────────────────────────────────────────────
# LangGraph node
# ──────────────────────────────────────────────────────────────────────
def run_discovery_agent(state: CareerAgentState) -> dict:
    """LangGraph node. Aggregates all enabled sources into raw_jobs.
    Any source that fails is skipped with an error note instead of
    crashing the whole pipeline."""
    jobs: List[Job] = []
    errors: List[str] = []

    # 1. Always load local JSON files (zero risk, always available)
    try:
        local = fetch_local_jobs()
        jobs.extend(local)
        print(f"  [discovery] Local files: {len(local)} jobs loaded")
    except Exception as e:
        errors.append(f"discovery_agent[local]: {e}")

    # 2. Greenhouse (public API, only if boards configured)
    if TARGET_GREENHOUSE_BOARDS:
        try:
            gh_jobs = fetch_greenhouse_jobs(TARGET_GREENHOUSE_BOARDS)
            jobs.extend(gh_jobs)
            print(f"  [discovery] Greenhouse: {len(gh_jobs)} jobs loaded")
        except Exception as e:
            errors.append(f"discovery_agent[greenhouse]: {e}")

    # 3. Lever (public API, only if companies configured)
    if TARGET_LEVER_COMPANIES:
        try:
            lever_jobs = fetch_lever_jobs(TARGET_LEVER_COMPANIES)
            jobs.extend(lever_jobs)
            print(f"  [discovery] Lever: {len(lever_jobs)} jobs loaded")
        except Exception as e:
            errors.append(f"discovery_agent[lever]: {e}")

    # 4. Remotive (free, no auth — enabled by default for demo)
    try:
        remotive = fetch_remotive_jobs()
        jobs.extend(remotive)
        print(f"  [discovery] Remotive: {len(remotive)} jobs loaded")
    except Exception as e:
        errors.append(f"discovery_agent[remotive]: {e}")

    # Assign stable IDs
    for job in jobs:
        job["job_id"] = _job_id(job.get("company", ""), job.get("role", ""))

    print(f"  [discovery] Total: {len(jobs)} jobs discovered")
    return {"raw_jobs": jobs, "errors": errors}
