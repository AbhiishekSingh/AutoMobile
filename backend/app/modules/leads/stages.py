"""STAGE ENGINE — the one place a lead's Enquiry Stage is allowed to change.

Why this exists: the stage used to be a dropdown a PBA could set by hand, so a
lead could show BOOKED with no payment behind it. Now the stage only moves
when a real event happens (payment saved, insurance done, RTO done, invoice
uploaded, delivery confirmed), and every move goes through `change_stage()`
below, which refuses invalid jumps.

Rules for the rest of the code:
  - Never write `lead.enquiry_stage = ...` anywhere else. Call change_stage().
  - The OPEN <-> CLOSED choice (closing / reopening a lead) is the only thing
    a PBA/CRE may still do by hand — see MANUAL_STAGES.
  - Stages from BOOKED onward are set by system events only (named helpers at
    the bottom, e.g. mark_booked).

Stage order after BOOKED is still PENDING CLIENT CONFIRMATION (whether the
invoice comes before or after insurance / RTO). To change the order, edit
ALLOWED_NEXT below — nothing else needs to change.

Every real change also (a) adds a row to lead_stage_history and (b) raises one
in-app alert each for the lead's PBA, the CRE(s) covering its branch, the GM(s)
and the Owner(s) — nobody is alerted about a change they made themselves.
"""
from fastapi import HTTPException
from sqlalchemy import or_

from app.modules.leads.models import EnquiryStage as S, Lead, StageHistory
from app.modules.notifications.models import NotificationType
from app.modules.notifications.service import create_notification
from app.modules.users.models import AppUser, Role, UserBranch

# ---- the allowed moves (edit here if the client changes the order) ----------
ALLOWED_NEXT: dict[S, set[S]] = {
    S.OPEN:           {S.BOOKED, S.CLOSED},
    S.BOOKED:         {S.INSURANCE_DONE, S.CLOSED},        # CLOSED = booking cancelled
    S.INSURANCE_DONE: {S.RTO_DONE, S.CLOSED},
    S.RTO_DONE:       {S.INVOICED, S.CLOSED},
    S.INVOICED:       {S.DELIVERED, S.CLOSED},
    S.DELIVERED:      {S.CLOSED},                          # CRE final review closes it
    S.CLOSED:         {S.OPEN},                            # a closed lead can be reopened
}

# Stages a customer has "bought" at (booking made or beyond, closed ones excluded).
BOUGHT_STAGES = (S.BOOKED, S.INSURANCE_DONE, S.RTO_DONE, S.INVOICED, S.DELIVERED)

# Stages where a booking exists but the bike has not been handed over yet.
OPEN_BOOKING_STAGES = (S.BOOKED, S.INSURANCE_DONE, S.RTO_DONE, S.INVOICED)
# A booking cancelled from one of these ends as CLOSED. (DELIVERED -> CLOSED is
# not a cancellation: it is the CRE's final review closing a finished sale.)
CANCELLABLE_STAGES = OPEN_BOOKING_STAGES

# The only stages a person may switch between by hand (close / reopen a lead).
MANUAL_STAGES = (S.OPEN, S.CLOSED)

# What a LeadSquared upload is allowed to set on a NEW lead. Everything from
# BOOKED onward is decided inside this CRM, never by a file.
IMPORT_STAGES = (S.OPEN, S.CLOSED)


STAGE_LABELS = {
    S.OPEN: "Open", S.BOOKED: "Booked", S.INSURANCE_DONE: "Insurance Done",
    S.RTO_DONE: "RTO Done", S.INVOICED: "Invoiced", S.DELIVERED: "Delivered",
    S.CLOSED: "Closed",
}


def stage_label(value) -> str:
    """Readable name for a stage (accepts the enum or its text value)."""
    try:
        return STAGE_LABELS[value if isinstance(value, S) else S(str(value))]
    except (KeyError, ValueError):
        return str(value or "")


def _as_stage(value) -> S:
    try:
        return value if isinstance(value, S) else S(str(value).upper())
    except ValueError:
        raise HTTPException(400, f"Unknown stage '{value}'")


def can_change(current: S | None, new: S) -> bool:
    return (current or S.OPEN) == new or new in ALLOWED_NEXT.get(current or S.OPEN, set())


def change_stage(db, lead: Lead, new_stage, *, actor_user_id: int | None = None,
                 reason: str | None = None, manual: bool = False) -> bool:
    """Move `lead` to `new_stage`. Returns True if the stage actually changed.

    manual=True is for a person using the lead screen: only OPEN <-> CLOSED is
    accepted, and only while the lead is still OPEN or CLOSED (a booked lead's
    stage belongs to the system). Does not commit.
    """
    new = _as_stage(new_stage)
    current = lead.enquiry_stage or S.OPEN

    if new == current:
        return False

    if manual:
        if current not in MANUAL_STAGES or new not in MANUAL_STAGES:
            raise HTTPException(
                400, "This stage is updated by the system (payment, insurance, RTO, "
                     "invoice, delivery) and can't be changed by hand")

    if not can_change(current, new):
        raise HTTPException(400, f"A lead can't move from {current.value} to {new.value}")

    lead.enquiry_stage = new
    _after_stage_change(db, lead, current, new, actor_user_id, reason)
    return True


