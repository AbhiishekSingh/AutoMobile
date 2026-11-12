"""FOLLOW-UP SLA — worked out from the clock every time, never stored.

The rule (PBA requirement file): a lead must be contacted within 3 hours of
the enquiry.

  state        meaning                                         flag colour
  -----------  ----------------------------------------------  -----------
  COMPLETED    first contact made within 3 hours of enquiry    GREEN
  LATE         first contact made, but after 3 hours           RED
  WITHIN_TIME  not contacted yet, still inside the 3 hours     YELLOW
  PENDING      not contacted, more than 3 hours (up to 24)     YELLOW
  OVERDUE      not contacted, more than 24 hours               RED

Pipeline buckets (leads page):
  Completed = COMPLETED
  Pending   = PENDING + LATE   (the 3-hour follow-up was not completed in time)
  Overdue   = OVERDUE          (still not contacted after 24 hours)

The same rules exist twice below — once as SQL conditions (counting and
filtering in the database) and once in Python (a single lead's badge). Keep
the two in step; tests/ compare them case by case.
Working hours / off days are NOT applied (Admin uploads leads in working
hours, so the clock simply runs from the enquiry time).
"""
from datetime import datetime, timedelta

from sqlalchemy import and_, or_

from app.core.database import now_ist
from app.modules.leads.models import Lead

FIRST_CONTACT_WINDOW = timedelta(hours=3)
OVERDUE_AFTER = timedelta(hours=24)

COMPLETED, LATE, WITHIN_TIME, PENDING, OVERDUE = (
    "COMPLETED", "LATE", "WITHIN_TIME", "PENDING", "OVERDUE")

_FLAG = {COMPLETED: "GREEN", LATE: "RED", WITHIN_TIME: "YELLOW",
         PENDING: "YELLOW", OVERDUE: "RED"}


# ---- one lead (Python) ------------------------------------------------------
def sla_state(enquiry_at: datetime | None, first_contact_at: datetime | None,
              now: datetime | None = None) -> str:
    now = now or now_ist()
    enquiry_at = enquiry_at or now
    if first_contact_at is not None:
        return COMPLETED if first_contact_at <= enquiry_at + FIRST_CONTACT_WINDOW else LATE
    waited = now - enquiry_at
    if waited > OVERDUE_AFTER:
        return OVERDUE
    if waited > FIRST_CONTACT_WINDOW:
        return PENDING
    return WITHIN_TIME


def sla_flag(state: str) -> str:
    return _FLAG[state]


def lead_sla(lead, now: datetime | None = None) -> tuple[str, str]:
    """(state, flag colour) for a Lead object."""
    st = sla_state(lead.enquiry_at, lead.first_contact_at, now)
    return st, _FLAG[st]


# ---- many leads (SQL conditions) --------------------------------------------
def sla_conditions(now: datetime | None = None) -> dict:
    """SQL conditions for the same rules, keyed by state, plus 'completed_bucket'
    style groupings used by the pipeline and the dashboard chart."""
    now = now or now_ist()
    contacted = Lead.first_contact_at.isnot(None)
    not_contacted = Lead.first_contact_at.is_(None)
    in_time = Lead.first_contact_at <= Lead.enquiry_at + FIRST_CONTACT_WINDOW

    c = {
        COMPLETED:   and_(contacted, in_time),
        LATE:        and_(contacted, ~in_time),
        OVERDUE:     and_(not_contacted, Lead.enquiry_at < now - OVERDUE_AFTER),
        PENDING:     and_(not_contacted, Lead.enquiry_at < now - FIRST_CONTACT_WINDOW,
                          Lead.enquiry_at >= now - OVERDUE_AFTER),
        WITHIN_TIME: and_(not_contacted, Lead.enquiry_at >= now - FIRST_CONTACT_WINDOW),
    }
    c["GREEN"] = c[COMPLETED]
    c["RED"] = or_(c[LATE], c[OVERDUE])
    c["YELLOW"] = or_(c[PENDING], c[WITHIN_TIME])
    c["PENDING_BUCKET"] = or_(c[PENDING], c[LATE])
    return c


# ---- ageing -----------------------------------------------------------------
def ageing_days(lead, today: datetime | None = None) -> int:
    """How many days old the enquiry is (calendar days since the enquiry date)."""
    today = today or now_ist()
    if not lead.enquiry_at:
        return 0
    return max((today.date() - lead.enquiry_at.date()).days, 0)
