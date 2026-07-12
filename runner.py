"""
runner.py - Entry point for Scheduled Prompt Runner.

Usage:
    python runner.py daily
    python runner.py weekly
    python runner.py monthly

Workflow:
1. Load environment variables from .env
2. Read prompts/prompt_<task>.txt
3. For "weekly": fetch Inbox emails since last Sunday via imap_client and
   append them to the prompt before sending. Other tasks send the prompt
   file as-is (web-tool wiring for daily/monthly comes in a later change).
4. Call Claude via llm_client
5. Save response as output/output_<task>_<date>.md
6. If response starts with the NO_UPDATE sentinel, skip email
7. Otherwise email the response via emailer

This module contains orchestration only. API details live in llm_client.py,
email-sending details live in emailer.py, IMAP details live in
imap_client.py.
"""

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


def parse_task_arg() -> str:
    if len(sys.argv) != 2 or sys.argv[1] not in VALID_TASKS:
        raise ValueError(
            f"Usage: python runner.py <task>, where <task> is one of {VALID_TASKS}"
        )
    return sys.argv[1]


def load_prompt(task: str) -> str:
    prompt_file = PROMPTS_DIR / f"prompt_{task}.txt"
    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_file}")
    text = prompt_file.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"Prompt file is empty: {prompt_file}")
    return text


def build_prompt(task: str, base_prompt: str) -> str:
    """
    Combine the static prompt with any task-specific injected data.
    Weekly needs live inbox content; daily/monthly are sent as-is for now.
    """
    if task == "weekly":
        log.info("Fetching inbox emails since last Sunday for weekly task.")
        emails_text = fetch_weekly_emails()
        log.info("Fetched email content (%d characters).", len(emails_text))
        return f"{base_prompt}\n\n---\n\nEmails:\n\n{emails_text}"
    return base_prompt


def save_output(task: str, response_text: str) -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    output_path = OUTPUT_DIR / f"output_{task}_{today}.md"
    output_path.write_text(response_text, encoding="utf-8")
    return output_path


def is_no_update(response_text: str) -> bool:
    return response_text.strip().startswith(NO_UPDATE_SENTINEL)


def main() -> int:
    load_dotenv(BASE_DIR / ".env")

    try:
        task = parse_task_arg()
        log.info("Starting scheduled prompt run: task=%s", task)

        base_prompt = load_prompt(task)
        log.info("Loaded prompt_%s.txt (%d characters).", task, len(base_prompt))

        full_prompt = build_prompt(task, base_prompt)

        # Daily and monthly need live web data; weekly already has live
        # data injected from the inbox and doesn't need it. Restricted to
        # a small set of authoritative domains rather than open web
        # search - accuracy from fewer sources over breadth from many.
        DOMAIN_ALLOWLIST = {
            "daily": ["anthropic.com", "openai.com"],
            "monthly": ["docs.claude.com"],
        }
        use_web_search = task in ("daily", "monthly")
        response_text = get_claude_response(
            full_prompt,
            enable_web_search=use_web_search,
            allowed_domains=DOMAIN_ALLOWLIST.get(task),
        )
        log.info("Received response from Claude (%d characters).", len(response_text))

        output_path = save_output(task, response_text)
        log.info("Saved output to %s", output_path)

        if is_no_update(response_text):
            log.info("Response indicates no update. Skipping email.")
            return 0

        subject = f"Scheduled Prompt Result ({task}) - {datetime.now().strftime('%Y-%m-%d')}"
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