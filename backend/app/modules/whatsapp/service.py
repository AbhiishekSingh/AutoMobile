"""WhatsApp messages: build -> send -> log. Every attempt is a row in whatsapp_message.

Manual sends (buttons) return the row, success or failure, so the screen can show the failure and offer Retry.
Automatic sends (welcome, test ride, delivery engagement) never raise and never repeat for the same item
once one has gone out; a person can resend manually.
"""
import json
import os

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import now_ist
from app.modules.documents import service as docs
from app.modules.handoffs import delivery as dlv
from app.modules.handoffs.models import DeliveryRecord, InsuranceCase
from app.modules.leads.models import Lead, TestRide
from app.modules.payments.models import Payment
from app.modules.payments.receipt_data import receipt_bytes
from app.modules.whatsapp import client
from app.modules.whatsapp.links import get_link
from app.modules.whatsapp.models import DealerLink, WhatsappMessage

OK = ("SENT", "DELIVERED", "READ")
LINK_KEYS = {"GOOGLE_REVIEW_URL": "Google review link", "INSTAGRAM_URL": "Instagram link", "KTM_APP_URL": "KTM India app link"}
TEMPLATE = {"WELCOME": "WA_TPL_WELCOME", "RECEIPT": "WA_TPL_RECEIPT", "INSURANCE": "WA_TPL_INSURANCE",
            "DELIVERY": "WA_TPL_DELIVERY", "ENGAGEMENT": "WA_TPL_ENGAGEMENT", "REVIEW": "WA_TPL_REVIEW",
            "TEST_RIDE": "WA_TPL_TEST_RIDE"}
KIND_LABEL = {"WELCOME": "Welcome message", "RECEIPT": "Booking receipt", "INSURANCE": "Insurance policy",
              "DELIVERY": "Delivery receipt", "ENGAGEMENT": "Delivery engagement links", "REVIEW": "Google review link",
              "TEST_RIDE": "Test ride scheduled"}


# ---------- links ----------
def _need_links(db, branch_id, keys):
    out = []
    for k in keys:
        v = get_link(db, branch_id, k)
        if not v:
            raise HTTPException(400, f"The {LINK_KEYS[k]} is not set yet. Owner / GM can add it under WhatsApp settings.")
        out.append(v)
    return out


# ---------- message builders: each returns dict(to, params, lead, recipient[, lang]) ----------
def _vehicle(lead):
    return " ".join(x for x in [lead.model.name if lead.model else None, lead.color] if x) or "your KTM"


def _agree_url(kind, token):
    return f"{settings.PUBLIC_API_URL.rstrip('/')}/public/{kind}/{token}"


def _customer(lead):
    return {"to": lead.customer.phone, "lead": lead, "recipient": "CUSTOMER"}


def build_welcome(db, lead, **_):
    from app.modules.users.models import AppUser
    pba = db.get(AppUser, lead.assigned_user_id) if lead.assigned_user_id else None
    if not pba:
        raise HTTPException(400, "The lead is not assigned to a PBA yet")
    br = lead.branch.name if lead.branch else "S.K. Automobiles"
    return {**_customer(lead), "params": [lead.customer.full_name, pba.full_name, br]}


def build_receipt(db, lead, ref_id, lang="en", **_):
    pay = db.get(Payment, ref_id)
    if not pay or pay.lead_id != lead.lead_id:
        raise HTTPException(404, "Payment not found")
    import secrets
    if not pay.agree_token:
        pay.agree_token = secrets.token_urlsafe(32)
    data, entry, summ = receipt_bytes(db, pay, lang)
    return {**_customer(lead), "lang_doc": lang,
            "params": [lead.customer.full_name, entry["receipt_no"], f'{float(pay.amount):,.0f}', _agree_url("receipt", pay.agree_token)]}


def build_insurance(db, lead, **_):
    case = db.query(InsuranceCase).filter(InsuranceCase.lead_id == lead.lead_id).first()
    if not case or case.status != "COMPLETED" or not case.pdf_stored_path:
        raise HTTPException(400, "The insurance policy PDF has not been uploaded yet")
    return {**_customer(lead), "params": [lead.customer.full_name, _vehicle(lead), case.policy_no or "-"]}


