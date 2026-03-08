"""
Email Constructor for Omakase Sales Bot

Reads a base email template, substitutes the shop name, and returns
the constructed subject line and email body.
"""

from pathlib import Path


def construct_email(basemail_path: str | Path, shop_name: str) -> dict:
    """
    Build a personalised email from a template.

    Args:
        basemail_path: Path to the base email template file.
        shop_name:     Name of the shop to address the email to.

    Returns:
        Dict with keys:
            - 'subject': the email subject line
            - 'body':    the full email body text
    """
    template = Path(basemail_path).read_text(encoding="utf-8")
    body = template.replace("{shop_name}", shop_name)
    subject = f"Omakase at {shop_name}?"

    return {"subject": subject, "body": body}


if __name__ == "__main__":
    BASEMAIL = Path(__file__).parent / "prompts" / "basemail.txt"
    result = construct_email(BASEMAIL, shop_name="Spielwaren Müller")
    print(f"Subject: {result['subject']}\n")
    print(result["body"])
