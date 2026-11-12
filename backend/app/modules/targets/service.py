"""Targets vs achievement. Achievement = bookings made in the period (cancelled ones excluded),
credited to the PBA the lead is assigned to, under the booked bike model."""
from datetime import date, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.leads.models import BikeModel, Lead
from app.modules.leads.stages import sold_condition
from app.modules.payments.models import Booking
from app.modules.targets.models import SalesTarget
from app.modules.users.models import AppUser, Role


def month_start(d) -> date:
    return date(d.year, d.month, 1)


def next_month(m: date) -> date:
    return date(m.year + 1, 1, 1) if m.month == 12 else date(m.year, m.month + 1, 1)


def pba_ids(db: Session, user, branch_id=None):
    """PBA user ids whose numbers `user` may see (None = no restriction)."""
    if user.role == Role.PBA:
        return [user.user_id]
    q = db.query(AppUser.user_id).filter(AppUser.role == Role.PBA, AppUser.is_active == True)  # noqa: E712
    ids = None
    if user.role == Role.CRE:
        ids = user.branch_ids or [-1]
    if branch_id:
        ids = [branch_id]
    if ids is not None:
        q = q.filter(AppUser.branch_id.in_(ids))
    elif user.role.value in ("OWNER", "GM", "ADMIN"):
        return None
    return [r[0] for r in q.all()]


def achieved(db: Session, start: datetime, end: datetime, user_ids=None):
    """{(user_id, model_id): bookings} for bookings created in [start, end)."""
    q = (db.query(Lead.assigned_user_id, Lead.model_id, func.count(Booking.booking_id))
         .join(Lead, Lead.lead_id == Booking.lead_id)
         .filter(Booking.created_at >= start, Booking.created_at < end, sold_condition(db)))
    if user_ids is not None:
        q = q.filter(Lead.assigned_user_id.in_(user_ids or [-1]))
    return {(u, m): c for u, m, c in q.group_by(Lead.assigned_user_id, Lead.model_id).all()}


def period_targets(db: Session, user, branch_id, period: str, start: datetime, end: datetime):
    """{model_name: target qty} for a dashboard period, or None when no targets are set
    (or the period is a day/week, which a monthly target does not cover)."""
    if period not in ("month", "year"):
        return None
    ids = pba_ids(db, user, branch_id)
    q = (db.query(BikeModel.name, func.sum(SalesTarget.qty))
         .join(SalesTarget, SalesTarget.model_id == BikeModel.id)
         .filter(SalesTarget.month >= start.date(), SalesTarget.month < end.date()))
    if ids is not None:
        q = q.filter(SalesTarget.user_id.in_(ids or [-1]))
    rows = {n: int(s) for n, s in q.group_by(BikeModel.name).all() if s}
    return rows or None


def booked_by_model(db: Session, user, branch_id, start, end):
    ids = pba_ids(db, user, branch_id)
    out = {}
    names = {m.id: m.name for m in db.query(BikeModel).all()}
    for (u, m), c in achieved(db, start, end, ids).items():
        out[names.get(m, "Unknown")] = out.get(names.get(m, "Unknown"), 0) + c
    return out
