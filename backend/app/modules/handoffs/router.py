"""Hand-off endpoints (insurance, RTO, owner approval, ATW, delivery reminders).

  GET  /leads/{id}/handoffs                    the whole panel for one lead
  PUT  /leads/{id}/insurance                   policy type, nominee, hypothecation   (CRE / Admin)
  POST /leads/{id}/insurance/policy            policy no., dates, premium + PDF -> COMPLETED
  GET  /leads/{id}/insurance/policy.pdf        view / download the policy PDF
  PATCH /leads/{id}/rto                        RTO status, registration no., delivery date (RTO / Admin)
  POST /leads/{id}/approval                    PBA asks the Owner to approve
  POST /leads/{id}/approval/decision           Owner approves / rejects
  POST /leads/{id}/atw   +  /atw/decision      same for the 10-year engine warranty
  GET  /handoffs/delivery-reminders            approved deliveries due within 5 days
  GET  /handoffs/queue                         the logged-in role's worklist
"""
from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.modules.audit.service import record_changes
from app.modules.documents import service as docs
from app.modules.handoffs import delivery as dlv
from app.modules.handoffs import service as svc
from app.modules.handoffs.models import (AtwApproval, InsuranceCase, InvoiceDetail, OwnerApproval,
                                         RtoCase)
from app.modules.leads.models import Lead
from app.modules.notifications.models import NotificationType
from app.modules.payments import service as pay_svc
from app.modules.users.access import MANAGER_ROLES, SALES_ROLES, scope_leads, get_visible_lead
from app.modules.users.models import AppUser

router = APIRouter(tags=["handoffs"])
ALL_ROLES = SALES_ROLES + MANAGER_ROLES + ("RTO", "INSURANCE")


def _panel(db: Session, lead: Lead) -> dict:
    out = svc.panel(db, lead)
    if out["booking_no"]:
        out["delivery"] = dlv.state(db, lead)
    return out


def _lead_for(db: Session, user: AppUser, lead_id: int) -> Lead:
    """Normal lead visibility; the RTO may also open leads that have reached the RTO."""
    if user.role.value == "RTO":
        lead = db.get(Lead, lead_id)
        rto = svc.get_case(db, RtoCase, lead_id) if lead else None
        if not lead or not rto:
            raise HTTPException(404, "Lead not found")
        return lead
    return get_visible_lead(db, user, lead_id)


