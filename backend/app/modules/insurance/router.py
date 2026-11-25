"""Insurance team screens: dashboard, customer list, one case, and document uploads.

  GET  /insurance/dashboard              KPI cards
  GET  /insurance/cases                  customer listing (+ filters)
  GET  /insurance/cases/{lead_id}        one case: read-only PBA/customer details, documents, nominee, policy
  POST /insurance/cases/{lead_id}/documents   upload one required document (replaces an earlier one)
Policy type / nominee / policy PDF use the existing /leads/{id}/insurance endpoints (handoffs router).
"""
from datetime import date, datetime, time
from typing import Optional

from decimal import Decimal
from pydantic import BaseModel
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.modules.audit.service import record_changes
from app.modules.documents import service as docs
from app.modules.documents.models import CustomerDocument
from app.modules.handoffs import service as hsvc
from app.modules.handoffs.models import InsuranceCase, InsurancePolicyHistory, InvoiceDetail
from app.modules.insurance import service as svc
from app.modules.leads.models import Lead
from app.modules.payments import service as pay_svc
from app.modules.users.access import get_visible_lead, scope_leads
from app.modules.users.models import AppUser
from app.modules.whatsapp.models import WhatsappMessage

router = APIRouter(tags=["insurance"])
ROLES = ("INSURANCE", "ADMIN", "OWNER", "GM", "CRE")
WRITE = ("INSURANCE", "ADMIN")


def _pba(db, lead):
    return db.get(AppUser, lead.assigned_user_id) if lead.assigned_user_id else None


def _wa_state(db, lead_id):
    m = (db.query(WhatsappMessage).filter(WhatsappMessage.lead_id == lead_id, WhatsappMessage.kind == "INSURANCE",
         WhatsappMessage.recipient == "CUSTOMER").order_by(WhatsappMessage.id.desc()).first())
    return m.status if m else "NOT_SENT"


def _row(db, lead: Lead, case: InsuranceCase) -> dict:
    booking = pay_svc.get_booking(db, lead.lead_id)
    pba = _pba(db, lead)
    nominee_ok = not hsvc.check_nominee(case)
    return {
        "lead_id": lead.lead_id, "booking_no": booking.booking_no if booking else None,
        "customer_name": lead.customer.full_name, "mobile": lead.customer.phone,
        "model": lead.model.name if getattr(lead, "model", None) else None,
        "pba_name": pba.full_name if pba else None, "pba_id": lead.assigned_user_id,
        "branch": lead.branch.name if lead.branch else None,
        "booking_date": booking.created_at if booking else None,
        "policy_type": case.policy_type, "customer_type": case.customer_type,
        "policy_type_label": hsvc.policy_label(case),
        "document_status": svc.doc_status(db, lead, case),
        "nominee_status": "COMPLETE" if nominee_ok else "PENDING",
        "status": case.status, "policy_no": case.policy_no, "policy_status": case.policy_status or "ACTIVE",
        "pdf_uploaded": bool(case.pdf_stored_path),
        "pba_notified": bool(case.status == "COMPLETED" and lead.assigned_user_id),
        "whatsapp_status": _wa_state(db, lead.lead_id)}


def _cases(db, user):
    q = (scope_leads(db.query(Lead), user)
         .join(InsuranceCase, InsuranceCase.lead_id == Lead.lead_id).add_columns(InsuranceCase))
    return q


