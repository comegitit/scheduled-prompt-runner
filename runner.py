"""
runner.py - Entry point for Scheduled Prompt Runner.

Usage:
    python runner.py <task> <variant>

Examples:
    python runner.py daily news
    python runner.py weekly inbox
    python runner.py monthly deprecation
    python runner.py monthly governance

Each (task, variant) pair maps to prompts/prompt_<task>_<variant>.txt.
A single scheduled task can chain multiple variants by invoking this
script multiple times (see run_prompt.bat and run_monthly_tasks.bat) -
each invocation is a fully independent, stateless run. runner.py itself
has no knowledge of chaining; that lives entirely at the .bat/Task
Scheduler level.

Workflow:
1. Load environment variables from .env
2. Read prompts/prompt_<task>_<variant>.txt
3. For task "weekly": fetch Inbox emails since last Sunday via
   imap_client and append them to the prompt before sending.
4. For web-search-enabled variants: call Claude with web search enabled,
   restricted to a per-variant domain allowlist.
5. Save response as output/output_<task>_<variant>_<date>.md
6. If response starts with the NO_UPDATE sentinel, skip email
7. Otherwise email the response via emailer

This module contains orchestration only. API details live in llm_client.py,
email-sending details live in emailer.py, IMAP details live in
imap_client.py.
"""

import os
import sys
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

from llm_client import get_claude_response
from emailer import send_email
from imap_client import fetch_weekly_emails

BASE_DIR = Path(__file__).resolve().parent
PROMPTS_DIR = BASE_DIR / "prompts"
OUTPUT_DIR = BASE_DIR / "output"
LOG_FILE = BASE_DIR / "runner.log"

VALID_TASKS = ("daily", "weekly", "monthly")

# Rotate logs daily, keep 122 days of history (~4 months).
LOG_RETENTION_DAYS = 122

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        TimedRotatingFileHandler(
            LOG_FILE,
            when="D",
            interval=1,
            backupCount=LOG_RETENTION_DAYS,
            encoding="utf-8",
        ),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

# If a prompt's response starts with this exact string, the run is logged
# and saved but no email is sent. Keeps "nothing changed" logic in the
# prompt (data), not here (code).
NO_UPDATE_SENTINEL = "NO_UPDATE"

# Per-variant web search configuration. Variants not listed here get no
# web search (e.g. "inbox", which uses IMAP-injected data instead).
# Restricted to small, trusted domain lists - accuracy from a few
# first-party sources over breadth from open search.
WEB_SEARCH_CONFIG = {
    "news": ["anthropic.com", "openai.com"],
    "markets": ["nasdaqtrader.com", "tsx.com", "ir.thomsonreuters.com"],
    "deprecation": ["docs.claude.com"],
    "governance": ["canada.ca", "alberta.ca", "cigionline.org", "betakit.com"],
}

# Per-variant IMAP account config for variants that need inbox content.
# Each entry names the .env variables holding that account's connection
# details - runner.py reads them and passes explicit values into
# imap_client, which has no knowledge of .env or which account it's
# talking to.
IMAP_ACCOUNT_CONFIG = {
    "inbox": {
        "host_env": "IMAP_SERVER",
        "port_env": "IMAP_PORT",
        "email_env": "IMAP_EMAIL",
        "password_env": "IMAP_PASSWORD",
    },
    "gmail": {
        "host_env": "GMAIL_IMAP_SERVER",
        "port_env": "GMAIL_IMAP_PORT",
        "email_env": "GMAIL_IMAP_EMAIL",
        "password_env": "GMAIL_IMAP_PASSWORD",
    },
}

# Human-readable, title-cased labels for email subjects, keyed by
# (task, variant). Falls back to a generic "<Task>/<Variant>" label for
# any pair not listed here, so a new variant never breaks email sending
# even if this table isn't updated immediately.
SUBJECT_LABELS = {
    ("daily", "news"): "Daily/LLM Vendor News",
    ("daily", "markets"): "Daily/Financial Markets",
    ("weekly", "inbox"): "Weekly/AI-YYC Inbox",
    ("weekly", "gmail"): "Weekly/Gmail Inbox",
    ("monthly", "deprecation"): "Monthly/Anthropic Model Deprecation",
    ("monthly", "governance"): "Monthly/Canada & Alberta Governance News",
}


