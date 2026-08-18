"""Reusable helpers for the leads module (kept out of the router)."""
from sqlalchemy.orm import Session

from app.modules.leads.models import (Disposition, Lead, LeadType, LostReason,
                                      OpportunityStatus, SLAFlag, TestRide,
                                      TestRideStatus)
from app.modules.users.models import AppUser, Role


def mask_phone(phone: str) -> str:
    p = "".join(ch for ch in (phone or "") if ch.isdigit())
    if len(p) < 4:
        return phone or ""
    return f"{p[:2]}{'X' * (len(p) - 4)}{p[-2:]}"


def scope(query, user: AppUser):
    """PBA sees only their branch; Owner/GM/Admin see all."""
    if user.role == Role.PBA and user.branch_id:
        query = query.filter(Lead.branch_id == user.branch_id)
    return query


def bucket_filter(query, bucket: str, db: Session):
    if bucket in (None, "", "all"):
        return query
    if bucket == "completed":
        return query.filter(Lead.sla_flag == SLAFlag.GREEN)
    if bucket == "pending":
        return query.filter(Lead.sla_flag == SLAFlag.YELLOW)
    if bucket == "overdue":
        return query.filter(Lead.sla_flag == SLAFlag.RED)
    if bucket == "calllater":
        d = db.query(Disposition).filter(Disposition.name == "CALL LATER").first()
        return query.filter(Lead.current_disposition_id == (d.id if d else -1))
    if bucket == "testride":
        sub = db.query(TestRide.lead_id).filter(TestRide.status == TestRideStatus.COMPLETED)
        return query.filter(Lead.lead_id.in_(sub))
    if bucket == "service":
        return query.filter(Lead.lead_type == LeadType.SERVICE)
    if bucket == "closed":
        return query.filter(Lead.enquiry_stage == "CLOSED")
    if bucket == "future":
        o = db.query(OpportunityStatus).filter(OpportunityStatus.name == "FUTURE LEAD").first()
        return query.filter(Lead.opportunity_status_id == (o.id if o else -1))
    if bucket == "casual":
        r = db.query(LostReason).filter(LostReason.name.ilike("%casual%")).first()
        return query.filter(Lead.lost_reason_id == (r.id if r else -1))
    return query
