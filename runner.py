# Entry point / orchestration

"""
runner.py - Entry point for Scheduled Prompt Runner.

Workflow:
1. Load environment variables from .env
2. Read prompts/prompt_current.txt
3. Call Claude via llm_client
4. Save response as output/output_<date>.md
5. If response starts with the NO_UPDATE sentinel, skip email
6. Otherwise email the response via emailer

This module contains orchestration only. No prompt logic, no API details,
no email details - those live in llm_client.py and emailer.py.

Phase 1 scope: single hardcoded prompt file. Phase 2 will add a CLI
argument for prompt file selection - not implemented here on purpose.
"""

import sys
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

from llm_client import get_claude_response
from emailer import send_email

BASE_DIR = Path(__file__).resolve().parent
PROMPT_FILE = BASE_DIR / "prompts" / "prompt_current.txt"
OUTPUT_DIR = BASE_DIR / "output"
LOG_FILE = BASE_DIR / "runner.log"

# Cap log file at 1 MB, keep 3 rotated backups (runner.log.1, .2, .3).
# Adjust MAX_LOG_BYTES later if real runs turn out more/less verbose.
MAX_LOG_BYTES = 1_000_000
LOG_BACKUP_COUNT = 3

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        RotatingFileHandler(
            LOG_FILE, maxBytes=MAX_LOG_BYTES, backupCount=LOG_BACKUP_COUNT, encoding="utf-8"
        ),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

# If a prompt's response starts with this exact string, the run is logged
# and saved but no email is sent. Prompts opt into this by instructing
# Claude to output the sentinel when there's nothing worth reporting.
# This keeps the "nothing changed" logic in the prompt (data), not here (code).
NO_UPDATE_SENTINEL = "NO_UPDATE"


def load_prompt() -> str:
    if not PROMPT_FILE.exists():
        raise FileNotFoundError(f"Prompt file not found: {PROMPT_FILE}")
    text = PROMPT_FILE.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"Prompt file is empty: {PROMPT_FILE}")
    return text


def save_output(response_text: str) -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    output_path = OUTPUT_DIR / f"output_{today}.md"
    output_path.write_text(response_text, encoding="utf-8")
    return output_path


def is_no_update(response_text: str) -> bool:
    return response_text.strip().startswith(NO_UPDATE_SENTINEL)


def main() -> int:
    load_dotenv(BASE_DIR / ".env")

    try:
        log.info("Starting scheduled prompt run.")
        prompt_text = load_prompt()
        log.info("Loaded prompt (%d characters).", len(prompt_text))

        response_text = get_claude_response(prompt_text)
        log.info("Received response from Claude (%d characters).", len(response_text))

        output_path = save_output(response_text)
        log.info("Saved output to %s", output_path)

        if is_no_update(response_text):
            log.info("Response indicates no update. Skipping email.")
            return 0

        subject = f"Scheduled Prompt Result - {datetime.now().strftime('%Y-%m-%d')}"
        send_email(subject=subject, body=response_text, attachment_path=output_path)
        log.info("Email sent successfully. Run complete.")
        return 0

    except Exception as exc:
        log.exception("Run failed: %s", exc)
        # Best-effort failure notification so a broken run doesn't fail silently.
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