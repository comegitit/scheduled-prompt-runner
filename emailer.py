# SMTP email wrapper

"""
emailer.py - Sends the generated output via email (SMTP).

Responsible for connecting to the SMTP server, sending the email, and
optionally attaching the output file. No prompt logic lives here.
"""

import os
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Optional


def send_email(subject: str, body: str, attachment_path: Optional[Path] = None) -> None:
    host = os.getenv("EMAIL_HOST")
    port = int(os.getenv("EMAIL_PORT", "587"))
    username = os.getenv("EMAIL_USERNAME")
    password = os.getenv("EMAIL_PASSWORD")
    to_addr = os.getenv("EMAIL_TO")

    missing = [
        name
        for name, val in [
            ("EMAIL_HOST", host),
            ("EMAIL_USERNAME", username),
            ("EMAIL_PASSWORD", password),
            ("EMAIL_TO", to_addr),
        ]
        if not val
    ]
    if missing:
        raise RuntimeError(f"Missing required email settings in .env: {', '.join(missing)}")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = username
    msg["To"] = to_addr
    msg.set_content(body)

    if attachment_path is not None:
        attachment_path = Path(attachment_path)
        if attachment_path.exists():
            msg.add_attachment(
                attachment_path.read_bytes(),
                maintype="text",
                subtype="markdown",
                filename=attachment_path.name,
            )

    with smtplib.SMTP(host, port, timeout=30) as server:
        server.starttls()
        server.login(username, password)
        server.send_message(msg)