"""
Email Agent for Omakase Sales Bot

Sends emails from info@omakase.com via Infomaniak SMTP.
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from dotenv import load_dotenv


load_dotenv()
email_password = os.getenv('OMAKASE_EMAIL_PASSWORD')  # or whatever your env var is called

SMTP_HOST = "mail.infomaniak.com"
SMTP_PORT = 587
SENDER_EMAIL = "info@omakasegame.com"
SMTP_PASSWORD = email_password


def send_email(
    to: str,
    subject: str,
    body: str,
    attachments: list[str] | None = None,
    html: bool = False,
) -> None:
    """
    Send an email from info@omakase.com.

    Args:
        to:          Recipient email address.
        subject:     Email subject line.
        body:        Email body (plain text or HTML).
        attachments: Optional list of file paths to attach.
        html:        Set to True if body is HTML content.
    """
    if not SMTP_PASSWORD:
        raise ValueError(
            "SMTP password not set. Export OMAKASE_EMAIL_PASSWORD as an environment variable."
        )
    msg = MIMEMultipart()
    msg["From"] = SENDER_EMAIL
    msg["To"] = to
    msg["Subject"] = subject

    mime_type = "html" if html else "plain"
    msg.attach(MIMEText(body, mime_type))

    for path_str in attachments or []:
        path = Path(path_str)
        if not path.is_file():
            raise FileNotFoundError(f"Attachment not found: {path_str}")
        with open(path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{path.name}"')
        msg.attach(part)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(SENDER_EMAIL, SMTP_PASSWORD)
        server.sendmail(SENDER_EMAIL, to, msg.as_string())

    print(f"Email sent to {to} | Subject: {subject}")


if __name__ == "__main__":
    # Example usage
    send_email(
        to="jean.kesselring@gmail.com",
        subject="Hello from Omakase",
        body="This is a test email sent from the Omakase sales bot.",
        attachments=[],  # e.g. ["/path/to/file.pdf"]
    )