def build_delivery(db, lead, **_):
    rec = db.query(DeliveryRecord).filter(DeliveryRecord.lead_id == lead.lead_id).first()
    if not rec or not rec.generated_at:
        raise HTTPException(400, "The delivery receipt has not been generated yet")
    link = dlv.link_token(db, lead)
    return {**_customer(lead), "params": [lead.customer.full_name, _vehicle(lead), rec.receipt_no, _agree_url("delivery", link.ack_token)]}


def build_engagement(db, lead, **_):
    rec = db.query(DeliveryRecord).filter(DeliveryRecord.lead_id == lead.lead_id).first()
    if not rec or not rec.generated_at:
        raise HTTPException(400, "The bike has not been delivered yet")
    app_l, insta, review = _need_links(db, lead.branch_id, ["KTM_APP_URL", "INSTAGRAM_URL", "GOOGLE_REVIEW_URL"])
    br = lead.branch.name if lead.branch else "S.K. Automobiles"
    return {**_customer(lead), "params": [lead.customer.full_name, lead.model.name if lead.model else "bike", br, app_l, insta, review]}


def build_review(db, lead, **_):
    if settings.WA_REVIEW_PARAMS == 4:
        review, app_l, insta = _need_links(db, lead.branch_id, ["GOOGLE_REVIEW_URL", "KTM_APP_URL", "INSTAGRAM_URL"])
        shop = (lead.branch.city or lead.branch.name) if lead.branch else "S.K. Automobiles"
        return {**_customer(lead), "params": [shop.upper(), review, app_l, insta]}
    (review,) = _need_links(db, lead.branch_id, ["GOOGLE_REVIEW_URL"])
    return {**_customer(lead), "params": [review]}


def build_test_ride(db, lead, ref_id, recipient="CUSTOMER", actor=None, **_):
    ride = db.get(TestRide, ref_id)
    if not ride or ride.lead_id != lead.lead_id or not ride.scheduled_at:
        raise HTTPException(404, "Test ride not found")
    from app.modules.users.models import AppUser
    when = ride.scheduled_at
    model = " ".join(x for x in [ride.model.name if ride.model else None, ride.color] if x) or _vehicle(lead)
    cre = f"{actor.full_name}" + (f" ({actor.phone})" if actor is not None and actor.phone else "") if actor else "the showroom"
    base = [lead.customer.full_name, model, when.strftime("%d-%m-%Y"), ride.slot or when.strftime("%I:%M %p"),
            ride.preferred_location or "Showroom", cre]
    if recipient == "PBA":
        pba = db.get(AppUser, lead.assigned_user_id) if lead.assigned_user_id else None
        if not pba:
            raise HTTPException(400, "This customer has no PBA assigned")
        # PBAs share a branch phone: alert goes to the branch WhatsApp number (PBA name is in the text);
        # falls back to the PBA's own number only if the branch has none saved.
        from app.modules.users.models import Branch
        br = db.get(Branch, lead.branch_id) if lead.branch_id else None
        to = (br.whatsapp_number if br and br.whatsapp_number else None) or pba.phone
        if not to:
            raise HTTPException(400, "No branch WhatsApp number saved (Admin: Branches page)")
        return {"to": to, "lead": lead, "recipient": "PBA", "params": [pba.full_name] + base}
    return {**_customer(lead), "params": [lead.customer.full_name] + base}


BUILDERS = {"WELCOME": build_welcome, "RECEIPT": build_receipt, "INSURANCE": build_insurance, "DELIVERY": build_delivery,
            "ENGAGEMENT": build_engagement, "REVIEW": build_review, "TEST_RIDE": build_test_ride}


def _document(db, kind, lead, ref_id, lang):
    """The PDF for kinds that carry one (rebuilt fresh on every attempt, including retries)."""
    if kind == "RECEIPT":
        pay = db.get(Payment, ref_id)
        data, entry, _ = receipt_bytes(db, pay, lang or "en")
        return data, f'{entry["receipt_no"]}.pdf'
    if kind == "INSURANCE":
        case = db.query(InsuranceCase).filter(InsuranceCase.lead_id == lead.lead_id).first()
        path = docs.full_path_of(case.pdf_stored_path)
        if not os.path.exists(path):
            raise HTTPException(400, "The insurance PDF file is missing on the server")
        with open(path, "rb") as f:
            return f.read(), f"Insurance-{case.policy_no or lead.lead_id}.pdf"
    if kind == "DELIVERY":
        rec = db.query(DeliveryRecord).filter(DeliveryRecord.lead_id == lead.lead_id).first()
        return dlv.make_pdf(db, lead, rec), f"{rec.receipt_no}.pdf"
    return None


