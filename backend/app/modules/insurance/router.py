"""Insurance team screens: dashboard, customer list, one case, and document uploads.

  GET  /insurance/dashboard              KPI cards
  GET  /insurance/cases                  customer listing (+ filters)
  GET  /insurance/cases/{lead_id}        one case: read-only PBA/customer details, documents, nominee, policy
  POST /insurance/cases/{lead_id}/documents   upload one required document (replaces an earlier one)
Policy type / nominee / policy PDF use the existing /leads/{id}/insurance endpoints (handoffs router).
"""
from datetime import date, datetime, time
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.modules.audit.service import record_changes
from app.modules.documents import service as docs
from app.modules.documents.models import CustomerDocument
from app.modules.handoffs import service as hsvc
from app.modules.handoffs.models import InsuranceCase
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
        "policy_type": case.policy_type,
        "policy_type_label": hsvc.POLICY_TYPES.get(case.policy_type, (None,))[0],
        "document_status": svc.doc_status(db, lead, case),
        "nominee_status": "COMPLETE" if nominee_ok else "PENDING",
        "status": case.status, "policy_no": case.policy_no,
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
            "whatsapp_failed": n(lambda r: r["whatsapp_status"] == "FAILED")}


@router.get("/insurance/cases", dependencies=[Depends(require_roles(*ROLES))])
def cases(status: Optional[str] = None, policy_type: Optional[str] = None, pba_id: Optional[int] = None,
          document_status: Optional[str] = None, date_from: Optional[date] = None,
          date_to: Optional[date] = None, q: Optional[str] = None,
          user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    out = []
    for lead, case in _cases(db, user).all():
        r = _row(db, lead, case)
        if status and r["status"] != status: continue
        if policy_type and r["policy_type"] != policy_type: continue
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
    r.update({
        "customer_id": lead.customer_id, "enquiry_no": lead.enquiry_no,
        "color": lead.color, "pba_employee_id": pba.login_id if pba else None,
        "documents": svc.checklist(db, lead, case),
        "nominee": {"name": case.nominee_name, "age": case.nominee_age, "relation": case.nominee_relation,
                    "relation_other": case.nominee_relation_other, "missing": hsvc.check_nominee(case)},
        "policy": {"company": hsvc.POLICY_TYPES.get(case.policy_type, (None, None))[1],
                   "policy_no": case.policy_no, "start": case.policy_start, "expiry": case.policy_expiry,
                   "premium": case.premium, "created_at": case.completed_at,
                   "executive": case.completed_by.full_name if case.completed_by else None},
        "can_edit": user.role.value in ("INSURANCE", "ADMIN", "CRE") and case.status != "COMPLETED",
        "can_send_whatsapp": user.role.value in ("INSURANCE", "ADMIN", "CRE") and case.status == "COMPLETED" and bool(case.pdf_stored_path),
        "options": {"policy_types": [{"value": k, "label": v[0]} for k, v in hsvc.POLICY_TYPES.items()],
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
        if case.status == "PENDING":
            case.status = "IN_PROGRESS"
        case.updated_by_user_id = user.user_id
        db.commit()
    except Exception:
        db.rollback(); docs.delete_file(saved["stored_path"]); raise
    return {"ok": True}
