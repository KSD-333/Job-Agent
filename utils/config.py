"""
Central config loader. All secrets come from environment variables
(populate a local .env — see .env.example — never commit real credentials).
"""

import os
from dotenv import load_dotenv

load_dotenv()

# LLM
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Embeddings
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")

# Gmail SMTP
GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Postgres (optional — CSVs are the default source of truth for the MVP)
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Pipeline behavior
MATCH_THRESHOLD = float(os.getenv("MATCH_THRESHOLD", "70"))
ENABLE_LINKEDIN_SCRAPING = os.getenv("ENABLE_LINKEDIN_SCRAPING", "false").lower() == "true"
ENABLE_NAUKRI_SCRAPING = os.getenv("ENABLE_NAUKRI_SCRAPING", "false").lower() == "true"
ENABLE_WELLFOUND_SCRAPING = os.getenv("ENABLE_WELLFOUND_SCRAPING", "false").lower() == "true"
