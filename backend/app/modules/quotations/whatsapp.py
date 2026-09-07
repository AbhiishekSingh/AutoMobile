"""Sends a quotation PDF to a customer as a real WhatsApp document attachment,
via Meta's WhatsApp Cloud API (Graph API).

This talks to two Graph API endpoints:
  1. POST /{phone_number_id}/media       — uploads the PDF, returns a media id
  2. POST /{phone_number_id}/messages    — sends a "template" message whose
                                            header references that media id,
                                            with the customer name + vehicle
                                            model filled into the approved
                                            template's body variables

Requires WHATSAPP_API_TOKEN + WHATSAPP_PHONE_NUMBER_ID to be set (see
app/core/config.py / .env). Without them, `send_quotation_pdf` raises
WhatsAppNotConfigured, which the router turns into a clear 400 response
instead of a confusing network error.

Note on WhatsApp policy: a PBA sharing a quotation is a *business-initiated*
message — the customer has not necessarily messaged the dealership first, so
Meta requires an approved message template for it (a plain free-form
document message only works inside the 24-hour window after the customer's
last message, which we can't assume here). This module therefore always
sends via the approved Utility template configured by WHATSAPP_TEMPLATE_NAME
(default "quotation_shared") — a Document-header template with a 2-line body
taking two variables: {{1}} = customer name, {{2}} = vehicle model. If you
change the template's wording or variable count in WhatsApp Manager, update
the `components` payload below to match, or the send will be rejected by
Meta with a "parameter count mismatch" error.
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


def send_quotation_pdf(contact_no: str, pdf_bytes: bytes, filename: str,
                       customer_name: str, model_name: str) -> str:
    """Uploads `pdf_bytes` and sends it via the approved WhatsApp template
    (document header + a 2-line body filled in with `customer_name` and
    `model_name`) to `contact_no`. Returns the WhatsApp message id on success.
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

    # 2. Send the approved template message, with the uploaded PDF as its
    # Document header and (customer_name, model_name) as the body variables.
    send_resp = requests.post(
        _graph_url(f"{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"),
        headers={**auth_headers, "Content-Type": "application/json"},
        json={
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "template",
            "template": {
                "name": settings.WHATSAPP_TEMPLATE_NAME,
                "language": {"code": settings.WHATSAPP_TEMPLATE_LANG},
                "components": [
                    {
                        "type": "header",
                        "parameters": [
                            {
                                "type": "document",
                                "document": {"id": media_id, "filename": filename},
                            }
                        ],
                    },
                    {
                        "type": "body",
                        "parameters": [
                            {"type": "text", "text": customer_name or "Customer"},
                            {"type": "text", "text": model_name or "your vehicle"},
                        ],
                    },
                ],
            },
        },
        timeout=30,
    )
    if send_resp.status_code >= 300:
        raise WhatsAppSendError(f"WhatsApp send failed: {send_resp.text}")

    body = send_resp.json()
    messages = body.get("messages") or []
    return messages[0]["id"] if messages else ""