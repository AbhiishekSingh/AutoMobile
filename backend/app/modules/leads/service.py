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
    """Visibility rule for a PBA's Leads/Pipeline/Follow-ups/Customers screens.

    A PBA sees:
      - leads specifically assigned to THEM (assigned_user_id == their id),
        regardless of branch — so a lead they own is never hidden from them, and
      - unassigned leads in their own branch, so there's still a pool of
        unclaimed leads to pick up.

    A PBA does NOT see another PBA's assigned leads just because it's the same
    branch — previously this filtered on branch alone, so every PBA in a branch
    saw every lead in that branch no matter who (if anyone) it was assigned to.
    That meant "assignment" and "visibility" were two unrelated things; this
    keeps them in sync. Owner/GM/Admin are unaffected — they still see everything.
    """
    if user.role == Role.PBA and user.branch_id:
        query = query.filter(
            (Lead.assigned_user_id == user.user_id) |
            ((Lead.assigned_user_id.is_(None)) & (Lead.branch_id == user.branch_id))
        )
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
