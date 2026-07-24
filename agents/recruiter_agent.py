"""
Agent 6 — Recruiter Research Agent

Looks up a plausible hiring manager / recruiter contact for each company
you're applying to, using only public sources:
    - Company careers page scraping (public HTML)
    - Google search for public LinkedIn recruiter profiles

Ethics/legal note: this agent does NOT guess personal emails at scale or
scrape private LinkedIn data. It only uses publicly listed contacts
(careers page "contact us", public recruiter posts) and lets the user
manually verify before outreach.
"""

import json
import os
import re

import requests
from bs4 import BeautifulSoup

from graph_flow.state import CareerAgentState, ContactInfo

CONTACTS_DIR = "database/history"
REQUEST_TIMEOUT = 10

# Common careers page URL patterns
CAREERS_URL_PATTERNS = [
    "https://{company_lower}.com/careers",
    "https://careers.{company_lower}.com",
    "https://www.{company_lower}.com/careers",
    "https://{company_lower}.com/jobs",
    "https://jobs.{company_lower}.com",
]

# Email regex for extracting emails from page text
EMAIL_REGEX = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    re.IGNORECASE,
)

# Common recruiter/HR title keywords
RECRUITER_KEYWORDS = [
    "recruiter", "talent", "hiring", "hr", "human resources",
    "people operations", "talent acquisition",
]


def search_company_careers_page(company: str) -> dict:
    """Fetch the company's careers page and extract any listed
    recruiter/HR contact info (emails, contact names)."""
    company_lower = company.lower().replace(" ", "")
    result = {"email": None, "recruiter": None, "careers_url": None}

    for pattern in CAREERS_URL_PATTERNS:
        url = pattern.format(company_lower=company_lower)
        try:
            resp = requests.get(
                url,
                timeout=REQUEST_TIMEOUT,
                headers={"User-Agent": "Mozilla/5.0 (compatible; CareerAgent/1.0)"},
                allow_redirects=True,
            )
            if resp.status_code == 200:
                result["careers_url"] = url
                soup = BeautifulSoup(resp.text, "html.parser")
                page_text = soup.get_text(separator=" ", strip=True)

                # Extract emails from page
                emails = EMAIL_REGEX.findall(page_text)
                # Filter out common non-recruiter emails
                recruiter_emails = [
                    e for e in emails
                    if not any(skip in e.lower() for skip in [
                        "noreply", "no-reply", "support", "info@", "sales",
                        "marketing", "press", "abuse", "privacy",
                    ])
                ]
                if recruiter_emails:
                    result["email"] = recruiter_emails[0]

                # Look for recruiter/HR names near keywords
                for keyword in RECRUITER_KEYWORDS:
                    if keyword in page_text.lower():
                        # Try to find a name near the keyword
                        idx = page_text.lower().find(keyword)
                        context = page_text[max(0, idx - 100):idx + 100]
                        # Simple name pattern: capitalized words before/after keyword
                        name_match = re.search(
                            r"([A-Z][a-z]+ [A-Z][a-z]+)", context
                        )
                        if name_match:
                            result["recruiter"] = name_match.group(1)
                            break

                break  # found a working careers page, stop trying patterns

        except requests.RequestException:
            continue  # try next URL pattern

    return result


def search_public_linkedin(company: str) -> dict:
    """Construct a public search for recruiters at this company.
    Returns a search URL and any publicly available info.
    NOTE: Does NOT log in or scrape private profiles."""
    result = {
        "hiring_manager": None,
        "recruiter": None,
        "linkedin_url": None,
    }

    # Build a Google search URL for public LinkedIn recruiter profiles
    company_encoded = company.replace(" ", "+")
    search_query = f"site:linkedin.com/in+recruiter+{company_encoded}"
    google_url = f"https://www.google.com/search?q={search_query}"

    try:
        resp = requests.get(
            google_url,
            timeout=REQUEST_TIMEOUT,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/120.0.0.0 Safari/537.36",
            },
        )
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")

            # Extract LinkedIn profile URLs from search results
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if "linkedin.com/in/" in href:
                    # Extract the actual LinkedIn URL
                    match = re.search(r"(https?://[a-z]+\.linkedin\.com/in/[^&?\"' ]+)", href)
                    if match:
                        result["linkedin_url"] = match.group(1)
                        # Try to get name from link text
                        link_text = link.get_text(strip=True)
                        if link_text and not link_text.startswith("http"):
                            # Check if it looks like a name
                            name_parts = link_text.split(" - ")[0].strip()
                            if len(name_parts.split()) >= 2:
                                result["recruiter"] = name_parts
                        break

    except requests.RequestException:
        pass  # Google search failed, not critical

    return result


def write_contact_json(company: str, contact: ContactInfo) -> str:
    """Persist contact info to database/history/{company}/contact.json."""
    safe_company = re.sub(r"[^A-Za-z0-9_-]", "_", company)
    path = os.path.join(CONTACTS_DIR, safe_company, "contact.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(contact, f, indent=2)
    return path


def run_recruiter_agent(state: CareerAgentState) -> dict:
    """LangGraph node. Looks up a contact for each qualified match's company.
    Failures are logged but don't block the pipeline — a missing contact
    is fine, the user can always search manually."""
    matches = state.get("qualified_matches", [])
    contacts = {}
    errors = []

    for match in matches:
        company = match["company"]
        try:
            careers_info = search_company_careers_page(company)
            linkedin_info = search_public_linkedin(company)

            contact: ContactInfo = {
                "company": company,
                "hiring_manager": linkedin_info.get("hiring_manager"),
                "recruiter": (
                    linkedin_info.get("recruiter")
                    or careers_info.get("recruiter")
                ),
                "email": careers_info.get("email"),
                "linkedin_url": linkedin_info.get("linkedin_url"),
                "source": "careers_page+google_public_search",
            }

            write_contact_json(company, contact)
            contacts[company] = contact
            print(f"  [recruiter] {company}: email={contact.get('email')}, recruiter={contact.get('recruiter')}")

        except Exception as e:
            errors.append(f"recruiter_agent[{company}]: {e}")

    return {"contacts": contacts, "errors": errors}
