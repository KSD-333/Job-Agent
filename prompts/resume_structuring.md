# Resume Structuring Prompt (Agent 1)

Used by `agents/resume_agent.py::structure_resume()`.

You are extracting structured data from a resume. Return ONLY valid JSON
matching this schema, with no commentary, no markdown fences:

{schema}

Rules:
- Do not invent, infer, or embellish any information not present in the source text.
- Preserve dates, titles, and company names exactly as written.
- Split each experience bullet into its own array entry.

Resume text:
{resume_text}
