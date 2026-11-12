import hashlib
import hmac
import json
from datetime import date, datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user, get_db, require_roles
from app.modules.users.access import get_visible_lead
from app.modules.users.models import AppUser, Branch
from app.modules.whatsapp import client, service as svc
from app.modules.whatsapp.models import DealerLink, WhatsappMessage

router = APIRouter(tags=["whatsapp"])
ALL = ("PBA", "CRE", "OWNER", "GM", "ADMIN")
IST = timezone(timedelta(hours=5, minutes=30))


def _out(db, m):
    names = {u.user_id: u.full_name for u in db.query(AppUser).filter(AppUser.user_id == m.created_by_user_id)}
    d = svc.row_dict(m, names)
    d["retried"] = db.query(WhatsappMessage).filter(WhatsappMessage.retry_of_id == m.id).first() is not None
    return d


def _go(db, user, lead_id, kind, roles, **kw):
    if user.role.value not in roles:
        raise HTTPException(403, "You can't send this message")
    lead = get_visible_lead(db, user, lead_id)
    row = svc.send(db, kind, lead, user=user, **kw)
    # delivery receipt sent OK -> engagement links follow automatically (once)
    if kind == "DELIVERY" and row.status != "FAILED":
        svc.after_delivery_sent(db, lead, user)
    db.commit()
    return _out(db, row)


class ReceiptIn(BaseModel):
    payment_id: int
    lang: str = "en"


