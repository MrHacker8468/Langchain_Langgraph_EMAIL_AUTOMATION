import os
import smtplib
from email.message import EmailMessage
from email.utils import parseaddr


SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587


def is_valid_email_address(address: str) -> bool:
    """Perform basic validation for a single email address."""
    address = address.strip()
    _, parsed = parseaddr(address)
    return (
        parsed == address
        and address.count("@") == 1
        and not any(character.isspace() for character in address)
        and "." in address.rsplit("@", 1)[-1]
    )


def send_email(recipient: str, subject: str, body: str) -> None:
    """Send one plain-text email via Gmail SMTP using local environment secrets."""
    sender = os.getenv("SMTP_SENDER_EMAIL", "").strip()
    app_password = os.getenv("SMTP_APP_PASSWORD", "").strip()

    if not sender or not app_password:
        raise ValueError(
            "Set SMTP_SENDER_EMAIL and SMTP_APP_PASSWORD in your local .env file."
        )
    if not is_valid_email_address(sender):
        raise ValueError("SMTP_SENDER_EMAIL must be a valid email address.")
    if not is_valid_email_address(recipient):
        raise ValueError("Enter a valid recipient email address.")
    if not subject.strip() or not body.strip():
        raise ValueError("Email subject and message cannot be empty.")

    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient.strip()
    message["Subject"] = " ".join(subject.splitlines()).strip()
    message.set_content(body)

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30) as server:
        server.starttls()
        server.login(sender, app_password)
        refused = server.send_message(message)
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)
