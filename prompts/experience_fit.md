# Experience Fit Prompt (Agent 3)

Used by `agents/matcher_agent.py::experience_fit_score()`.

Judge how well this candidate's experience level and domain fit the job
below. Consider years of experience, seniority language ("senior", "lead",
"intern"), and domain overlap (e.g. mobile vs backend vs data). Do not
consider skills overlap — that is scored separately.

Return ONLY valid JSON, no commentary, no markdown fences:
{"score": <integer 0-100>, "reasoning": "<one sentence>"}

Candidate experience:
{experience_summary}

Job:
Title: {job_title}
Company: {company}
Description: {job_description}