@router.get("/insurance/dashboard", dependencies=[Depends(require_roles(*ROLES))])
def dashboard(user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = [_row(db, l, c) for l, c in _cases(db, user).all()]
    n = lambda f: sum(1 for r in rows if f(r))
    return {"total": len(rows),
            "pending": n(lambda r: r["status"] == "PENDING"),
            "documents_pending": n(lambda r: r["status"] != "COMPLETED" and r["document_status"] != "COMPLETE"),
            "in_progress": n(lambda r: r["status"] == "IN_PROGRESS"),
            "completed": n(lambda r: r["status"] == "COMPLETED"),
            "pdf_not_uploaded": n(lambda r: not r["pdf_uploaded"]),
            "pba_notification_pending": n(lambda r: r["status"] == "COMPLETED" and not r["pba_notified"]),
            "whatsapp_failed": n(lambda r: r["whatsapp_status"] == "FAILED"),
            "cancelled": n(lambda r: r["policy_status"] == "CANCELLED")}


@router.get("/insurance/cases", dependencies=[Depends(require_roles(*ROLES))])
def cases(status: Optional[str] = None, policy_type: Optional[str] = None, customer_type: Optional[str] = None, pba_id: Optional[int] = None,
          document_status: Optional[str] = None, date_from: Optional[date] = None,
          date_to: Optional[date] = None, q: Optional[str] = None,
          user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    out = []
    for lead, case in _cases(db, user).all():
        r = _row(db, lead, case)
        if status and r["status"] != status: continue
        if policy_type and r["policy_type"] != policy_type: continue
        if customer_type and r["customer_type"] != customer_type: continue
        if pba_id and r["pba_id"] != pba_id: continue
        if document_status and r["document_status"] != document_status: continue
        bd = r["booking_date"]
        if date_from and (not bd or bd.date() < date_from): continue
        if date_to and (not bd or bd.date() > date_to): continue
        if q and q.lower() not in " ".join(str(r[k] or "") for k in ("customer_name", "mobile", "booking_no", "policy_no")).lower(): continue
        out.append(r)
    out.sort(key=lambda r: (r["status"] == "COMPLETED", r["booking_date"] or datetime.min), reverse=False)
    return out


@router.get("/insurance/pbas", dependencies=[Depends(require_roles(*ROLES))])
def pbas(user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    seen = {}
    for lead, _ in _cases(db, user).all():
        p = _pba(db, lead)
        if p: seen[p.user_id] = p.full_name
    return [{"user_id": k, "full_name": v} for k, v in sorted(seen.items(), key=lambda x: x[1])]


@router.get("/insurance/cases/{lead_id}", dependencies=[Depends(require_roles(*ROLES))])
def case_detail(lead_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    lead = get_visible_lead(db, user, lead_id)
    case = hsvc.get_case(db, InsuranceCase, lead_id)
    if not case:
        raise HTTPException(404, "No insurance file for this customer yet")
    r = _row(db, lead, case)
    pba = _pba(db, lead)
    inv = hsvc.get_case(db, InvoiceDetail, lead_id)
    r.update({
        "customer_id": lead.customer_id, "enquiry_no": lead.enquiry_no,
        "color": lead.color, "pba_employee_id": pba.login_id if pba else None,
        "documents": svc.checklist(db, lead, case),
        "nominee": {"name": case.nominee_name, "age": case.nominee_age, "relation": case.nominee_relation,
                    "relation_other": case.nominee_relation_other, "missing": hsvc.check_nominee(case)},
        "policy": {"company": hsvc.POLICY_TYPES.get(case.policy_type, (None, None))[1],
                   "policy_no": case.policy_no, "start": case.policy_start, "expiry": case.policy_expiry,
                   "premium": case.premium, "created_at": case.completed_at,
                   "executive": case.completed_by.full_name if case.completed_by else None,
                   "status": case.policy_status or "ACTIVE", "cancel_date": case.cancel_date, "cancel_remark": case.cancel_remark,
                   "refund_amount": case.refund_amount, "refund_expected_date": case.refund_expected_date,
                   "cancelled_at": case.cancelled_at, "cancelled_by": case.cancelled_by.full_name if case.cancelled_by else None},
        "previous_policies": [
            {"id": h.id, "company": hsvc.POLICY_TYPES.get(h.policy_type, (None, h.policy_type))[1], "policy_no": h.policy_no,
             "start": h.policy_start, "expiry": h.policy_expiry, "premium": h.premium, "has_pdf": bool(h.pdf_stored_path),
             "cancel_date": h.cancel_date, "cancel_remark": h.cancel_remark, "refund_amount": h.refund_amount,
             "refund_expected_date": h.refund_expected_date,
             "cancelled_by": h.cancelled_by.full_name if h.cancelled_by else None, "cancelled_at": h.cancelled_at}
            for h in db.query(InsurancePolicyHistory).filter(InsurancePolicyHistory.lead_id == lead_id)
                       .order_by(InsurancePolicyHistory.id.desc()).all()],
        "can_add_new_policy": user.role.value in WRITE and case.status == "COMPLETED" and (case.policy_status or "ACTIVE") == "CANCELLED",
        "addons": [hsvc.ADDONS[k] for k in (case.addons or (inv.insurance_addon if inv else "") or "").split(",") if k in hsvc.ADDONS],
        "docs_verified": {"at": case.docs_verified_at, "by": case.docs_verified_by.full_name if case.docs_verified_by else None},
        "can_edit_details": user.role.value in ("ADMIN", "CRE") and case.status != "COMPLETED",   # policy type + nominee are the PBA's; Insurance only views
        "can_edit": user.role.value in ("INSURANCE", "ADMIN", "CRE") and case.status != "COMPLETED",
        "can_send_whatsapp": user.role.value in ("INSURANCE", "ADMIN", "CRE") and case.status == "COMPLETED" and bool(case.pdf_stored_path)
                             and (case.policy_status or "ACTIVE") == "ACTIVE",
        "can_cancel_policy": user.role.value in WRITE and case.status == "COMPLETED",
        "options": {"policy_types": hsvc.policy_type_options(),
                    "customer_types": [{"value": k, "label": v} for k, v in hsvc.CUSTOMER_TYPES.items()],
                    "nominee_relations": hsvc.NOMINEE_RELATIONS}})
    return r


@router.post("/insurance/cases/{lead_id}/documents", dependencies=[Depends(require_roles(*WRITE))])
def upload_doc(lead_id: int, doc_type: str = Form(...), file: UploadFile = File(...),
               user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    lead = get_visible_lead(db, user, lead_id)
    case = hsvc.get_case(db, InsuranceCase, lead_id)
    if not case:
        raise HTTPException(404, "No insurance file for this customer yet")
    if case.status == "COMPLETED":
        raise HTTPException(400, "The insurance is completed and can no longer be edited")
    svc.check_upload(case, doc_type, file.filename)
    saved = docs.save_upload(file, lead.customer_id)
    try:
        for old in db.query(CustomerDocument).filter(CustomerDocument.lead_id == lead_id,
                                                     CustomerDocument.doc_type == doc_type).all():
            docs.delete_file(old.stored_path); db.delete(old)
        db.add(CustomerDocument(lead_id=lead_id, customer_id=lead.customer_id, doc_type=doc_type,
                                note="Insurance", uploaded_by_user_id=user.user_id, **saved))
        case.docs_verified_at = case.docs_verified_by_user_id = None      # a new file needs verifying again
        if case.status == "PENDING":
            case.status = "IN_PROGRESS"
        case.updated_by_user_id = user.user_id
        db.commit()
    except Exception:
        db.rollback(); docs.delete_file(saved["stored_path"]); raise
    return {"ok": True}


@router.post("/insurance/cases/{lead_id}/verify-documents", dependencies=[Depends(require_roles(*WRITE))])
def verify_documents(lead_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """Workflow step: documents uploaded + nominee entered -> documents verified (then the policy can be created)."""
    from app.core.database import now_ist
    lead = get_visible_lead(db, user, lead_id)
    case = hsvc.get_case(db, InsuranceCase, lead_id)
    if not case:
        raise HTTPException(404, "No insurance file for this customer yet")
    if case.status == "COMPLETED":
        raise HTTPException(400, "The insurance is already completed")
    if case.policy_type not in svc.REQUIRED_DOCS:
        raise HTTPException(400, "Select the insurance policy type first")
    gap = svc.missing_documents(db, lead, case)
    if gap:
        raise HTTPException(400, "Upload the required documents first: " + ", ".join(gap))
    miss = hsvc.check_nominee(case)
    if miss:
        raise HTTPException(400, "Enter the nominee details first: " + ", ".join(miss))
    case.docs_verified_at, case.docs_verified_by_user_id, case.updated_by_user_id = now_ist(), user.user_id, user.user_id
    if case.status == "PENDING":
        case.status = "IN_PROGRESS"
    record_changes(db, entity_type="insurance", entity_id=case.id, before={"docs_verified_at": None}, after=case,
                   fields=("docs_verified_at",), changed_by_user_id=user.user_id)
    db.commit()
    return {"ok": True}


# ---------- cancel / reactivate a completed policy ----------
class CancelPolicy(BaseModel):
    cancel_date: date
    remark: str
    refund_amount: Optional[Decimal] = None
    refund_expected_date: Optional[date] = None


class ReactivatePolicy(BaseModel):
    remark: str


def _completed_case(db, user, lead_id):
    get_visible_lead(db, user, lead_id)
    case = hsvc.get_case(db, InsuranceCase, lead_id)
    if not case:
        raise HTTPException(404, "No insurance file for this customer yet")
    if case.status != "COMPLETED":
        raise HTTPException(400, "Only a completed policy can be cancelled")
    return case


@router.post("/insurance/cases/{lead_id}/cancel-policy", dependencies=[Depends(require_roles(*WRITE))])
def cancel_policy(lead_id: int, body: CancelPolicy, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.core.database import now_ist
    case = _completed_case(db, user, lead_id)
    if (case.policy_status or "ACTIVE") == "CANCELLED":
        raise HTTPException(400, "This policy is already cancelled")
    if not body.remark.strip():
        raise HTTPException(400, "Enter the reason for the cancellation")
    if body.cancel_date > now_ist().date():
        raise HTTPException(400, "The cancellation date cannot be in the future")
    # a policy can be cancelled before its cover starts (start date in the future), so the limit is the day it was created
    if case.completed_at and body.cancel_date < case.completed_at.date():
        raise HTTPException(400, f"The cancellation date cannot be before the policy was created ({case.completed_at:%d-%m-%Y})")
    if body.refund_amount is not None:
        if body.refund_amount < 0:
            raise HTTPException(400, "The refund amount cannot be negative")
        if case.premium is not None and body.refund_amount > case.premium:
            raise HTTPException(400, "The refund cannot be more than the premium paid")
    if body.refund_expected_date and body.refund_expected_date < body.cancel_date:
        raise HTTPException(400, "The expected refund date cannot be before the cancellation date")
    fields = ("policy_status", "cancel_date", "cancel_remark", "refund_amount", "refund_expected_date")
    before = {f: getattr(case, f) for f in fields}
    case.policy_status, case.cancel_date, case.cancel_remark = "CANCELLED", body.cancel_date, body.remark.strip()
    case.refund_amount, case.refund_expected_date = body.refund_amount, body.refund_expected_date
    case.cancelled_at, case.cancelled_by_user_id, case.updated_by_user_id = now_ist(), user.user_id, user.user_id
    record_changes(db, entity_type="insurance", entity_id=case.id, before=before, after=case, fields=fields, changed_by_user_id=user.user_id)
    db.commit()
    return {"ok": True}


@router.post("/insurance/cases/{lead_id}/reactivate-policy", dependencies=[Depends(require_roles(*WRITE))])
def reactivate_policy(lead_id: int, body: ReactivatePolicy, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    case = _completed_case(db, user, lead_id)
    if (case.policy_status or "ACTIVE") != "CANCELLED":
        raise HTTPException(400, "This policy is not cancelled")
    if not body.remark.strip():
        raise HTTPException(400, "Enter the reason for making the policy active again")
    fields = ("policy_status", "cancel_date", "cancel_remark", "refund_amount", "refund_expected_date")
    before = {f: getattr(case, f) for f in fields}
    before["cancel_remark"] = f"{before['cancel_remark']} [reactivated: {body.remark.strip()}]"
    case.policy_status, case.cancel_date, case.cancel_remark, case.refund_amount, case.refund_expected_date = "ACTIVE", None, None, None, None
    case.cancelled_at, case.cancelled_by_user_id, case.updated_by_user_id = None, None, user.user_id
    record_changes(db, entity_type="insurance", entity_id=case.id, before=before, after=case, fields=fields, changed_by_user_id=user.user_id)
    db.commit()
    return {"ok": True}


@router.post("/insurance/cases/{lead_id}/new-policy", dependencies=[Depends(require_roles(*WRITE))])
def add_new_policy(lead_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """After a policy was cancelled (rejected by the insurer, customer changed company...): move the cancelled policy to the
    history with its refund details and open the Policy & PDF step again so a new policy can be entered. The documents,
    nominee and verification stay; only the policy itself is replaced."""
    from app.core.database import now_ist
    case = _completed_case(db, user, lead_id)
    if (case.policy_status or "ACTIVE") != "CANCELLED":
        raise HTTPException(400, "Cancel the current policy first")
    db.add(InsurancePolicyHistory(
        lead_id=lead_id, case_id=case.id, customer_type=case.customer_type, policy_type=case.policy_type,
        policy_no=case.policy_no, policy_start=case.policy_start, policy_expiry=case.policy_expiry, premium=case.premium,
        pdf_original_name=case.pdf_original_name, pdf_stored_path=case.pdf_stored_path,
        completed_at=case.completed_at, completed_by_user_id=case.completed_by_user_id,
        cancel_date=case.cancel_date, cancel_remark=case.cancel_remark, refund_amount=case.refund_amount,
        refund_expected_date=case.refund_expected_date, cancelled_at=case.cancelled_at,
        cancelled_by_user_id=case.cancelled_by_user_id, replaced_by_user_id=user.user_id))
    fields = ("status", "policy_no", "policy_status")
    before = {f: getattr(case, f) for f in fields}
    case.policy_no = case.policy_start = case.policy_expiry = case.premium = None
    case.pdf_original_name = case.pdf_stored_path = case.pdf_size_bytes = None
    case.completed_at = case.completed_by_user_id = None
    case.policy_status, case.cancel_date, case.cancel_remark, case.refund_amount, case.refund_expected_date = "ACTIVE", None, None, None, None
    case.cancelled_at = case.cancelled_by_user_id = None
    case.status, case.updated_by_user_id = "IN_PROGRESS", user.user_id
    record_changes(db, entity_type="insurance", entity_id=case.id, before=before, after=case, fields=fields, changed_by_user_id=user.user_id)
    db.commit()
    return {"ok": True}


@router.get("/insurance/cases/{lead_id}/previous-policies/{history_id}/pdf")
def previous_policy_pdf(lead_id: int, history_id: int, download: bool = False,
                        user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    from fastapi.responses import FileResponse
    get_visible_lead(db, user, lead_id)
    h = db.get(InsurancePolicyHistory, history_id)
    if not h or h.lead_id != lead_id or not h.pdf_stored_path:
        raise HTTPException(404, "No PDF for this policy")
    return FileResponse(docs.full_path_of(h.pdf_stored_path), media_type="application/pdf", filename=h.pdf_original_name,
                        content_disposition_type="attachment" if download else "inline")
