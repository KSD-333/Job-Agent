# Cover Letter Drafting Prompt (Agent 5)

Used by `agents/cover_letter_agent.py::draft_cover_letter_text()`.

Write a professional cover letter (300-350 words, NO greeting/sign-off — those are added separately) for the role below. Follow these rules strictly:

1. Ground every claim in the candidate's actual resume data provided — NEVER invent skills, projects, or experience.
2. Reference 1-2 specific matched skills/projects by name.
3. Explain WHY you're a good fit, connecting your experience to the role's requirements.
4. Keep tone confident, specific, and non-generic. Avoid clichés like "passionate about technology" or "team player".
5. Structure as 3 paragraphs: (1) why this role excites you + strongest qualification, (2) relevant experience/projects with specifics, (3) closing enthusiasm + what you bring.

Return ONLY valid JSON with no commentary, no markdown fences:
{"cover_letter": "<the full cover letter text, 3 paragraphs>"}

Candidate resume data:
{resume_json}

Job description:
{job_description}

Matched skills: {matched_skills}
