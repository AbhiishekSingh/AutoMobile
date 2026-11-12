"""CRE final review & customer closure.

  GET  /final-reviews                 the CRE's task list (delivered customers waiting) + recently closed
  GET  /leads/{id}/final-review       one customer's review (or the blank form)
  POST /leads/{id}/final-review       save it; status COMPLETED closes the customer (stage CLOSED, time stored)
A delivered customer is never closed by anyone or anything else (the stage engine refuses a manual DELIVERED -> CLOSED).
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db, now_ist
from app.core.deps import get_current_user, require_roles
from app.modules.audit.service import record_changes
from app.modules.final_review.models import FinalReview
from app.modules.leads.models import EnquiryStage as S, Lead
from app.modules.leads.stages import change_stage
from app.modules.users.access import get_visible_lead, scope_leads
from app.modules.users.models import AppUser

router = APIRouter(tags=["final-review"])
VIEW = ("CRE", "OWNER", "GM", "ADMIN", "PBA")
STATUSES = {"COMPLETED": "Completed — close the customer", "CALLBACK_NEEDED": "Call back later", "NOT_REACHABLE": "Customer not reachable"}
RATING = {1: "Very dissatisfied", 2: "Dissatisfied", 3: "Neutral", 4: "Satisfied", 5: "Very satisfied"}


class ReviewIn(BaseModel):
    review_date: Optional[date] = None
    customer_feedback: str = ""
    product_satisfaction: Optional[int] = None
    customer_experience: Optional[int] = None
    cre_remarks: str = ""
    status: str


def _dict(r: Optional[FinalReview]):
    if not r:
        return None
    return {"review_date": r.review_date, "customer_feedback": r.customer_feedback, "product_satisfaction": r.product_satisfaction,
            "customer_experience": r.customer_experience, "cre_remarks": r.cre_remarks, "status": r.status, "attempts": r.attempts,
            "reviewed_by": r.reviewed_by.full_name if r.reviewed_by else None, "closed_at": r.closed_at, "updated_at": r.updated_at}


def _delivered_leads(db, user):
    return scope_leads(db.query(Lead), user).filter(Lead.enquiry_stage == S.DELIVERED)


@router.get("/final-reviews", dependencies=[Depends(require_roles(*VIEW))])
def tasks(user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role.value == "PBA":
        raise HTTPException(403, "Insufficient permissions")
    revs = {r.lead_id: r for r in db.query(FinalReview).all()}
    due = []
    for l in _delivered_leads(db, user).order_by(Lead.updated_at.asc()).all():
        r = revs.get(l.lead_id)
        due.append({"lead_id": l.lead_id, "enquiry_no": l.enquiry_no, "customer": l.customer.full_name, "mobile": l.customer.phone,
                    "model": l.model.name if l.model else None, "branch": l.branch.name if l.branch else None,
                    "last_status": r.status if r else None, "attempts": r.attempts if r else 0, "delivered_since": l.updated_at})
    closed = []
    q = (db.query(FinalReview, Lead).join(Lead, Lead.lead_id == FinalReview.lead_id).filter(FinalReview.status == "COMPLETED"))
    q = scope_leads(q, user)
    for r, l in q.order_by(FinalReview.closed_at.desc()).limit(50).all():
        closed.append({"lead_id": l.lead_id, "customer": l.customer.full_name, "closed_at": r.closed_at, "reviewed_by": r.reviewed_by.full_name if r.reviewed_by else None,
                       "product_satisfaction": r.product_satisfaction, "customer_experience": r.customer_experience})
    return {"due": due, "closed": closed}


@router.get("/leads/{lead_id}/final-review", dependencies=[Depends(require_roles(*VIEW))])
def get_review(lead_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    lead = get_visible_lead(db, user, lead_id)
    r = db.query(FinalReview).filter(FinalReview.lead_id == lead_id).first()
    open_ = lead.enquiry_stage == S.DELIVERED
    return {"stage": lead.enquiry_stage.value, "review": _dict(r), "can_review": open_ and user.role.value in ("CRE", "ADMIN"),
            "show": open_ or bool(r), "statuses": [{"value": k, "label": v} for k, v in STATUSES.items()],
            "ratings": [{"value": k, "label": v} for k, v in RATING.items()]}


@router.post("/leads/{lead_id}/final-review", dependencies=[Depends(require_roles("CRE", "ADMIN"))])
def save_review(lead_id: int, body: ReviewIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    lead = get_visible_lead(db, user, lead_id)
    if lead.enquiry_stage != S.DELIVERED:
        raise HTTPException(400, "A final review can only be done for a delivered customer" +
                            (" (this customer is already closed)" if lead.enquiry_stage == S.CLOSED else ""))
    if body.status not in STATUSES:
        raise HTTPException(400, "Choose the final review status")
    d = body.review_date or date.today()
    if d > date.today():
        raise HTTPException(400, "Review date cannot be in the future")
    missing = []
    if not body.customer_feedback.strip(): missing.append("Customer feedback")
    if body.product_satisfaction not in RATING: missing.append("Product satisfaction")
    if body.customer_experience not in RATING: missing.append("Customer experience")
    if not body.cre_remarks.strip(): missing.append("CRE final remarks")
    if missing:
        raise HTTPException(400, "Please fill: " + ", ".join(missing))
    r = db.query(FinalReview).filter(FinalReview.lead_id == lead_id).first()
    before = {"status": r.status if r else None}
    if not r:
        r = FinalReview(lead_id=lead_id, attempts=0); db.add(r)
    r.review_date, r.customer_feedback, r.cre_remarks = d, body.customer_feedback.strip(), body.cre_remarks.strip()
    r.product_satisfaction, r.customer_experience, r.status = body.product_satisfaction, body.customer_experience, body.status
    r.attempts = (r.attempts or 0) + 1
    r.reviewed_by_user_id = user.user_id
    db.flush()
    record_changes(db, entity_type="final_review", entity_id=lead_id, before=before, after=r, fields=("status",), changed_by_user_id=user.user_id)
    if body.status == "COMPLETED":
        r.closed_at = now_ist()
        change_stage(db, lead, S.CLOSED, actor_user_id=user.user_id, reason="CRE final review completed")
    db.commit()
    return {"ok": True, "closed": body.status == "COMPLETED"}