@router.post("/leads/{lead_id}/whatsapp/receipt")
def send_receipt(lead_id: int, body: ReceiptIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.lang not in ("en", "mr"):
        raise HTTPException(400, "Unknown language")
    return _go(db, user, lead_id, "RECEIPT", ALL, ref_id=body.payment_id, lang=body.lang)


@router.post("/leads/{lead_id}/whatsapp/insurance")
def send_insurance(lead_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return _go(db, user, lead_id, "INSURANCE", ("PBA", "CRE", "OWNER", "GM", "ADMIN", "INSURANCE"))


@router.post("/leads/{lead_id}/whatsapp/delivery")
def send_delivery(lead_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return _go(db, user, lead_id, "DELIVERY", ("PBA", "OWNER", "GM", "ADMIN"))


@router.post("/leads/{lead_id}/whatsapp/engagement")
def send_engagement(lead_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return _go(db, user, lead_id, "ENGAGEMENT", ("PBA", "OWNER", "GM", "ADMIN"))


@router.post("/leads/{lead_id}/whatsapp/review")
def send_review(lead_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return _go(db, user, lead_id, "REVIEW", ALL)


@router.post("/leads/{lead_id}/whatsapp/welcome")
def send_welcome(lead_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return _go(db, user, lead_id, "WELCOME", ("PBA", "CRE", "OWNER", "GM", "ADMIN"))


@router.get("/leads/{lead_id}/whatsapp")
def lead_log(lead_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role.value not in ALL + ("INSURANCE",):
        raise HTTPException(403, "Insufficient permissions")
    get_visible_lead(db, user, lead_id)
    rows = db.query(WhatsappMessage).filter(WhatsappMessage.lead_id == lead_id).order_by(WhatsappMessage.id.desc()).all()
    return {"configured": client.configured(), "messages": [_out(db, m) for m in rows]}


@router.post("/whatsapp/{msg_id}/retry")
def retry_message(msg_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role.value not in ALL:
        raise HTTPException(403, "Insufficient permissions")
    m = db.get(WhatsappMessage, msg_id)
    if not m:
        raise HTTPException(404, "Message not found")
    get_visible_lead(db, user, m.lead_id)
    new = svc.retry(db, m, user)
    db.commit()
    return _out(db, new)


# ---------- links (Owner / GM / Admin) ----------
class LinkIn(BaseModel):
    branch_id: int | None = None
    key: str
    value: str | None = None


@router.get("/whatsapp/links", dependencies=[Depends(require_roles("OWNER", "GM", "ADMIN"))])
def links(db: Session = Depends(get_db)):
    rows = db.query(DealerLink).all()
    return {"keys": [{"key": k, "label": v} for k, v in svc.LINK_KEYS.items()],
            "branches": [{"id": b.branch_id, "name": b.name} for b in db.query(Branch).filter(Branch.is_active == True).all()],  # noqa: E712
            "values": [{"branch_id": r.branch_id, "key": r.key, "value": r.value} for r in rows],
            "configured": client.configured()}


@router.put("/whatsapp/links")
def save_link(body: LinkIn, user: AppUser = Depends(require_roles("OWNER", "GM", "ADMIN")), db: Session = Depends(get_db)):
    if body.key not in svc.LINK_KEYS:
        raise HTTPException(400, "Unknown link")
    v = (body.value or "").strip()
    if v and not v.lower().startswith(("http://", "https://")):
        raise HTTPException(400, "The link must start with https://")
    row = db.query(DealerLink).filter(DealerLink.key == body.key,
                                      DealerLink.branch_id.is_(None) if body.branch_id is None else DealerLink.branch_id == body.branch_id).first()
    if row:
        row.value = v or None; row.updated_by_user_id = user.user_id
    elif v:
        db.add(DealerLink(branch_id=body.branch_id, key=body.key, value=v, updated_by_user_id=user.user_id))
    db.commit()
    return {"ok": True}


@router.post("/whatsapp/links/preset")
def apply_preset(overwrite: bool = False, user: AppUser = Depends(require_roles("OWNER", "GM", "ADMIN")), db: Session = Depends(get_db)):
    """Fill the showroom links (Google review, Instagram) and the KTM app link from the dealership's list.
    Showrooms are matched by name/city; a link already set is kept unless overwrite=true."""
    from app.modules.whatsapp import presets

    def put(branch_id, key, value):
        row = db.query(DealerLink).filter(DealerLink.key == key, DealerLink.branch_id.is_(None) if branch_id is None else DealerLink.branch_id == branch_id).first()
        if row and row.value and not overwrite:
            return 0
        if row:
            row.value, row.updated_by_user_id = value, user.user_id
        else:
            db.add(DealerLink(branch_id=branch_id, key=key, value=value, updated_by_user_id=user.user_id))
        return 1
    matched, skipped, set_n = [], [], 0
    seen = set()
    for b in db.query(Branch).filter(Branch.is_active == True).all():  # noqa: E712
        k = presets.match(b)
        if not k:
            skipped.append(b.name); continue
        seen.add(k); matched.append(f"{b.name} -> {k}")
        for key, val in presets.PRESET[k].items():
            set_n += put(b.branch_id, key, val)
    set_n += put(None, "KTM_APP_URL", presets.KTM_APP)
    db.commit()
    return {"links_set": set_n, "matched": matched, "branches_not_matched": skipped,
            "list_entries_without_branch": [k for k in presets.PRESET if k not in seen]}


@router.get("/whatsapp/review-log")
def review_log(date_from: date | None = None, date_to: date | None = None, cre_id: int | None = None, branch_id: int | None = None,
               user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """Google-review link messages: who got it, which CRE sent it, when, delivery status, how many times it was sent."""
    import json
    from datetime import datetime, time, timedelta
    from app.modules.leads.models import Lead
    from app.modules.users.access import scope_leads
    if user.role.value not in ("CRE", "OWNER", "GM", "ADMIN"):
        raise HTTPException(403, "Insufficient permissions")
    q = (db.query(WhatsappMessage, Lead).join(Lead, Lead.lead_id == WhatsappMessage.lead_id).filter(WhatsappMessage.kind == "REVIEW"))
    q = scope_leads(q, user)
    if date_from: q = q.filter(WhatsappMessage.created_at >= datetime.combine(date_from, time.min))
    if date_to: q = q.filter(WhatsappMessage.created_at < datetime.combine(date_to + timedelta(days=1), time.min))
    if cre_id: q = q.filter(WhatsappMessage.created_by_user_id == cre_id)
    if branch_id: q = q.filter(Lead.branch_id == branch_id)
    rows = q.order_by(WhatsappMessage.created_at.desc()).limit(1000).all()
    names = {u.user_id: u.full_name for u in db.query(AppUser).all()}
    counts = {}
    for m, l in db.query(WhatsappMessage, Lead).join(Lead, Lead.lead_id == WhatsappMessage.lead_id).filter(WhatsappMessage.kind == "REVIEW").order_by(WhatsappMessage.id).all():
        counts.setdefault(m.lead_id, []).append(m.id)
    out = []
    for m, l in rows:
        try:
            link = next((p for p in json.loads(m.body_params or "[]") if str(p).startswith("http") and "google" in str(p)), None)
        except Exception:
            link = None
        ids = counts.get(m.lead_id, [])
        out.append({"id": m.id, "customer": l.customer.full_name, "lead_id": l.lead_id, "enquiry_no": l.enquiry_no, "mobile": m.to_number or l.customer.phone,
                    "branch": l.branch.name if l.branch else None, "cre": names.get(m.created_by_user_id), "link": link, "sent_at": m.created_at,
                    "status": m.status, "error": m.error, "send_no": ids.index(m.id) + 1 if m.id in ids else 1, "total_sends": len(ids),
                    "is_retry": bool(m.retry_of_id)})
    return out


# ---------- Meta webhook: delivery status ----------
@router.get("/webhooks/whatsapp")
def verify(mode: str = Query(None, alias="hub.mode"), token: str = Query(None, alias="hub.verify_token"),
           challenge: str = Query("", alias="hub.challenge")):
    if mode == "subscribe" and settings.WHATSAPP_VERIFY_TOKEN and hmac.compare_digest(token or "", settings.WHATSAPP_VERIFY_TOKEN):
        return Response(challenge, media_type="text/plain")
    raise HTTPException(403, "Verification failed")


@router.post("/webhooks/whatsapp")
async def webhook(request: Request, db: Session = Depends(get_db)):
    raw = await request.body()
    if settings.WHATSAPP_APP_SECRET:
        sig = request.headers.get("X-Hub-Signature-256", "")
        want = "sha256=" + hmac.new(settings.WHATSAPP_APP_SECRET.encode(), raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, want):
            raise HTTPException(403, "Bad signature")
    try:
        payload = json.loads(raw or b"{}")
    except ValueError:
        return {"ok": True}
    rank = {"SENT": 1, "DELIVERED": 2, "READ": 3}
    for entry in payload.get("entry", []):
        for ch in entry.get("changes", []):
            for st in (ch.get("value") or {}).get("statuses", []):
                m = db.query(WhatsappMessage).filter(WhatsappMessage.wa_message_id == st.get("id")).first()
                if not m:
                    continue
                s = (st.get("status") or "").lower()
                ts = datetime.fromtimestamp(int(st["timestamp"]), IST).replace(tzinfo=None) if st.get("timestamp") else None
                if s == "failed":
                    errs = st.get("errors") or [{}]
                    m.status = "FAILED"; m.error = f'{errs[0].get("title") or errs[0].get("message") or "Delivery failed"} (code {errs[0].get("code", "?")})'[:500]
                elif s in ("delivered", "read"):
                    if rank.get(s.upper(), 0) > rank.get(m.status, 0):
                        m.status = s.upper()
                    if s == "delivered": m.delivered_at = ts
                    else: m.read_at = ts; m.delivered_at = m.delivered_at or ts
    db.commit()
    return {"ok": True}
