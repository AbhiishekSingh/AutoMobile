"""Thin Meta WhatsApp Cloud API client (same credentials as the quotation sender)."""
import requests

from app.core.config import settings


class NotConfigured(Exception):
    pass


class SendError(Exception):
    pass


def configured() -> bool:
    return bool(settings.WHATSAPP_API_TOKEN and settings.WHATSAPP_PHONE_NUMBER_ID)


def to_wa_number(raw: str) -> str:
    digits = "".join(c for c in (raw or "") if c.isdigit())
    return f"91{digits}" if len(digits) == 10 else digits


def _url(path: str) -> str:
    return f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}/{path}"


def send_template(to: str, template: str, params: list[str], doc: tuple[bytes, str] | None = None,
                  lang: str | None = None) -> str:
    """Send an approved template. `params` fill {{1}}, {{2}}... of the body in order.
    `doc` = (pdf bytes, filename) for a template with a Document header. Returns the WhatsApp message id."""
    if not configured():
        raise NotConfigured("WhatsApp is not configured on the server (set WHATSAPP_API_TOKEN and WHATSAPP_PHONE_NUMBER_ID).")
    if not template:
        raise NotConfigured("The WhatsApp template name for this message is not set in the server settings.")
    to = to_wa_number(to)
    if len(to) < 11:
        raise SendError("No valid WhatsApp number to send to.")
    auth = {"Authorization": f"Bearer {settings.WHATSAPP_API_TOKEN}"}
    comps = []
    try:
        if doc:
            up = requests.post(_url(f"{settings.WHATSAPP_PHONE_NUMBER_ID}/media"), headers=auth,
                               data={"messaging_product": "whatsapp", "type": "application/pdf"},
                               files={"file": (doc[1], doc[0], "application/pdf")}, timeout=30)
            if up.status_code >= 300:
                raise SendError(_err(up))
            mid = up.json().get("id")
            if not mid:
                raise SendError("WhatsApp did not accept the PDF upload.")
            comps.append({"type": "header", "parameters": [{"type": "document", "document": {"id": mid, "filename": doc[1]}}]})
        if params:
            comps.append({"type": "body", "parameters": [{"type": "text", "text": (p or "-")[:1000]} for p in params]})
        r = requests.post(_url(f"{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"),
                          headers={**auth, "Content-Type": "application/json"},
                          json={"messaging_product": "whatsapp", "to": to, "type": "template",
                                "template": {"name": template, "language": {"code": lang or settings.WHATSAPP_TEMPLATE_LANG},
                                             "components": comps}}, timeout=30)
    except requests.RequestException as e:
        raise SendError(f"Could not reach WhatsApp: {e.__class__.__name__}")
    if r.status_code >= 300:
        raise SendError(_err(r))
    msgs = r.json().get("messages") or []
    return msgs[0]["id"] if msgs else ""


def _err(resp) -> str:
    try:
        e = resp.json().get("error", {})
        return f"{e.get('message', resp.text)} (code {e.get('code', resp.status_code)})"[:500]
    except Exception:
        return resp.text[:500]