def get_subject_label(task: str, variant: str) -> str:
    return SUBJECT_LABELS.get((task, variant), f"{task.title()}/{variant.title()}")


def parse_args() -> tuple[str, str]:
    if len(sys.argv) != 3 or sys.argv[1] not in VALID_TASKS:
        raise ValueError(
            f"Usage: python runner.py <task> <variant>, "
            f"where <task> is one of {VALID_TASKS}"
        )
    return sys.argv[1], sys.argv[2]


def load_prompt(task: str, variant: str) -> str:
    prompt_file = PROMPTS_DIR / f"prompt_{task}_{variant}.txt"
    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_file}")
    text = prompt_file.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"Prompt file is empty: {prompt_file}")
    return text


def build_prompt(variant: str, base_prompt: str) -> str:
    """
    Combine the static prompt with any variant-specific injected data.
    IMAP-backed variants (see IMAP_ACCOUNT_CONFIG) get live inbox content
    appended; other variants are sent as-is (web search, if configured,
    is applied separately in main()).
    """
    imap_config = IMAP_ACCOUNT_CONFIG.get(variant)
    if imap_config:
        host = os.getenv(imap_config["host_env"])
        port = int(os.getenv(imap_config["port_env"], "993"))
        username = os.getenv(imap_config["email_env"])
        password = os.getenv(imap_config["password_env"])

        log.info("Fetching inbox emails since last Sunday for %s account.", variant)
        emails_text = fetch_weekly_emails(host, port, username, password)
        log.info("Fetched email content (%d characters).", len(emails_text))
        return f"{base_prompt}\n\n---\n\nEmails:\n\n{emails_text}"
    return base_prompt


def save_output(task: str, variant: str, response_text: str) -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    output_path = OUTPUT_DIR / f"output_{task}_{variant}_{today}.md"
    output_path.write_text(response_text, encoding="utf-8")
    return output_path


def is_no_update(response_text: str) -> bool:
    return response_text.strip().startswith(NO_UPDATE_SENTINEL)


def main() -> int:
    load_dotenv(BASE_DIR / ".env")

    try:
        task, variant = parse_args()
        log.info("Starting scheduled prompt run: task=%s variant=%s", task, variant)

        base_prompt = load_prompt(task, variant)
        log.info(
            "Loaded prompt_%s_%s.txt (%d characters).", task, variant, len(base_prompt)
        )

        full_prompt = build_prompt(variant, base_prompt)

        allowed_domains = WEB_SEARCH_CONFIG.get(variant)
        use_web_search = allowed_domains is not None
        response_text = get_claude_response(
            full_prompt,
            enable_web_search=use_web_search,
            allowed_domains=allowed_domains,
        )
        log.info("Received response from Claude (%d characters).", len(response_text))

        output_path = save_output(task, variant, response_text)
        log.info("Saved output to %s", output_path)

        if is_no_update(response_text):
            log.info("Response indicates no update. Skipping email.")
            return 0

        subject = (
            f"Scheduled Prompt Result ({get_subject_label(task, variant)}) - "
            f"{datetime.now().strftime('%Y-%m-%d')}"
        )
        send_email(subject=subject, body=response_text, attachment_path=output_path)
        log.info("Email sent successfully. Run complete.")
        return 0

    except Exception as exc:
        log.exception("Run failed: %s", exc)
        try:
            send_email(
                subject="Scheduled Prompt Runner FAILED",
                body=(
                    f"The scheduled run failed with an error:\n\n{exc}\n\n"
                    f"Check {LOG_FILE} on the machine for full details."
                ),
                attachment_path=None,
            )
        except Exception:
            log.exception("Failed to send failure notification email.")
        return 1


if __name__ == "__main__":
    sys.exit(main())