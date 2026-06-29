"""SMTP-based email delivery helpers for Driftwatch reports."""

import os
import smtplib
from email.message import EmailMessage

from dotenv import load_dotenv

load_dotenv()


def _get_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def get_smtp_settings() -> dict:
    host = os.getenv("SMTP_SERVER", os.getenv("SMTP_HOST", "")).strip()
    port = os.getenv("SMTP_PORT", "587")
    username = os.getenv("GMAIL_SENDER_EMAIL", os.getenv("SMTP_USERNAME", os.getenv("SMTP_FROM", ""))).strip()
    password = os.getenv("GMAIL_SENDER_PASSWORD", os.getenv("SMTP_PASSWORD", "")).strip()
    from_addr = os.getenv("GMAIL_SENDER_EMAIL", os.getenv("SMTP_FROM", username)).strip()

    return {
        "host": host,
        "port": int(port),
        "username": username,
        "password": password,
        "from_addr": from_addr,
        "use_tls": _get_bool(os.getenv("SMTP_USE_TLS"), default=True),
    }


def build_report_email(recipient: str, topic: str, report_paths: list[str] | None = None, report_text: str | None = None) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = f"Driftwatch report: {topic}"
    message["To"] = recipient
    message["From"] = get_smtp_settings()["from_addr"] or "driftwatch@localhost"

    lines = [
        f"Driftwatch generated a new report for topic '{topic}'.",
        "",
    ]
    if report_text:
        lines.append(report_text)
        lines.append("")

    if report_paths:
        lines.append("Generated files:")
        for path in report_paths:
            lines.append(f"- {path}")
        lines.append("")

    lines.append("This email was sent automatically by Driftwatch.")
    message.set_content("\n".join(lines))
    return message


def send_report_email(recipient: str, topic: str, report_paths: list[str] | None = None, report_text: str | None = None) -> None:
    if not recipient:
        raise ValueError("A recipient email is required.")

    settings = get_smtp_settings()
    if not settings["host"]:
        raise RuntimeError("SMTP_HOST is not configured.")

    message = build_report_email(recipient, topic, report_paths, report_text)

    if settings["port"] == 465:
        with smtplib.SMTP_SSL(settings["host"], settings["port"]) as smtp:
            if settings["username"] and settings["password"]:
                smtp.login(settings["username"], settings["password"])
            smtp.send_message(message)
        return

    with smtplib.SMTP(settings["host"], settings["port"]) as smtp:
        if settings["use_tls"]:
            smtp.starttls()
        if settings["username"] and settings["password"]:
            smtp.login(settings["username"], settings["password"])
        smtp.send_message(message)
