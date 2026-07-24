"""
Agent 9 — Notification Agent

Sends a daily digest (Gmail SMTP) and/or Telegram message summarizing
today's qualified matches. Runs as the final node in the main graph.

Both channels gracefully skip if credentials aren't configured — the
pipeline never crashes because of missing notification config.
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date

import requests

from graph_flow.state import CareerAgentState
from utils.config import (
    GMAIL_USER,
    GMAIL_APP_PASSWORD,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
)


def format_digest(qualified_matches: list, analytics: dict = None, missing_skills: dict = None) -> str:
    """Format qualified matches into a readable daily digest."""
    lines = []
    today = date.today().strftime("%B %d, %Y")
    lines.append(f"🎯 AI Career Agent — Daily Report ({today})")
    lines.append("=" * 50)

    if not qualified_matches:
        lines.append("\nNo new qualified matches today.")
        return "\n".join(lines)

    lines.append(f"\n📋 {len(qualified_matches)} Qualified Job Matches:\n")

    for i, m in enumerate(
        sorted(qualified_matches, key=lambda m: m["score"], reverse=True), 1
    ):
        score = m["score"]
        # Score emoji
        if score >= 90:
            emoji = "🟢"
        elif score >= 80:
            emoji = "🟡"
        else:
            emoji = "🟠"

        lines.append(f"  {emoji} {i}. {m['company']} — {m['role']} — {score}%")

        if m.get("matched_skills"):
            skills_str = ", ".join(m["matched_skills"][:5])
            lines.append(f"     ✅ Matched: {skills_str}")

        if m.get("missing_skills"):
            missing_str = ", ".join(m["missing_skills"][:3])
            lines.append(f"     ❌ Missing: {missing_str}")

    # Analytics summary
    if analytics:
        lines.append(f"\n📊 Application Funnel:")
        lines.append(f"  Applied: {analytics.get('applied', 0)}")
        lines.append(f"  Interview: {analytics.get('interview', 0)}")
        lines.append(f"  Rejected: {analytics.get('rejected', 0)}")
        lines.append(f"  Offer: {analytics.get('offer', 0)}")

    # Missing skills
    if missing_skills:
        lines.append(f"\n📈 Top Missing Skills (learn these!):")
        for skill, count in list(missing_skills.items())[:5]:
            lines.append(f"  • {skill} (requested by {count} companies)")

    lines.append(f"\n{'=' * 50}")
    lines.append("Sent by AI Career Agent 🤖")

    return "\n".join(lines)


def format_telegram_digest(qualified_matches: list) -> str:
    """Format a shorter, Telegram-friendly version of the digest."""
    if not qualified_matches:
        return "🎯 No new qualified matches today."

    lines = [f"🎯 *{len(qualified_matches)} New Job Matches*\n"]

    for m in sorted(qualified_matches, key=lambda m: m["score"], reverse=True)[:10]:
        score = m["score"]
        emoji = "🟢" if score >= 90 else ("🟡" if score >= 80 else "🟠")
        lines.append(f"{emoji} *{m['company']}* — {m['role']} — {score}%")

    return "\n".join(lines)


def send_email(subject: str, body: str):
    """Send via Gmail SMTP using credentials from environment variables.
    Skips gracefully if credentials aren't set."""
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        raise ValueError(
            "Gmail credentials not configured. "
            "Set GMAIL_USER and GMAIL_APP_PASSWORD in .env"
        )

    msg = MIMEMultipart()
    msg["From"] = GMAIL_USER
    msg["To"] = GMAIL_USER  # send to self
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.send_message(msg)
            print(f"  [notification] Email sent to {GMAIL_USER}")
    except smtplib.SMTPAuthenticationError:
        raise ValueError(
            "Gmail authentication failed. Make sure you're using an App Password, "
            "not your regular Gmail password. Generate one at: "
            "https://myaccount.google.com/apppasswords"
        )


def send_telegram(message: str):
    """POST to Telegram Bot API sendMessage endpoint.
    Skips gracefully if credentials aren't set."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise ValueError(
            "Telegram credentials not configured. "
            "Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env"
        )

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
    }

    resp = requests.post(url, json=payload, timeout=10)
    if resp.status_code == 200:
        print(f"  [notification] Telegram message sent")
    else:
        error_info = resp.json().get("description", resp.text)
        raise ValueError(f"Telegram API error: {error_info}")


def run_notification_agent(state: CareerAgentState) -> dict:
    """LangGraph node. Sends the daily digest via configured channels.
    Failures here don't fail the whole pipeline — just get logged."""
    matches = state.get("qualified_matches", [])
    analytics = state.get("analytics", {})
    missing_skills = state.get("missing_skill_report", {})

    digest = format_digest(matches, analytics, missing_skills)
    telegram_digest = format_telegram_digest(matches)
    errors = []

    # Email
    try:
        send_email(
            subject=f"🎯 {len(matches)} new job matches — AI Career Agent",
            body=digest,
        )
    except ValueError as e:
        errors.append(f"notification_agent[email]: {e}")

    # Telegram
    try:
        send_telegram(telegram_digest)
    except ValueError as e:
        errors.append(f"notification_agent[telegram]: {e}")

    # Also save the digest to a local file as fallback
    try:
        os.makedirs("reports", exist_ok=True)
        digest_path = os.path.join("reports", "latest_digest.txt")
        with open(digest_path, "w", encoding="utf-8") as f:
            f.write(digest)
        print(f"  [notification] Digest saved to {digest_path}")
    except Exception as e:
        errors.append(f"notification_agent[file]: {e}")

    return {"notifications_sent": len(errors) < 2, "errors": errors}
