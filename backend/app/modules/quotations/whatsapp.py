"""Sends a quotation PDF to a customer as a real WhatsApp document attachment,
via Meta's WhatsApp Cloud API (Graph API).

This talks to two Graph API endpoints:
  1. POST /{phone_number_id}/media       — uploads the PDF, returns a media id
  2. POST /{phone_number_id}/messages    — sends a "document" message that
                                            references that media id, with a
                                            plain-text caption (no links)

Requires WHATSAPP_API_TOKEN + WHATSAPP_PHONE_NUMBER_ID to be set (see
app/core/config.py / .env). Without them, `send_quotation_pdf` raises
WhatsAppNotConfigured, which the router turns into a clear 400 response
instead of a confusing network error.

Note on WhatsApp policy: Meta only allows a business to freely message a
customer with arbitrary text/document content inside the 24-hour "customer
service window" after the customer last messaged the business number. Outside
that window, WhatsApp requires a pre-approved message template instead. This
module sends a normal (non-template) document message, which is correct for
replying to an inbound customer conversation; if you need to *start* a
conversation from cold, you'll need to set up an approved template in Meta
Business Manager and switch the `messages` payload below to `type: "template"`.
"""
import requests

from app.core.config import settings


class WhatsAppNotConfigured(Exception):
    """Raised when WHATSAPP_API_TOKEN / WHATSAPP_PHONE_NUMBER_ID aren't set."""


class WhatsAppSendError(Exception):
    """Raised when the Graph API rejects the upload or the send."""


def _graph_url(path: str) -> str:
    return f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}/{path}"


def _to_wa_number(contact_no: str) -> str:
    """Normalise a stored contact number into WhatsApp's expected format
    (country code + number, digits only, no leading '+'). Assumes India (91)
    for bare 10-digit numbers, matching the rest of the app's phone handling.
    """
    digits = "".join(ch for ch in (contact_no or "") if ch.isdigit())
    if len(digits) == 10:
        return f"91{digits}"
    return digits


def send_quotation_pdf(contact_no: str, pdf_bytes: bytes, filename: str, caption: str) -> str:
    """Uploads `pdf_bytes` and sends it as a WhatsApp document message with
    `caption` to `contact_no`. Returns the WhatsApp message id on success.
    """
    if not settings.WHATSAPP_API_TOKEN or not settings.WHATSAPP_PHONE_NUMBER_ID:
        raise WhatsAppNotConfigured(
            "WhatsApp isn't configured on the server yet — set WHATSAPP_API_TOKEN "
            "and WHATSAPP_PHONE_NUMBER_ID in the backend .env to enable sending."
        )

    to_number = _to_wa_number(contact_no)
    if not to_number:
        raise WhatsAppSendError("This quotation has no valid contact number to send to.")

    auth_headers = {"Authorization": f"Bearer {settings.WHATSAPP_API_TOKEN}"}

    # 1. Upload the PDF as media
    upload_resp = requests.post(
        _graph_url(f"{settings.WHATSAPP_PHONE_NUMBER_ID}/media"),
        headers=auth_headers,
        data={"messaging_product": "whatsapp", "type": "application/pdf"},
        files={"file": (filename, pdf_bytes, "application/pdf")},
        timeout=30,
    )
    if upload_resp.status_code >= 300:
        raise WhatsAppSendError(f"WhatsApp media upload failed: {upload_resp.text}")
    media_id = upload_resp.json().get("id")
    if not media_id:
        raise WhatsAppSendError("WhatsApp media upload did not return a media id.")

    # 2. Send the document message referencing that media id
    send_resp = requests.post(
        _graph_url(f"{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"),
        headers={**auth_headers, "Content-Type": "application/json"},
        json={
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "document",
            "document": {"id": media_id, "filename": filename, "caption": caption},
        },
        timeout=30,
    )
    if send_resp.status_code >= 300:
        raise WhatsAppSendError(f"WhatsApp send failed: {send_resp.text}")

    body = send_resp.json()
    messages = body.get("messages") or []
    return messages[0]["id"] if messages else ""