def _deliver(db, row: WhatsappMessage, lead) -> WhatsappMessage:
    try:
        doc = _document(db, row.kind, lead, row.ref_id, row.lang)
        wid = client.send_template(row.to_number, row.template, json.loads(row.body_params or "[]"), doc)
        row.status, row.wa_message_id, row.error = "SENT", wid, None
    except HTTPException as e:
        row.status, row.error = "FAILED", str(e.detail)
    except (client.NotConfigured, client.SendError) as e:
        row.status, row.error = "FAILED", str(e)
    except Exception as e:   # never let a WhatsApp problem break the screen action
        row.status, row.error = "FAILED", f"Unexpected error: {e.__class__.__name__}"
    return row


def send(db: Session, kind: str, lead: Lead, user=None, ref_id=None, auto=False, lang=None, recipient="CUSTOMER",
         retry_of=None) -> WhatsappMessage:
    """Build, send and log one message. Manual: build problems raise HTTPException (nothing logged).
    Auto: returns None if skipped (already sent / can't build), never raises."""
    ref_id = ref_id if ref_id is not None else lead.lead_id
    if auto:
        dup = db.query(WhatsappMessage).filter(WhatsappMessage.kind == kind, WhatsappMessage.ref_id == ref_id,
                                               WhatsappMessage.recipient == recipient,
                                               WhatsappMessage.status.in_(OK)).first()
        if dup:
            return None
    try:
        spec = BUILDERS[kind](db, lead, ref_id=ref_id, lang=lang or "en", recipient=recipient, actor=user)
    except HTTPException:
        if auto:
            return None
        raise
    row = WhatsappMessage(kind=kind, ref_id=ref_id, lead_id=lead.lead_id, customer_id=lead.customer_id, branch_id=lead.branch_id,
                          recipient=spec["recipient"], to_number=client.to_wa_number(spec["to"]),
                          template=getattr(settings, TEMPLATE[kind], ""), body_params=json.dumps(spec["params"]),
                          lang=spec.get("lang_doc"), auto=1 if auto else 0, retry_of_id=retry_of,
                          created_by_user_id=getattr(user, "user_id", None), created_at=now_ist())
    db.add(row)
    _deliver(db, row, lead)
    db.flush()
    return row


def auto_send(db, kind, lead, **kw):
    """Fire-and-forget: any problem is swallowed (the log shows failures)."""
    try:
        return send(db, kind, lead, auto=True, **kw)
    except Exception:
        return None


def retry(db: Session, row: WhatsappMessage, user) -> WhatsappMessage:
    if row.status != "FAILED":
        raise HTTPException(400, "Only a failed message can be retried")
    if db.query(WhatsappMessage).filter(WhatsappMessage.retry_of_id == row.id).first():
        raise HTTPException(400, "This message was already retried")
    lead = db.get(Lead, row.lead_id)
    new = WhatsappMessage(kind=row.kind, ref_id=row.ref_id, lead_id=row.lead_id, customer_id=row.customer_id, branch_id=row.branch_id,
                          recipient=row.recipient, to_number=row.to_number, template=getattr(settings, TEMPLATE[row.kind], row.template),
                          body_params=row.body_params, lang=row.lang, auto=0, retry_of_id=row.id,
                          created_by_user_id=user.user_id, created_at=now_ist())
    db.add(new)
    _deliver(db, new, lead)
    db.flush()
    return new


def after_delivery_sent(db, lead, user):
    """Delivery receipt went out -> send the engagement links once."""
    return auto_send(db, "ENGAGEMENT", lead, user=user)


def row_dict(m: WhatsappMessage, names=None) -> dict:
    return {"id": m.id, "kind": m.kind, "label": KIND_LABEL.get(m.kind, m.kind), "recipient": m.recipient, "to": m.to_number,
            "template": m.template, "status": m.status, "error": m.error, "auto": bool(m.auto), "at": m.created_at,
            "delivered_at": m.delivered_at, "read_at": m.read_at, "retried": False,
            "by": (names or {}).get(m.created_by_user_id), "ref_id": m.ref_id}
