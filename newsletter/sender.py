"""Send the rendered HTML newsletter (SMTP) or write it to disk (dry run)."""

from __future__ import annotations

import logging
import smtplib
from datetime import date, datetime
from email.message import EmailMessage
from pathlib import Path

from .config import OUT_DIR, Settings

log = logging.getLogger(__name__)


def write_to_disk(subject: str, html: str, today: date | None = None) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    today = today or datetime.now().date()
    path = OUT_DIR / f"newsletter-{today.isoformat()}.html"
    path.write_text(html, encoding="utf-8")
    log.info("Dry run: wrote %s (subject: %s)", path, subject)
    return path


def send_email(subject: str, html: str, settings: Settings) -> None:
    missing = [
        k for k in ("smtp_username", "smtp_password", "email_from", "email_to")
        if not getattr(settings, k)
    ]
    if missing:
        raise RuntimeError(
            f"Cannot send email; missing settings: {', '.join(missing)}. "
            "Either fill them in .env or use --dry-run."
        )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.email_from
    msg["To"] = settings.email_to
    msg.set_content(
        "This newsletter is best viewed in HTML. "
        "If you see this text, your client did not render the HTML part."
    )
    msg.add_alternative(html, subtype="html")

    log.info(
        "SMTP send: %s:%d as %s -> %s",
        settings.smtp_host, settings.smtp_port,
        settings.smtp_username, settings.email_to,
    )
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.starttls()
        server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(msg)
    log.info("SMTP send: done.")