def _alert_recipient_ids(db, lead: Lead) -> list[int]:
    """Who hears about a stage change: the lead's PBA, the CRE(s) covering its
    branch, every GM and every Owner (active accounts only), no duplicates."""
    ids: list[int] = []
    if lead.assigned_user_id:
        ids.append(lead.assigned_user_id)
    if lead.branch_id:
        ids += [u.user_id for u in (
            db.query(AppUser).join(UserBranch, UserBranch.user_id == AppUser.user_id)
            .filter(AppUser.role == Role.CRE, AppUser.is_active.is_(True),
                    UserBranch.branch_id == lead.branch_id).all())]
    ids += [u.user_id for u in (
        db.query(AppUser).filter(AppUser.role.in_([Role.GM, Role.OWNER]),
                                 AppUser.is_active.is_(True)).all())]
    return list(dict.fromkeys(ids))      # keep order, drop repeats


def _after_stage_change(db, lead: Lead, old: S, new: S, actor_user_id, reason) -> None:
    """Runs once per REAL stage change: history row + alerts (not committed —
    they save or roll back together with the change itself)."""
    db.add(StageHistory(lead_id=lead.lead_id, from_stage=old.value, to_stage=new.value,
                        changed_by_user_id=actor_user_id, reason=reason))

    name = lead.customer.full_name if getattr(lead, "customer", None) else "Customer"
    if new == S.DELIVERED:    # CRE final-review task: one alert to every CRE covering the branch
        for u in (db.query(AppUser).join(UserBranch, UserBranch.user_id == AppUser.user_id)
                  .filter(AppUser.role == Role.CRE, AppUser.is_active.is_(True), UserBranch.branch_id == lead.branch_id).all()):
            create_notification(db, user_id=u.user_id, type_=NotificationType.FINAL_REVIEW_DUE, title="Final review due",
                                message=f"{name} (enquiry {lead.enquiry_no}) has been delivered. Call the customer, record the final review and close the file.",
                                reference_type="lead", reference_id=lead.lead_id, actor_user_id=actor_user_id)
    text = f"{name} (enquiry {lead.enquiry_no}) moved from {stage_label(old)} to {stage_label(new)}."
    for uid in _alert_recipient_ids(db, lead):
        create_notification(
            db, user_id=uid, type_=NotificationType.STAGE_CHANGED,
            title=f"Stage changed: {stage_label(old)} → {stage_label(new)}",
            message=text, reference_type="lead", reference_id=lead.lead_id,
            actor_user_id=actor_user_id)


# ---- dashboard counting rules (used by every dashboard number) --------------
# A delivered customer later becomes CLOSED once the CRE finishes the final
# review. That lead must still count as a SALE, so "closed after delivery" is
# read from the stage history (leads/stages.py is the only writer of it).
def _closed_from(db, stages):
    return (db.query(StageHistory.lead_id)
            .filter(StageHistory.to_stage == S.CLOSED.value,
                    StageHistory.from_stage.in_([x.value for x in stages])))


def sold_condition(db):
    """Booked or any later stage, including delivered-then-closed. Excludes
    cancelled bookings and leads that never booked."""
    return or_(Lead.enquiry_stage.in_(BOUGHT_STAGES),
               Lead.lead_id.in_(_closed_from(db, [S.DELIVERED])))


def invoiced_condition(db):
    """Reached invoicing (invoiced, delivered, or delivered-then-closed)."""
    return or_(Lead.enquiry_stage.in_([S.INVOICED, S.DELIVERED]),
               Lead.lead_id.in_(_closed_from(db, [S.DELIVERED])))


def delivered_condition(db):
    return or_(Lead.enquiry_stage == S.DELIVERED,
               Lead.lead_id.in_(_closed_from(db, [S.DELIVERED])))


def open_booking_condition():
    return Lead.enquiry_stage.in_(OPEN_BOOKING_STAGES)


def cancelled_booking_condition(db):
    """Closed after a booking existed (not delivered). A lead that was only
    ever an enquiry and got closed is a lost lead, NOT a cancelled sale."""
    return (Lead.enquiry_stage == S.CLOSED) & Lead.lead_id.in_(
        _closed_from(db, CANCELLABLE_STAGES)) & ~Lead.lead_id.in_(
        _closed_from(db, [S.DELIVERED]))


# ---- named events (what the rest of the app calls) --------------------------
def mark_booked(db, lead: Lead, actor_user_id: int | None = None) -> bool:
    """Call when the FIRST payment for a lead is saved (Booking & Payment block).
    Does nothing if the lead is already booked or beyond."""
    if (lead.enquiry_stage or S.OPEN) != S.OPEN:
        return False
    return change_stage(db, lead, S.BOOKED, actor_user_id=actor_user_id,
                        reason="First payment saved")
