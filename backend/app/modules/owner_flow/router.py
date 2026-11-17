"""Owner Portal workflow endpoints.

  GET  /leads/{id}/owner-flow                    full detail + every stage's status (Owner, GM, PBA, CRE, Admin)
  POST /leads/{id}/owner-flow/initial/decision   Owner: approve (price + processing + ATW) / reject (remark)
  POST /leads/{id}/owner-flow/final/decision     Owner: approve / reject (remark)
  POST /leads/{id}/owner-flow/{initial|final}/resubmit   PBA: send a rejected request again
  GET  /owner-flow/board                         one row per booked lead with its current status
"""
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.modules.audit.service import record_changes
from app.modules.handoffs.models import RtoCase
from app.modules.leads.models import Lead
from app.modules.owner_flow import service as svc
from app.modules.owner_flow.models import OwnerStageApproval
from app.modules.payments.models import Booking
from app.modules.users.access import MANAGER_ROLES, SALES_ROLES, get_visible_lead, scope_leads
from app.modules.users.models import AppUser

router = APIRouter(tags=["owner-flow"])
VIEW = SALES_ROLES + MANAGER_ROLES
FIELDS = ("status", "discounted_price", "customer_processing", "atw_allowed", "remark")


class InitialDecision(BaseModel):
    approve: bool
    discounted_price: Optional[Decimal] = None
    customer_processing: Optional[bool] = None
    atw_allowed: Optional[bool] = None
    remark: Optional[str] = None


class FinalDecision(BaseModel):
    approve: bool
    remark: Optional[str] = None


def _snap(row): return {f: getattr(row, f) for f in FIELDS}


@router.get("/leads/{lead_id}/owner-flow", dependencies=[Depends(require_roles(*VIEW))])
def get_flow(lead_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    lead = get_visible_lead(db, user, lead_id)
    from app.modules.handoffs.service import ensure_insurance_case, is_booking_done
    if is_booking_done(lead) and ensure_insurance_case(db, lead):     # BOOKING DONE leads always have the request
        db.commit()
    return svc.detail(db, lead)


@router.post("/leads/{lead_id}/owner-flow/initial/decision", dependencies=[Depends(require_roles("OWNER"))])
def initial_decision(lead_id: int, body: InitialDecision, user: AppUser = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    lead = db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    row = svc.get_stage(db, lead_id, "INITIAL")
    before = _snap(row) if row else {f: None for f in FIELDS}
    row = svc.decide_initial(db, lead, approve=body.approve, discounted_price=body.discounted_price,
                             customer_processing=body.customer_processing, atw_allowed=body.atw_allowed,
                             remark=body.remark, user=user)
    record_changes(db, entity_type="owner_initial", entity_id=row.id, before=before, after=row,
                   fields=FIELDS, changed_by_user_id=user.user_id)
    db.commit()
    return svc.detail(db, lead)


@router.post("/leads/{lead_id}/owner-flow/final/decision", dependencies=[Depends(require_roles("OWNER"))])
def final_decision(lead_id: int, body: FinalDecision, user: AppUser = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    lead = db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    row = svc.get_stage(db, lead_id, "FINAL")
    before = _snap(row) if row else {f: None for f in FIELDS}
    row = svc.decide_final(db, lead, approve=body.approve, remark=body.remark, user=user)
    record_changes(db, entity_type="owner_final", entity_id=row.id, before=before, after=row,
                   fields=("status", "remark"), changed_by_user_id=user.user_id)
    db.commit()
    return svc.detail(db, lead)


@router.post("/leads/{lead_id}/owner-flow/{stage}/resubmit", dependencies=[Depends(require_roles("PBA"))])
def resubmit(lead_id: int, stage: str, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    if stage not in ("initial", "final"):
        raise HTTPException(404, "Unknown stage")
    lead = get_visible_lead(db, user, lead_id)
    row = svc.resubmit(db, lead, stage.upper(), user)
    record_changes(db, entity_type="owner_" + stage, entity_id=row.id, before={"status": "REJECTED"}, after=row,
                   fields=("status",), changed_by_user_id=user.user_id)
    db.commit()
    return svc.detail(db, lead)


@router.get("/leads/{lead_id}/journey", dependencies=[Depends(require_roles(*VIEW, "RTO", "INSURANCE"))])
def get_journey(lead_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """The customer journey, readable by every department (names and statuses only)."""
    if user.role.value in ("PBA", "CRE"):
        lead = get_visible_lead(db, user, lead_id)
    else:
        lead = db.get(Lead, lead_id)
        if not lead:
            raise HTTPException(404, "Lead not found")
    return svc.journey(db, lead, money=user.role.value not in ("RTO", "INSURANCE"))


@router.get("/owner-flow/approvals", dependencies=[Depends(require_roles("OWNER", "GM", "ADMIN"))])
def approvals(stage: str = "ALL", status: str = "PENDING", page: int = 1, page_size: int = 20,
              db: Session = Depends(get_db)):
    if stage not in ("ALL", "INITIAL", "FINAL"):
        raise HTTPException(400, "Unknown stage")
    return svc.approval_cards(db, stage, status.upper(), max(page, 1), min(max(page_size, 1), 50))


@router.get("/owner-flow/board", dependencies=[Depends(require_roles(*VIEW))])
def board(status: Optional[str] = None, page: int = 1, page_size: int = 25,
          user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """Booked leads in the user's scope. Filtering and paging happen in SQL; the status of each row
    is worked out only for the 25 rows on screen, so it stays fast with a very large lead table."""
    from sqlalchemy import and_, exists, or_
    from app.modules.handoffs.models import InsuranceCase as IC
    def has(stage, *st):
        c = [OwnerStageApproval.lead_id == Lead.lead_id, OwnerStageApproval.stage == stage]
        if st:
            c.append(OwnerStageApproval.status.in_(st))
        return exists().where(and_(*c))
    ins_open = exists().where(and_(IC.lead_id == Lead.lead_id, IC.status != "COMPLETED"))
    ins_any = exists().where(IC.lead_id == Lead.lead_id)
    rto_open = exists().where(and_(RtoCase.lead_id == Lead.lead_id, RtoCase.status != "REGISTERED"))
    flt = {"AWAITING_INITIAL_APPROVAL": has("INITIAL", "PENDING"),
           "INITIAL_REJECTED": or_(has("INITIAL", "REJECTED"), has("FINAL", "REJECTED")),
           "AWAITING_PBA": and_(has("INITIAL", "APPROVED"), ~ins_any),
           "AT_INSURANCE": ins_open, "AWAITING_FINAL_APPROVAL": has("FINAL", "PENDING"), "AT_RTO": rto_open}
    q = scope_leads(db.query(Lead), user).join(Booking, Booking.lead_id == Lead.lead_id)
    if status in flt:
        q = q.filter(flt[status])
    page, page_size = max(page, 1), min(max(page_size, 1), 50)
    total = q.count()
    out = []
    for lead in q.order_by(Lead.lead_id.desc()).offset((page - 1) * page_size).limit(page_size).all():
        d = svc.detail(db, lead)
        out.append({"lead_id": lead.lead_id, "enquiry_no": lead.enquiry_no, "customer_name": d["customer_name"],
                    "branch": d["branch"], "pba": d["pba"], "model": d["model"], "bike_price": d["bike_price"],
                    "discounted_price": d["discounted_price"], **d["workflow"]})
    return {"total": total, "page": page, "page_size": page_size, "rows": out}
