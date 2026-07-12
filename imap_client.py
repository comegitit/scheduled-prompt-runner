"""
imap_client.py - Thin wrapper around IMAP email fetching.

Responsibility: connect to the mailbox, fetch messages received since a
given date from the Inbox, and return them as a single formatted text
blob (sender / date / subject / body) for inclusion in a prompt. No
prompt logic, no orchestration, no email-sending logic (that's emailer.py).
"""

import os
import imaplib
import email
from email.header import decode_header
from datetime import datetime, timedelta

# Cap each email body so one long email can't blow up the combined prompt.
MAX_BODY_CHARS = 2000


def _decode(value) -> str:
    if not value:
        return ""
    parts = decode_header(value)
    result = []
    for part, encoding in parts:
        if isinstance(part, bytes):
            result.append(part.decode(encoding or "utf-8", errors="replace"))
        else:
            result.append(part)
    return "".join(result)


def _get_body(msg) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition") or "")
            if content_type == "text/plain" and "attachment" not in disposition:
                charset = part.get_content_charset() or "utf-8"
                payload = part.get_payload(decode=True)
                if payload is None:
                    continue
                try:
                    return payload.decode(charset, errors="replace")
                except Exception:
                    continue
        return ""
    else:
        charset = msg.get_content_charset() or "utf-8"
        payload = msg.get_payload(decode=True)
        if payload is None:
            return ""
        try:
            return payload.decode(charset, errors="replace")
        except Exception:
            return ""


def get_last_sunday() -> datetime:
    """Most recent Sunday at 00:00 (today, if today is Sunday)."""
    today = datetime.now()
    days_since_sunday = (today.weekday() + 1) % 7  # Monday=0 ... Sunday=6
    last_sunday = today - timedelta(days=days_since_sunday)
    return last_sunday.replace(hour=0, minute=0, second=0, microsecond=0)


def fetch_weekly_emails() -> str:
    """
    Fetch all Inbox emails received since last Sunday. No sender/subject
    filtering - returns everything. Returns a formatted text blob ready
    to append to a prompt, or a plain "no emails" message if the inbox
    is empty for that window.
    """
    host = os.getenv("IMAP_SERVER")
    port = int(os.getenv("IMAP_PORT", "993"))
    username = os.getenv("IMAP_EMAIL")
    password = os.getenv("IMAP_PASSWORD")

    missing = [
        name
        for name, val in [
            ("IMAP_SERVER", host),
            ("IMAP_EMAIL", username),
            ("IMAP_PASSWORD", password),
        ]
        if not val
    ]
    if missing:
        raise RuntimeError(f"Missing required IMAP settings in .env: {', '.join(missing)}")

    since_date = get_last_sunday()
    imap_date = since_date.strftime("%d-%b-%Y")  # IMAP SEARCH format, e.g. 06-Jul-2026

    mail = imaplib.IMAP4_SSL(host, port)
    try:
        mail.login(username, password)
        mail.select("INBOX")

        status, data = mail.search(None, f'(SINCE "{imap_date}")')
        if status != "OK":
            raise RuntimeError(f"IMAP search failed with status: {status}")

        message_ids = data[0].split()
        if not message_ids:
            return "No emails received since last Sunday."

        formatted = []
        for msg_id in message_ids:
            status, msg_data = mail.fetch(msg_id, "(RFC822)")
            if status != "OK":
                continue

            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            subject = _decode(msg.get("Subject"))
            sender = _decode(msg.get("From"))
            date_str = msg.get("Date", "")
            body = _get_body(msg).strip()

            if len(body) > MAX_BODY_CHARS:
                body = body[:MAX_BODY_CHARS] + "... [truncated]"

            formatted.append(
                f"From: {sender}\nDate: {date_str}\nSubject: {subject}\n\n{body}\n{'-' * 40}"
            )

        return "\n\n".join(formatted)

    finally:
        try:
            mail.close()
        except Exception:
            pass
        mail.logout()