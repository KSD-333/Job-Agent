"""
Agent 1 — Resume Knowledge Agent

Runs only when the master resume changes (cache is keyed off the source
PDF's mtime). Extracts raw text, structures it into a fixed JSON schema via
an LLM call, then chunks + embeds that JSON into a local FAISS index so
downstream agents can retrieve relevant slices via RAG instead of stuffing
the whole resume into every prompt.

Pipeline:
    resume.pdf -> extract text -> LLM structuring -> resume.json
    resume.json -> chunk -> embed (BAAI/bge-small-en-v1.5) -> FAISS index
"""

import json
import os

import pdfplumber
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from graph_flow.state import CareerAgentState
from utils.config import EMBEDDING_MODEL
from utils.llm_json import call_groq_json

RESUME_JSON_PATH = "resumes/resume.json"
GENERATED_DIR = "resumes/generated"
FAISS_INDEX_PATH = os.path.join(GENERATED_DIR, "resume.index")
CHUNKS_PATH = os.path.join(GENERATED_DIR, "resume_chunks.json")
CACHE_MARKER_PATH = os.path.join(GENERATED_DIR, ".last_processed_mtime")
PROMPT_TEMPLATE_PATH = "prompts/resume_structuring.md"

RESUME_SCHEMA = {
    "personal_info": {
        "name": "", "email": "", "phone": "", "location": "",
        "linkedin": "", "github": "",
    },
    "skills": ["string"],
    "experience": [{
        "company": "", "title": "", "start_date": "", "end_date": "",
        "bullets": ["string"],
    }],
    "projects": [{
        "name": "", "description": "", "skills": ["string"], "bullets": ["string"],
    }],
    "education": [{
        "institution": "", "degree": "", "start_date": "", "end_date": "",
    }],
    "achievements": ["string"],
    "keywords": ["string"],
}

