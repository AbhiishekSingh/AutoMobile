"""Call-details rule and the "Call Later" reminder.

1. After an ENQUIRY call the PBA must give the call details — bike model, colour,
   showroom visit, test ride — otherwise the call is not counted (requirement:
   "after call PBA should fill the details compulsory otherwise call will not be
   counted"). Calls that never reached a conversation (Ringing / Switch Off) and a
   "Call Later" need no details.
2. "Call Later": the PBA gets a notification 1 hour later to call the customer back.
   There is no background worker; due reminders are created when the PBA's
   notification bell next asks (it polls every minute or so) — see deliver_due_callbacks.
"""
from datetime import timedelta

from app.core.database import now_ist
from app.modules.leads.lookup_names import lookup_key
from app.modules.leads.models import Lead
from app.modules.notifications.models import NotificationType
from app.modules.notifications.service import create_notification

# dispositions that do NOT count as an enquiry conversation (compared with lookup_key)
NO_DETAILS_DISPOSITIONS = {lookup_key(n) for n in ("RINGING", "SWITCH OFF", "CALL LATER")}
CALL_LATER_KEY = lookup_key("CALL LATER")
CHOICES = ("YES", "NO", "PLANNED")
REMINDER_AFTER = timedelta(hours=1)


def missing_call_details(lead: Lead) -> list[str]:
    out = []
    if not lead.model_id:
        out.append("bike model")
    if not (lead.color or "").strip():
        out.append("colour")
    if not lead.showroom_visit:
        out.append("showroom visit")
    if not lead.test_ride_interest:
        out.append("test ride")
    return out


def needs_call_details(contacted: bool, disposition_name: str | None) -> bool:
    if not contacted:
        return False
    return not (disposition_name and lookup_key(disposition_name) in NO_DETAILS_DISPOSITIONS)


def update_callback_reminder(lead: Lead, disposition_name: str | None) -> None:
    """Called after every saved follow-up: Call Later starts a 1-hour reminder, any other
    outcome cancels a reminder that has not fired yet."""
    if disposition_name and lookup_key(disposition_name) == CALL_LATER_KEY:
        lead.callback_remind_at = now_ist() + REMINDER_AFTER
        lead.callback_notified = False
    elif lead.callback_remind_at and not lead.callback_notified:
        lead.callback_remind_at = None


def deliver_due_callbacks(db, user) -> int:
    """Create the reminder notification for this PBA's leads whose hour is up."""
    if user.role.value != "PBA":
        return 0
    due = (db.query(Lead).filter(Lead.assigned_user_id == user.user_id,
                                 Lead.callback_remind_at.isnot(None),
                                 Lead.callback_remind_at <= now_ist(),
                                 Lead.callback_notified.is_(False)).all())
    for lead in due:
        lead.callback_notified = True
        create_notification(
            db, user_id=user.user_id, type_=NotificationType.CALL_LATER_REMINDER,
            title="Call back now",
            message=f"{lead.customer.full_name} ({lead.enquiry_no}) asked to be called later. "
                    f"Please call back.",
            reference_type="lead", reference_id=lead.lead_id)
    if due:
        db.commit()
    return len(due)