@router.get("/leads/{lead_id}/handoffs", dependencies=[Depends(require_roles(*ALL_ROLES))])
def get_panel(lead_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    lead = _lead_for(db, user, lead_id)
    if svc.is_booking_done(lead) or pay_svc.get_booking(db, lead_id):
        if svc.ensure_insurance_case(db, lead):       # covers leads that were already BOOKING DONE
            db.commit()
    return _panel(db, lead)


# ---------------- invoice details ----------------
@router.put("/leads/{lead_id}/invoice", dependencies=[Depends(require_roles("PBA"))])
def save_invoice(lead_id: int, chassis_no: str = Form(...), engine_no: str = Form(...),
                 invoice_no: Optional[str] = Form(None), invoice_date: Optional[date] = Form(None),
                 registration_type: Optional[str] = Form(None), hypothecation: Optional[str] = Form(None),
                 nominee_name: Optional[str] = Form(None), nominee_relation: Optional[str] = Form(None),
                 insurance_addon: Optional[str] = Form(None), delivery_date: Optional[date] = Form(None),
                 file: Optional[UploadFile] = File(None), user: AppUser = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    """Invoice copy + chassis / engine no. + registration type + insurance options + delivery date.
    The first save moves the lead towards INVOICED (see service.sync_stage). The file is optional
    when editing an existing invoice."""
    lead = get_visible_lead(db, user, lead_id)
    saved = docs.save_upload(file, lead.customer_id) if file is not None and file.filename else None
    old = svc.get_case(db, InvoiceDetail, lead_id)
    old_path, before = (old.file_stored_path if old else None), \
        ({f: getattr(old, f) for f in ("chassis_no", "engine_no", "registration_type", "delivery_date")} if old else None)
    try:
        row = svc.save_invoice(db, lead, dict(
            chassis_no=chassis_no, engine_no=engine_no, invoice_no=invoice_no, invoice_date=invoice_date,
            registration_type=registration_type or None, hypothecation=hypothecation,
            nominee_name=nominee_name, nominee_relation=nominee_relation or None,
            insurance_addon=insurance_addon, delivery_date=delivery_date), saved, user)
        record_changes(db, entity_type="invoice", entity_id=row.id,
                       before=before or {"chassis_no": None, "engine_no": None, "registration_type": None, "delivery_date": None},
                       after=row, fields=("chassis_no", "engine_no", "registration_type", "delivery_date"),
                       changed_by_user_id=user.user_id)
        db.commit()
    except Exception:
        db.rollback()
        if saved:
            docs.delete_file(saved["stored_path"])
        raise
    if saved and old_path:
        docs.delete_file(old_path)           # the replaced copy is no longer needed
    return _panel(db, lead)


@router.get("/leads/{lead_id}/invoice/file", dependencies=[Depends(require_roles(*ALL_ROLES))])
def get_invoice_file(lead_id: int, download: bool = False, user: AppUser = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    _lead_for(db, user, lead_id)
    inv = svc.get_case(db, InvoiceDetail, lead_id)
    if not inv or not inv.file_stored_path:
        raise HTTPException(404, "No invoice copy uploaded yet")
    return FileResponse(docs.full_path_of(inv.file_stored_path), media_type=inv.file_content_type,
                        filename=inv.file_original_name,
                        content_disposition_type="attachment" if download else "inline")


# ---------------- insurance ----------------
class InsuranceDetails(BaseModel):
    policy_type: Optional[str] = None
    nominee_name: Optional[str] = None
    nominee_age: Optional[int] = None
    nominee_relation: Optional[str] = None
    nominee_relation_other: Optional[str] = None
    hypothecation: Optional[str] = None


@router.put("/leads/{lead_id}/insurance",
            dependencies=[Depends(require_roles(*svc.WRITE_INSURANCE_ROLES))])
def save_insurance(lead_id: int, body: InsuranceDetails, user: AppUser = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    lead = get_visible_lead(db, user, lead_id)
    case = svc.get_case(db, InsuranceCase, lead_id)
    if not case:
        raise HTTPException(400, "Insurance starts when the lead is BOOKING DONE")
    if case.status == "COMPLETED":
        raise HTTPException(400, "The insurance is completed and can no longer be edited")
    d = body.model_dump(exclude_unset=True)
    if d.get("policy_type") not in (None, *svc.POLICY_TYPES):
        raise HTTPException(400, "Unknown policy type")
    if d.get("nominee_relation") not in (None, *svc.NOMINEE_RELATIONS):
        raise HTTPException(400, "Unknown nominee relation")
    if d.get("nominee_age") is not None and not (1 <= d["nominee_age"] <= 120):
        raise HTTPException(400, "Nominee age must be between 1 and 120")
    fields = tuple(d)
    before = {f: getattr(case, f) for f in fields}
    for k, v in d.items():
        setattr(case, k, (v.strip() or None) if isinstance(v, str) else v)
    if case.nominee_relation != "Other":
        case.nominee_relation_other = None
    case.updated_by_user_id = user.user_id
    if case.status == "PENDING":
        case.status = "IN_PROGRESS"
    record_changes(db, entity_type="insurance", entity_id=case.id, before=before, after=case,
                   fields=fields, changed_by_user_id=user.user_id)
    db.commit()
    return _panel(db, lead)


@router.post("/leads/{lead_id}/insurance/policy",
             dependencies=[Depends(require_roles(*svc.WRITE_INSURANCE_ROLES))])
def upload_policy(lead_id: int, policy_no: str = Form(...), policy_start: date = Form(...),
                  policy_expiry: date = Form(...), premium: Optional[Decimal] = Form(None),
                  file: UploadFile = File(...), user: AppUser = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    lead = get_visible_lead(db, user, lead_id)
    case = svc.get_case(db, InsuranceCase, lead_id)
    if not case:
        raise HTTPException(400, "Insurance starts when the lead is BOOKING DONE")
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "The insurance policy must be a PDF file")
    saved = docs.save_upload(file, lead.customer_id)
    try:
        svc.complete_insurance(db, lead, case, policy_no=policy_no, start=policy_start,
                               expiry=policy_expiry, premium=premium, saved=saved, user=user)
        record_changes(db, entity_type="insurance", entity_id=case.id,
                       before={"status": "IN_PROGRESS", "policy_no": None}, after=case,
                       fields=("status", "policy_no"), changed_by_user_id=user.user_id)
        db.commit()
    except Exception:
        db.rollback()
        docs.delete_file(saved["stored_path"])
        raise
    return _panel(db, lead)


@router.get("/leads/{lead_id}/insurance/policy.pdf", dependencies=[Depends(require_roles(*ALL_ROLES))])
def get_policy_pdf(lead_id: int, download: bool = False, user: AppUser = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    _lead_for(db, user, lead_id)
    case = svc.get_case(db, InsuranceCase, lead_id)
    if not case or not case.pdf_stored_path:
        raise HTTPException(404, "No insurance policy has been uploaded yet")
    return FileResponse(docs.full_path_of(case.pdf_stored_path), media_type="application/pdf",
                        filename=case.pdf_original_name,
                        content_disposition_type="attachment" if download else "inline")


# ---------------- RTO ----------------
class RtoUpdate(BaseModel):
    status: Optional[str] = None
    registration_type: Optional[str] = None
    registration_no: Optional[str] = None
    registration_date: Optional[date] = None
    delivery_date: Optional[date] = None


@router.patch("/leads/{lead_id}/rto", dependencies=[Depends(require_roles(*svc.WRITE_RTO_ROLES))])
def save_rto(lead_id: int, body: RtoUpdate, user: AppUser = Depends(get_current_user),
             db: Session = Depends(get_db)):
    lead = db.get(Lead, lead_id)
    rto = svc.get_case(db, RtoCase, lead_id) if lead else None
    if not rto:
        raise HTTPException(400, "The file reaches the RTO after the insurance policy is uploaded")
    data = body.model_dump(exclude_unset=True)
    fields = tuple(k for k in data)
    before = {f: getattr(rto, f) for f in fields}
    svc.update_rto(db, lead, rto, data, user)
    record_changes(db, entity_type="rto", entity_id=rto.id, before=before, after=rto, fields=fields,
                   changed_by_user_id=user.user_id)
    db.commit()
    return _panel(db, lead)


# ---------------- owner approval / ATW ----------------
class ApprovalRequest(BaseModel):
    items: list[str] = []
    note: Optional[str] = None
    delivery_date: Optional[date] = None


class Decision(BaseModel):
    approve: bool
    note: Optional[str] = None


@router.post("/leads/{lead_id}/approval", dependencies=[Depends(require_roles("PBA"))])
def ask_approval(lead_id: int, body: ApprovalRequest, user: AppUser = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    lead = get_visible_lead(db, user, lead_id)
    row = svc.request_approval(db, lead, body.items, body.note, body.delivery_date, user)
    record_changes(db, entity_type="owner_approval", entity_id=row.id, before={"status": None},
                   after=row, fields=("status",), changed_by_user_id=user.user_id)
    db.commit()
    return _panel(db, lead)


@router.post("/leads/{lead_id}/approval/decision", dependencies=[Depends(require_roles("OWNER"))])
def decide_approval(lead_id: int, body: Decision, user: AppUser = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    lead = db.get(Lead, lead_id)
    row = svc.get_case(db, OwnerApproval, lead_id) if lead else None
    if not row:
        raise HTTPException(404, "No approval request for this lead")
    before = {"status": row.status}
    svc.decide(db, lead, row, body.approve, body.note, user, NotificationType.APPROVAL_DECIDED, "Approval")
    record_changes(db, entity_type="owner_approval", entity_id=row.id, before=before, after=row,
                   fields=("status",), changed_by_user_id=user.user_id)
    db.commit()
    return _panel(db, lead)


@router.post("/leads/{lead_id}/atw", dependencies=[Depends(require_roles("PBA"))])
def ask_atw(lead_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    lead = get_visible_lead(db, user, lead_id)
    row = svc.request_atw(db, lead, user)
    record_changes(db, entity_type="atw", entity_id=row.id, before={"status": None}, after=row,
                   fields=("status",), changed_by_user_id=user.user_id)
    db.commit()
    return _panel(db, lead)


@router.post("/leads/{lead_id}/atw/decision", dependencies=[Depends(require_roles("OWNER"))])
def decide_atw(lead_id: int, body: Decision, user: AppUser = Depends(get_current_user),
               db: Session = Depends(get_db)):
    lead = db.get(Lead, lead_id)
    row = svc.get_case(db, AtwApproval, lead_id) if lead else None
    if not row:
        raise HTTPException(404, "No ATW request for this lead")
    before = {"status": row.status}
    svc.decide(db, lead, row, body.approve, body.note, user, NotificationType.ATW_DECIDED, "ATW")
    record_changes(db, entity_type="atw", entity_id=row.id, before=before, after=row, fields=("status",),
                   changed_by_user_id=user.user_id)
    db.commit()
    return _panel(db, lead)


# ---------------- reminders + worklists ----------------
@router.get("/handoffs/delivery-reminders",
            dependencies=[Depends(require_roles(*SALES_ROLES, *MANAGER_ROLES))])
def delivery_reminders(user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.delivery_reminders(db, scope_leads(db.query(Lead), user))


@router.get("/handoffs/queue", dependencies=[Depends(require_roles(*ALL_ROLES))])
def queue(user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """Worklist for the logged-in role.
       OWNER -> approvals + ATW waiting;  RTO -> RTO cases not yet registered;
       CRE / ADMIN / GM -> insurance cases not completed (CRE: own branches)."""
    role = user.role.value
    out = []
    def row(lead, **extra):
        return {"lead_id": lead.lead_id, "enquiry_no": lead.enquiry_no,
                "customer_name": lead.customer.full_name, "branch": lead.branch.name if lead.branch else None, **extra}
    if role == "OWNER":
        for a in db.query(OwnerApproval).filter(OwnerApproval.status == "PENDING").all():
            out.append(row(db.get(Lead, a.lead_id), kind="APPROVAL", since=a.requested_at,
                           items=[svc.SPECIAL_ITEMS.get(i, i) for i in (a.special_items or "").split(",") if i],
                           delivery_date=a.delivery_date.isoformat() if a.delivery_date else None))
        for a in db.query(AtwApproval).filter(AtwApproval.status == "PENDING").all():
            out.append(row(db.get(Lead, a.lead_id), kind="ATW", since=a.requested_at, model_name=a.model_name))
    elif role == "RTO":
        for r in db.query(RtoCase).filter(RtoCase.status != "REGISTERED").all():
            out.append(row(db.get(Lead, r.lead_id), kind="RTO", status=r.status, since=r.created_at,
                           registration_type=svc.REG_TYPES.get(r.registration_type)))
    else:
        q = scope_leads(db.query(Lead), user).join(InsuranceCase, InsuranceCase.lead_id == Lead.lead_id) \
            .filter(InsuranceCase.status != "COMPLETED").add_columns(InsuranceCase.status, InsuranceCase.created_at)
        for lead, st, since in q.all():
            out.append(row(lead, kind="INSURANCE", status=st, since=since))
    return out


# ---------------- delivery ----------------
class OverrideIn(BaseModel):
    reason: str


@router.post("/leads/{lead_id}/delivery/override", dependencies=[Depends(require_roles("OWNER"))])
def delivery_override(lead_id: int, body: OverrideIn, user: AppUser = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    """The Owner allows delivery although approval / payment is still pending (reason required)."""
    lead = db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    rec = dlv.override(db, lead, body.reason, user)
    record_changes(db, entity_type="delivery", entity_id=rec.id, before={"override_reason": None}, after=rec,
                   fields=("override_reason",), changed_by_user_id=user.user_id)
    db.commit()
    return _panel(db, lead)


@router.post("/leads/{lead_id}/delivery/generate", dependencies=[Depends(require_roles("PBA"))])
def delivery_generate(lead_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """Hand over the bike: creates the delivery receipt, sets today as the delivery date, stage -> DELIVERED."""
    lead = get_visible_lead(db, user, lead_id)
    rec = dlv.generate(db, lead, user)
    record_changes(db, entity_type="delivery", entity_id=rec.id, before={"receipt_no": None}, after=rec,
                   fields=("receipt_no", "delivery_date"), changed_by_user_id=user.user_id)
    db.commit()
    return _panel(db, lead)


@router.get("/leads/{lead_id}/delivery/receipt.pdf",
            dependencies=[Depends(require_roles(*SALES_ROLES, *MANAGER_ROLES))])
def delivery_pdf(lead_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    lead = _lead_for(db, user, lead_id)
    rec = dlv._rec(db, lead_id)
    if not rec or not rec.generated_at:
        raise HTTPException(404, "The delivery receipt has not been generated yet")
    return Response(dlv.make_pdf(db, lead, rec), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{rec.receipt_no}.pdf"'})


@router.get("/leads/{lead_id}/delivery/accepted.pdf",
            dependencies=[Depends(require_roles(*SALES_ROLES, *MANAGER_ROLES))])
def delivery_accepted_pdf(lead_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """The copy the customer accepted (PBA, GM, Owner, CRE, Admin)."""
    _lead_for(db, user, lead_id)
    from app.modules.documents.models import CustomerDocument
    rec = dlv._rec(db, lead_id)
    doc = db.get(CustomerDocument, rec.accepted_doc_id) if rec and rec.accepted_doc_id else None
    if not doc:
        raise HTTPException(404, "The customer has not accepted the receipt yet")
    return FileResponse(docs.full_path_of(doc.stored_path), media_type="application/pdf",
                        filename=doc.original_name, content_disposition_type="inline")


@router.post("/leads/{lead_id}/delivery/link",
             dependencies=[Depends(require_roles(*SALES_ROLES, *MANAGER_ROLES))])
def delivery_link(lead_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.core.config import settings
    lead = _lead_for(db, user, lead_id)
    rec = dlv.link_token(db, lead)
    db.commit()
    return {"url": f"{settings.PUBLIC_API_URL.rstrip('/')}/public/delivery/{rec.ack_token}", "agreed_at": rec.agreed_at}