_embedding_model = None  # lazy-loaded singleton, model load is expensive


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract raw text from every page of the resume PDF, in order."""
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Resume PDF not found at {pdf_path}")

    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            pages.append(text)

    full_text = "\n".join(pages).strip()
    if not full_text:
        raise ValueError(
            f"No extractable text found in {pdf_path}. "
            "If this is a scanned/image resume, OCR it first."
        )
    return full_text


def structure_resume(raw_text: str) -> dict:
    """Call the LLM to turn raw resume text into the fixed schema above."""
    with open(PROMPT_TEMPLATE_PATH, "r") as f:
        template = f.read()

    prompt = template.replace(
        "{schema}", json.dumps(RESUME_SCHEMA, indent=2)
    ).replace(
        "{resume_text}", raw_text
    )

    return call_groq_json(prompt)


def _get_embedding_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    return _embedding_model


def chunk_resume(resume_json: dict) -> list:
    """Turn structured resume JSON into retrieval-sized text chunks, each
    tagged with the section it came from so downstream agents can filter
    (e.g. matcher only needs skills+experience, cover letter wants projects)."""
    chunks = []

    skills = resume_json.get("skills", [])
    if skills:
        chunks.append({
            "section": "skills",
            "text": "Skills: " + ", ".join(skills),
            "metadata": {"skills": skills},
        })

    for exp in resume_json.get("experience", []):
        bullets = exp.get("bullets", [])
        text = (
            f"{exp.get('title', '')} at {exp.get('company', '')} "
            f"({exp.get('start_date', '')} - {exp.get('end_date', '')}). "
            + " ".join(bullets)
        ).strip()
        if text:
            chunks.append({
                "section": "experience",
                "text": text,
                "metadata": {"company": exp.get("company", ""), "title": exp.get("title", "")},
            })

    for proj in resume_json.get("projects", []):
        text = (
            f"Project: {proj.get('name', '')}. {proj.get('description', '')} "
            + " ".join(proj.get("bullets", []))
        ).strip()
        if text:
            chunks.append({
                "section": "projects",
                "text": text,
                "metadata": {"name": proj.get("name", ""), "skills": proj.get("skills", [])},
            })

    for edu in resume_json.get("education", []):
        text = (
            f"{edu.get('degree', '')}, {edu.get('institution', '')} "
            f"({edu.get('start_date', '')} - {edu.get('end_date', '')})"
        ).strip()
        if text:
            chunks.append({"section": "education", "text": text, "metadata": {}})

    achievements = resume_json.get("achievements", [])
    if achievements:
        chunks.append({
            "section": "achievements",
            "text": "Achievements: " + "; ".join(achievements),
            "metadata": {},
        })

    return chunks


def build_or_load_index(resume_json: dict):
    """Chunk resume_json, embed with EMBEDDING_MODEL, build a FAISS index,
    and persist both the index and the chunk metadata to disk. Returns the
    faiss index handle."""
    os.makedirs(GENERATED_DIR, exist_ok=True)

    chunks = chunk_resume(resume_json)
    if not chunks:
        raise ValueError("No content to embed — resume_json has no populated sections.")

    model = _get_embedding_model()
    texts = [c["text"] for c in chunks]
    embeddings = model.encode(texts, normalize_embeddings=True)
    embeddings = np.asarray(embeddings, dtype="float32")

    index = faiss.IndexFlatIP(embeddings.shape[1])  # cosine sim via normalized inner product
    index.add(embeddings)

    faiss.write_index(index, FAISS_INDEX_PATH)
    with open(CHUNKS_PATH, "w") as f:
        json.dump(chunks, f, indent=2)

    return index


def retrieve_relevant_chunks(query: str, top_k: int = 5, section: str = None) -> list:
    """Semantic search over the resume index. Used by the Match, Tailor, and
    Cover Letter agents instead of re-reading the whole resume each time.
    Optionally filter to a single section (e.g. section='experience')."""
    if not (os.path.exists(FAISS_INDEX_PATH) and os.path.exists(CHUNKS_PATH)):
        raise FileNotFoundError(
            "No resume index found. Run the resume agent at least once first."
        )

    index = faiss.read_index(FAISS_INDEX_PATH)
    with open(CHUNKS_PATH, "r") as f:
        chunks = json.load(f)

    model = _get_embedding_model()
    query_vec = np.asarray(model.encode([query], normalize_embeddings=True), dtype="float32")

    k = min(top_k * 3 if section else top_k, len(chunks))  # over-fetch if filtering
    scores, indices = index.search(query_vec, k)

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx == -1:
            continue
        chunk = chunks[idx]
        if section and chunk["section"] != section:
            continue
        results.append({**chunk, "score": float(score)})
        if len(results) >= top_k:
            break

    return results


def _source_mtime(path: str) -> float:
    return os.path.getmtime(path) if os.path.exists(path) else -1.0


def run_resume_agent(state: CareerAgentState) -> dict:
    """LangGraph node. Skips re-processing (LLM call + re-embedding) if the
    source PDF hasn't changed since the last successful run."""
    resume_path = state.get("resume_path", "resumes/master_resume.pdf")

    current_mtime = _source_mtime(resume_path)
    cached_mtime = None
    if os.path.exists(CACHE_MARKER_PATH):
        with open(CACHE_MARKER_PATH, "r") as f:
            try:
                cached_mtime = float(f.read().strip())
            except ValueError:
                cached_mtime = None

    already_cached = (
        cached_mtime is not None
        and current_mtime == cached_mtime
        and os.path.exists(RESUME_JSON_PATH)
        and os.path.exists(FAISS_INDEX_PATH)
    )

    if already_cached:
        with open(RESUME_JSON_PATH, "r") as f:
            resume_json = json.load(f)
        return {"resume_json": resume_json, "resume_embeddings_ready": True}

    try:
        raw_text = extract_text_from_pdf(resume_path)
        resume_json = structure_resume(raw_text)

        os.makedirs(os.path.dirname(RESUME_JSON_PATH), exist_ok=True)
        with open(RESUME_JSON_PATH, "w") as f:
            json.dump(resume_json, f, indent=2)

        build_or_load_index(resume_json)

        os.makedirs(GENERATED_DIR, exist_ok=True)
        with open(CACHE_MARKER_PATH, "w") as f:
            f.write(str(current_mtime))

        return {"resume_json": resume_json, "resume_embeddings_ready": True}

    except (FileNotFoundError, ValueError, RuntimeError) as e:
        return {
            "resume_json": {},
            "resume_embeddings_ready": False,
            "errors": [f"resume_agent: {e}"],
        }
