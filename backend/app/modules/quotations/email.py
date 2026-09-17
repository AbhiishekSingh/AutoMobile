"""Sends a quotation PDF to a customer's email address as an attachment,
via plain SMTP.

This is a stopgap for "Send via WhatsApp" while Meta's production message
template is pending approval (roughly a 1-week review) — WhatsApp needs an
approved template for business-initiated messages, but email has no such
approval process, so this can go live immediately.

Deliberately mirrors app/modules/quotations/whatsapp.py in shape:
  - EmailNotConfigured  <-> WhatsAppNotConfigured  (missing .env settings)
  - EmailSendError      <-> WhatsAppSendError      (provider rejected the send)
so the router can handle both the same way, and either channel can be swapped
in or out without changing how failures are reported to the person clicking
the button.

Requires EMAIL_SMTP_HOST, EMAIL_SMTP_USERNAME, EMAIL_SMTP_PASSWORD, and
EMAIL_FROM_ADDRESS to be set (see app/core/config.py / .env). Without them,
`send_quotation_email` raises EmailNotConfigured, which the router turns into
a clear 400 response instead of a confusing connection error.
"""
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings


class EmailNotConfigured(Exception):
    """Raised when the EMAIL_SMTP_* / EMAIL_FROM_ADDRESS settings aren't set."""


class EmailSendError(Exception):
    """Raised when the SMTP server rejects the connection, login, or send."""


def _build_message(to_email: str, customer_name: str, model_name: str,
                   quotation_no: str, pdf_bytes: bytes, filename: str) -> MIMEMultipart:
    msg = MIMEMultipart()
    msg["Subject"] = f"Your Quotation {quotation_no} — S.K Automobiles"
    msg["From"] = settings.EMAIL_FROM_ADDRESS
    msg["To"] = to_email

    body = (
        f"Dear {customer_name or 'Customer'},\n\n"
        f"Thank you for your interest in the {model_name or 'vehicle'}. "
        f"Please find your quotation attached as a PDF.\n\n"
        f"If you have any questions, feel free to reply to this email or "
        f"contact your S.K Automobiles sales advisor.\n\n"
        f"Regards,\nS.K Automobiles"
    )
    msg.attach(MIMEText(body, "plain"))

    attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
    attachment.add_header("Content-Disposition", "attachment", filename=filename)
    msg.attach(attachment)
    return msg


def send_quotation_email(to_email: str, pdf_bytes: bytes, filename: str,
                         customer_name: str, model_name: str, quotation_no: str) -> str:
    """Emails `pdf_bytes` as an attachment to `to_email`. Returns a short
    success string (there's no message-id concept in plain SMTP the way
    WhatsApp has one, so this just confirms the send).
    """
    if not settings.EMAIL_SMTP_HOST or not settings.EMAIL_SMTP_USERNAME \
            or not settings.EMAIL_SMTP_PASSWORD or not settings.EMAIL_FROM_ADDRESS:
        raise EmailNotConfigured(
            "Email isn't configured on the server yet — set EMAIL_SMTP_HOST, "
            "EMAIL_SMTP_USERNAME, EMAIL_SMTP_PASSWORD, and EMAIL_FROM_ADDRESS "
            "in the backend .env to enable sending."
        )

    to_email = (to_email or "").strip()
    if not to_email:
        raise EmailSendError("This quotation has no email address on file to send to.")

    msg = _build_message(to_email, customer_name, model_name, quotation_no,
                         pdf_bytes, filename)

    try:
        if settings.EMAIL_USE_SSL:
            server = smtplib.SMTP_SSL(settings.EMAIL_SMTP_HOST, settings.EMAIL_SMTP_PORT, timeout=30)
        else:
            server = smtplib.SMTP(settings.EMAIL_SMTP_HOST, settings.EMAIL_SMTP_PORT, timeout=30)
        with server:
            if not settings.EMAIL_USE_SSL:
                server.starttls()
            server.login(settings.EMAIL_SMTP_USERNAME, settings.EMAIL_SMTP_PASSWORD)
            server.sendmail(settings.EMAIL_FROM_ADDRESS, [to_email], msg.as_string())
    except smtplib.SMTPAuthenticationError as e:
        raise EmailSendError(
            "Email login was rejected — check EMAIL_SMTP_USERNAME/PASSWORD. "
            "If this is Gmail, you likely need an App Password, not your normal password."
        ) from e
    except (smtplib.SMTPException, OSError) as e:
        raise EmailSendError(f"Email send failed: {e}") from e

    return f"sent to {to_email}"