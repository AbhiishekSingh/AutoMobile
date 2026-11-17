"""CRE Walkin / LeadSquare worklists: every lead of the CRE's branches, split by source."""
from datetime import date, datetime, time, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.modules.cre_reports.service import other_condition
from app.modules.leads.models import EnquiryStage, Lead, LeadFollowup, LeadSource
from app.modules.quotations.models import Quotation
from app.modules.users.access import scope_leads
from app.modules.users.models import AppUser, Branch

router = APIRouter(prefix="/cre-worklist", tags=["cre-worklist"],
                   dependencies=[Depends(require_roles("CRE", "OWNER", "GM", "ADMIN"))])


@router.get("")
def worklist(source: str, search: Optional[str] = None, bucket: Optional[str] = None, opportunity_status_id: Optional[int] = None,
             branch_id: Optional[int] = None, limit: int = 300,
             user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    if source not in ("WALKIN", "CSV"):
        raise HTTPException(400, "source must be WALKIN or CSV")
    q = scope_leads(db.query(Lead), user, branch_id)
    q = q.filter(Lead.source == LeadSource[source])
    now = datetime.now()
    d0 = datetime.combine(date.today(), time.min)
    open_ = q.filter(Lead.enquiry_stage == EnquiryStage.OPEN, Lead.next_followup_at.isnot(None))
    cond = {"overdue": open_.filter(Lead.next_followup_at < now),
            "due_today": open_.filter(Lead.next_followup_at >= d0, Lead.next_followup_at < d0 + timedelta(days=1)),
            "pending": open_,   # open leads with a follow-up date (due later or overdue)
            "other": q.filter(other_condition(db))}
    summary = {"total": q.count(), "overdue": cond["overdue"].count(), "due_today": cond["due_today"].count(),
               "pending": cond["pending"].count(), "other": cond["other"].count()}
    if bucket in cond:
        q = cond[bucket]
    if opportunity_status_id:
        q = q.filter(Lead.opportunity_status_id == opportunity_status_id)
    if search and search.strip():
        s = f"%{search.strip()}%"
        from app.modules.leads.models import Customer
        q = q.join(Customer, Customer.customer_id == Lead.customer_id).filter(
            or_(Customer.full_name.ilike(s), Customer.phone.ilike(s), Lead.enquiry_no.ilike(s)))
    leads = q.order_by(Lead.lead_id.desc()).limit(min(limit, 500)).all()
    ids = [l.lead_id for l in leads]
    names = {u.user_id: u for u in db.query(AppUser).all()}
    bn = {b.branch_id: b.name for b in db.query(Branch).all()}
    pba_remark, price = {}, {}
    if ids:
        for f in db.query(LeadFollowup).filter(LeadFollowup.lead_id.in_(ids)).order_by(LeadFollowup.id.asc()).all():
            u = names.get(f.user_id)
            if u and u.role.value == "PBA" and f.remark:
                pba_remark[f.lead_id] = f.remark          # last one wins
        for qt in db.query(Quotation).filter(Quotation.lead_id.in_(ids)).order_by(Quotation.quotation_id.asc()).all():
            if qt.discounted_price is not None:
                price[qt.lead_id] = float(qt.discounted_price)
    out = []
    for l in leads:
        pba = names.get(l.assigned_user_id)
        out.append({"lead_id": l.lead_id, "enquiry_no": l.enquiry_no, "customer": l.customer.full_name, "mobile": l.customer.phone,
                    "branch": bn.get(l.branch_id), "model": l.model.name if l.model else None, "variant": l.sku_code, "colour": l.color,
                    "source": l.source.value, "pba": pba.full_name if pba else None, "pba_remark": pba_remark.get(l.lead_id),
                    "discounted_price": price.get(l.lead_id),
                    "opportunity": l.opportunity.name if l.opportunity else None, "stage": l.enquiry_stage.value,
                    "created_at": l.enquiry_at, "next_followup_at": l.next_followup_at})
    return {"rows": out, "summary": summary}
