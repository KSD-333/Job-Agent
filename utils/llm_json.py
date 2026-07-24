"""
Shared helper for agents that need structured JSON back from Groq.
Used by resume_agent, matcher_agent, tailor_agent, cover_letter_agent, and
interview_agent so the "call LLM, parse strict JSON, retry once on
malformed output" logic lives in exactly one place.
"""

import json
import re

from groq import Groq

from utils.config import GROQ_API_KEY, GROQ_MODEL


def strip_json_fences(text: str) -> str:
    """Strip ```json ... ``` fences some models wrap responses in."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def extract_first_json_object(text: str) -> str:
    """Pull out the first balanced {...} block if the model added any
    stray commentary around the JSON."""
    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON object found in LLM response.")
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    raise ValueError("Unbalanced JSON braces in LLM response.")


def call_groq_json(prompt: str, model: str = None, temperature: float = 0, max_retries: int = 1) -> dict:
    """Call Groq with a prompt that asks for JSON-only output, and return
    the parsed dict. Retries with a corrective follow-up if the model
    returns something that isn't valid JSON (or wraps it in commentary /
    markdown fences)."""
    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Add it to your .env file "
            "(see .env.example) before calling the LLM."
        )

    client = Groq(api_key=GROQ_API_KEY)
    messages = [{"role": "user", "content": prompt}]

    last_error = None
    for attempt in range(max_retries + 1):
        response = client.chat.completions.create(
            model=model or GROQ_MODEL,
            messages=messages,
            temperature=temperature,
        )
        content = response.choices[0].message.content

        for candidate in (content, strip_json_fences(content)):
            try:
                return json.loads(candidate)
            except (json.JSONDecodeError, TypeError):
                pass

        try:
            return json.loads(extract_first_json_object(strip_json_fences(content)))
        except (json.JSONDecodeError, ValueError) as e:
            last_error = e
            if attempt < max_retries:
                messages.append({"role": "assistant", "content": content})
                messages.append({
                    "role": "user",
                    "content": "That was not valid JSON. Reply with ONLY the JSON "
                                "object, no commentary, no markdown fences.",
                })

    raise ValueError(f"LLM did not return valid JSON after retries: {last_error}")
