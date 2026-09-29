"""Test ride rules — booking, completing, rescheduling, cancelling.

LIFECYCLE
  new ride ─┬─ BOOKED ──┬─ Mark Completed ──> COMPLETED   (final)
            │           ├─ Reschedule ──────> RESCHEDULED (can be completed /
            │           │                                  rescheduled / cancelled again)
            │           └─ Cancel ──────────> CANCELLED   (final)
            └─ COMPLETED straight away — ONLY for a spot ride: the customer is
               in the showroom and riding right now (date = today, not later)

RULES
  - A new ride is either BOOKED (needs a date/time, today or later) or a spot
    ride COMPLETED now. It can't be created as Rescheduled or Cancelled.
  - No completing in advance: a booked ride can only be marked Completed once
    its scheduled time has come (up to COMPLETE_EARLY_GRACE early, for a
    customer who turns up a little before the slot).
  - Completed and Cancelled rides are final.

LEAD STATUS (Opportunity Status) — updated automatically:
  ride booked / rescheduled -> TEST RIDE BOOKED
  ride completed            -> TEST RIDE COMPLETED
  ride cancelled            -> left as it is (the PBA decides what's next)
  Never changed once the customer has bought: lead stage BOOKED/INVOICED, or
  status BOOKING DONE / DELIVERED, stays as it is.
Every change is written to the Activity Log.
"""
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.database import IST, now_ist
from app.modules.audit.service import record_changes
from app.modules.leads.lookup_names import lookup_key
from app.modules.leads.models import (EnquiryStage, Lead, OpportunityStatus,
                                      TestRide, TestRideStatus)

COMPLETE_EARLY_GRACE = timedelta(minutes=15)   # may mark done this long before the slot
PAST_GRACE = timedelta(minutes=5)              # form opened a few minutes ago is fine

OPEN = (TestRideStatus.BOOKED, TestRideStatus.RESCHEDULED)
BOUGHT_STAGES = (EnquiryStage.BOOKED, EnquiryStage.INVOICED)
BOUGHT_STATUSES = ("BOOKING DONE", "DELIVERED")


def to_ist_naive(value: datetime | None) -> datetime | None:
    """Datetimes are stored as IST wall-clock with no timezone."""
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(IST).replace(tzinfo=None)


def _fmt(dt: datetime) -> str:
    return dt.strftime("%d %b %Y, %I:%M %p")


# ---------- lead Opportunity Status ----------
def set_lead_test_ride_status(db: Session, lead: Lead, status_name: str,
                              actor_user_id: int | None) -> None:
    """Move the lead's Opportunity Status to TEST RIDE BOOKED / COMPLETED,
    unless the customer has already bought (never downgrade a sale)."""
    if lead.enquiry_stage in BOUGHT_STAGES:
        return
    current = lead.opportunity.name if lead.opportunity else None
    if current and lookup_key(current) in {lookup_key(n) for n in BOUGHT_STATUSES}:
        return
    target = next((o for o in db.query(OpportunityStatus)
                   .filter(OpportunityStatus.is_active.is_(True)).all()
                   if lookup_key(o.name) == lookup_key(status_name)), None)
    if not target or target.id == lead.opportunity_status_id:
        return
    before = {"opportunity_status_id": lead.opportunity_status_id}
    lead.opportunity_status_id = target.id
    record_changes(db, entity_type="lead", entity_id=lead.lead_id, before=before,
                   after=lead, fields=("opportunity_status_id",),
                   changed_by_user_id=actor_user_id)


# ---------- create ----------
def create_test_ride(db: Session, lead: Lead, *, status: str, scheduled_at: datetime | None,
                     model_id=None, color=None, slot=None, preferred_location=None,
                     actor_user_id: int | None = None) -> TestRide:
    now = now_ist()
    scheduled_at = to_ist_naive(scheduled_at)
    status = (status or "BOOKED").upper()

    if status == "BOOKED":
        if not scheduled_at:
            raise HTTPException(400, "Please choose the date & time of the test ride")
        if scheduled_at < now - PAST_GRACE:
            raise HTTPException(400, "A test ride can't be booked in the past — pick a time from now onwards")
        new_status, opp = TestRideStatus.BOOKED, "TEST RIDE BOOKED"
    elif status == "COMPLETED":
        # Spot ride: the customer is riding right now.
        if scheduled_at is None:
            scheduled_at = now
        if scheduled_at.date() != now.date() or scheduled_at > now + PAST_GRACE:
            raise HTTPException(400, "'Completed' is only for a customer riding right now "
                                     "(today). For a later date, book the ride and mark it "
                                     "completed after it happens.")
        new_status, opp = TestRideStatus.COMPLETED, "TEST RIDE COMPLETED"
    else:
        raise HTTPException(400, "A new test ride can only be Booked, or Completed for a "
                                 "customer riding right now")

    ride = TestRide(lead_id=lead.lead_id, model_id=model_id, color=color, status=new_status,
                    completed=new_status == TestRideStatus.COMPLETED,
                    scheduled_at=scheduled_at, slot=slot, preferred_location=preferred_location)
    db.add(ride)
    db.flush()
    record_changes(db, entity_type="test_ride", entity_id=ride.id,
                   before={"status": None, "scheduled_at": None}, after=ride,
                   fields=("status", "scheduled_at"), changed_by_user_id=actor_user_id)
    set_lead_test_ride_status(db, lead, opp, actor_user_id)
    return ride


# ---------- update an existing ride ----------
def update_test_ride(db: Session, ride: TestRide, *, action: str,
                     scheduled_at: datetime | None = None, slot: str | None = None,
                     actor_user_id: int | None = None) -> TestRide:
    if ride.status not in OPEN:
        raise HTTPException(400, f"This test ride is already {ride.status.value.lower()} "
                                 f"and can't be changed")
    now = now_ist()
    before = {"status": ride.status, "scheduled_at": ride.scheduled_at, "slot": ride.slot}
    lead = ride.lead

    if action == "complete":
        if ride.scheduled_at and ride.scheduled_at - COMPLETE_EARLY_GRACE > now:
            raise HTTPException(400, f"This test ride is scheduled for {_fmt(ride.scheduled_at)}. "
                                     f"It can be marked completed once it has happened.")
        ride.status, ride.completed = TestRideStatus.COMPLETED, True
        set_lead_test_ride_status(db, lead, "TEST RIDE COMPLETED", actor_user_id)

    elif action == "reschedule":
        scheduled_at = to_ist_naive(scheduled_at)
        if not scheduled_at:
            raise HTTPException(400, "Please choose the new date & time")
        if scheduled_at < now - PAST_GRACE:
            raise HTTPException(400, "The new time can't be in the past")
        ride.status, ride.completed = TestRideStatus.RESCHEDULED, False
        ride.scheduled_at = scheduled_at
        if slot is not None:
            ride.slot = slot or None
        set_lead_test_ride_status(db, lead, "TEST RIDE BOOKED", actor_user_id)

    elif action == "cancel":
        ride.status, ride.completed = TestRideStatus.CANCELLED, False

    else:
        raise HTTPException(400, "Unknown action")

    record_changes(db, entity_type="test_ride", entity_id=ride.id, before=before, after=ride,
                   fields=("status", "scheduled_at", "slot"), changed_by_user_id=actor_user_id)
    return ride