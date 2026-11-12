"""Reusable helpers for the leads module (kept out of the router)."""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.database import IST, now_ist
from app.modules.leads.lookup_names import lookup_key
from app.modules.leads.sla import COMPLETED, OVERDUE, sla_conditions
from app.modules.leads.models import (Customer, CustomerDetailHistory,
                                      Disposition, Lead, LeadType, LostReason,
                                      OpportunityStatus, SLAFlag, TestRide,
                                      TestRideStatus)
from app.modules.users.access import scope_leads
from app.modules.users.models import AppUser


# ---------------------------------------------------------------------------
# Fixed dropdown lists
#
# These are the ONLY values a user can pick in the two status dropdowns on
# Customer Details / Add Follow-up, in the order they're shown. Edit a list
# here and restart the backend — that's all (see sync_dropdown_lists below,
# which app/main.py runs on every startup).
#
# Values not in a list are switched off (is_active = False), never deleted:
# existing leads and follow-up history still point at them and keep showing
# their original name.
# ---------------------------------------------------------------------------
FOLLOWUP_DISPOSITIONS = [
    "VEHICLE NOT IN STOCK",
    "PLANNING",
    "SATISFIED / POSITIVE EXPERIENCE",
    "FUTURE CUSTOMER",
    "PRAISE FOR PBA",
    "PRODUCT SATISFACTION",
    "PRODUCT/QUALITY ISSUE",
    "STAFF CONDUCT CONCERN",
    "ESCALATED TO GM",
    "OUT OF BUDGET",
]

OPPORTUNITY_STATUSES = [
    "RINGING/BUSY/SWITCH OFF",
    "CALL LATER",
    "INCOMING OFF/VOICE MAIL",
    "OPEN LEAD",
    "BOOKING DONE",
    "CASUAL ENQUIRY",
    "FALSE ENQUIRY",
    "DELIVERED",
    "TEST RIDE BOOKED",
    "TEST RIDE COMPLETED",
    "PLAN DROPPED",
    "NO POTENTIAL",          # set by CRE: customer details are kept, lead isn't deleted
]

# lookup table -> its fixed list
DROPDOWN_LISTS = {
    Disposition: FOLLOWUP_DISPOSITIONS,
    OpportunityStatus: OPPORTUNITY_STATUSES,
}
_ALLOWED_KEYS = {M: [lookup_key(n) for n in names] for M, names in DROPDOWN_LISTS.items()}


def is_allowed(Model, name: str) -> bool:
    """True if `name` is in Model's fixed list (spelling-insensitive)."""
    return lookup_key(name) in _ALLOWED_KEYS[Model]


def list_sort_key(Model, name: str) -> int:
    """Position of `name` in Model's fixed list (unknown -> last)."""
    keys = _ALLOWED_KEYS[Model]
    k = lookup_key(name)
    return keys.index(k) if k in keys else len(keys)


def dropdown_options(db: Session, Model) -> list:
    """The rows to offer in Model's dropdown: only listed + active, in list order."""
    rows = [r for r in db.query(Model).filter(Model.is_active.is_(True)).all()
            if is_allowed(Model, r.name)]
    rows.sort(key=lambda r: (list_sort_key(Model, r.name), r.id))
    return rows


def _sync_one(db: Session, Model, names: list[str]) -> tuple[int, int]:
    wanted = {lookup_key(n): n for n in names}
    rows = db.query(Model).order_by(Model.id).all()
    existing_names = {r.name for r in rows}
    found = set()
    switched_off = 0
    for r in rows:
        k = lookup_key(r.name)
        if k in wanted and k not in found:
            found.add(k)
            # use the exact spelling from the list (names are UNIQUE, so only
            # if no other row already has that exact name)
            if r.name != wanted[k] and wanted[k] not in existing_names:
                r.name = wanted[k]
            r.is_active = True
        else:
            if r.is_active:
                switched_off += 1
            r.is_active = False
    for k, name in wanted.items():
        if k not in found:
            db.add(Model(name=name, is_active=True))
    return len(wanted), switched_off


def sync_dropdown_lists(db: Session) -> dict[str, tuple[int, int]]:
    """Make each lookup table in DROPDOWN_LISTS match its list: create missing
    values, fix spelling, switch listed values ON and everything else OFF.

    Runs automatically on every backend start (app/main.py). Safe to run any
    number of times. Returns {table_name: (active_count, switched_off_count)}.
    """
    out = {M.__tablename__: _sync_one(db, M, names) for M, names in DROPDOWN_LISTS.items()}
    db.commit()
    return out


# ---------------------------------------------------------------------------
# Next Follow-up Date window
#
# A next follow-up can only be set from "now" up to the end of the day
# FOLLOWUP_MAX_DAYS days from today (IST). E.g. on 23 Sep, anything from now
# until 8 Oct 23:59 is allowed. The frontend limits the date picker to the
# same window; this is the server-side check behind it.
# ---------------------------------------------------------------------------
FOLLOWUP_MAX_DAYS = 15
_FOLLOWUP_GRACE = timedelta(minutes=5)   # form opened a few minutes ago is fine


def followup_window() -> tuple[datetime, datetime]:
    """(earliest, latest_exclusive) allowed Next Follow-up datetime, IST-naive."""
    now = now_ist()
    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return now - _FOLLOWUP_GRACE, start_of_today + timedelta(days=FOLLOWUP_MAX_DAYS + 1)


def check_followup_date(value: datetime | None) -> datetime | None:
    """Return `value` as an IST-naive datetime if it's inside followup_window(),
    else raise ValueError with a message fit to show the user. None passes."""
    if value is None:
        return None
    if value.tzinfo is not None:   # e.g. "...Z" or "+05:30" sent by an API client
        value = value.astimezone(IST).replace(tzinfo=None)
    earliest, latest = followup_window()
    if value < earliest:
        raise ValueError("Next Follow-up Date can't be in the past")
    if value >= latest:
        last_day = (latest - timedelta(days=1)).strftime("%d %b %Y")
        raise ValueError(f"Next Follow-up Date must be within the next "
                         f"{FOLLOWUP_MAX_DAYS} days (up to {last_day})")
    return value


# ---------------------------------------------------------------------------
# Returning customers — one customer per phone number
#
# The phone number is how the CRM recognises a returning customer (walk-in
# form and LeadSquared import alike). Numbers arrive as "9822010001",
# "+91 98220 10001", "09822010001" ... so they're compared on their last 10
# digits, and new numbers are saved as plain 10 digits.
# ---------------------------------------------------------------------------
def normalize_phone(phone: str | None) -> str:
    """Digits only; drops a leading 91 / 0 from an Indian mobile number."""
    p = "".join(ch for ch in (phone or "") if ch.isdigit())
    if len(p) == 12 and p.startswith("91"):
        p = p[2:]
    elif len(p) == 11 and p.startswith("0"):
        p = p[1:]
    return p


def find_customer_by_phone(db: Session, phone: str | None) -> Customer | None:
    """The existing customer with this phone number, whichever way it was
    stored, or None."""
    p = normalize_phone(phone)
    if not p:
        return None
    candidates = {p, f"91{p}", f"+91{p}", f"0{p}", f"+91 {p}", (phone or "").strip()}
    return (db.query(Customer).filter(Customer.phone.in_(candidates))
            .order_by(Customer.customer_id).first())


DETAIL_FIELDS = ("full_name", "alt_phone", "email", "city", "pincode")


def update_customer_details(db: Session, cust: Customer, new: dict, *, source: str,
                            enquiry_no: str | None = None) -> bool:
    """Make `new` the customer's current details, keeping the old ones.

    Only non-empty values in `new` count (a blank cell in a file never wipes
    a saved value). If nothing actually changes, nothing is written. If
    something does, the details as they were BEFORE are saved as one
    CustomerDetailHistory row, then the customer is updated.
    Returns True if the details changed. Does not commit.
    """
    changes = {f: v.strip() for f, v in new.items()
               if f in DETAIL_FIELDS and isinstance(v, str) and v.strip()
               and v.strip() != (getattr(cust, f) or "")}
    if not changes:
        return False
    db.add(CustomerDetailHistory(
        customer_id=cust.customer_id,
        **{f: getattr(cust, f) for f in DETAIL_FIELDS},
        replaced_by_source=source, replaced_by_enquiry_no=enquiry_no,
        replaced_at=now_ist(),
    ))
    for f, v in changes.items():
        setattr(cust, f, v)
    return True


def mask_phone(phone: str) -> str:
    p = "".join(ch for ch in (phone or "") if ch.isdigit())
    if len(p) < 4:
        return phone or ""
    return f"{p[:2]}{'X' * (len(p) - 4)}{p[-2:]}"


def scope(query, user: AppUser, branch_id: int | None = None, whole_branch: bool = False):
    """Limit a Lead query to what `user` may see (optionally one branch).

    The rule itself lives in app/modules/users/access.py (scope_leads) so
    Leads, Customers, Follow Ups, Dashboard and Quotations all share it:
    PBA = own leads + unassigned in own branch; CRE = every lead in their
    1-2 branches; Owner/GM/Admin = everything.
    """
    return scope_leads(query, user, branch_id, whole_branch)


def _ids_named(db: Session, Model, name: str) -> list[int]:
    """Ids of every row in Model whose name matches `name` spelling-insensitively
    (so "Call Later" and "CALL LATER" both count)."""
    k = lookup_key(name)
    return [r.id for r in db.query(Model).all() if lookup_key(r.name) == k]


def bucket_filter(query, bucket: str, db: Session):
    if bucket in (None, "", "all"):
        return query
    # Completed / Pending / Overdue come from the clock (leads/sla.py), not a stored flag
    if bucket == "completed":
        return query.filter(sla_conditions()[COMPLETED])
    if bucket == "pending":
        return query.filter(sla_conditions()["PENDING_BUCKET"])
    if bucket == "overdue":
        return query.filter(sla_conditions()[OVERDUE])
    if bucket == "calllater":
        # "CALL LATER" is now an Opportunity Status; older/imported leads may
        # still carry it as a disposition — count both.
        d_ids = _ids_named(db, Disposition, "CALL LATER")
        o_ids = _ids_named(db, OpportunityStatus, "CALL LATER")
        return query.filter(Lead.current_disposition_id.in_(d_ids or [-1]) |
                            Lead.opportunity_status_id.in_(o_ids or [-1]))
    if bucket == "testride":
        sub = db.query(TestRide.lead_id).filter(TestRide.status == TestRideStatus.COMPLETED)
        return query.filter(Lead.lead_id.in_(sub))
    if bucket == "service":
        return query.filter(Lead.lead_type == LeadType.SERVICE)
    if bucket == "unassigned":      # in the branch pool: nobody owns it yet
        return query.filter(Lead.assigned_user_id.is_(None))
    if bucket == "closed":
        return query.filter(Lead.enquiry_stage == "CLOSED")
    if bucket == "future":
        # Opportunity Status "FUTURE LEAD" (leads imported from LeadSquare) OR
        # Disposition "FUTURE CUSTOMER" (picked by the PBA in the CRM).
        o_ids = _ids_named(db, OpportunityStatus, "FUTURE LEAD")
        d_ids = _ids_named(db, Disposition, "FUTURE CUSTOMER")
        return query.filter(Lead.opportunity_status_id.in_(o_ids or [-1]) |
                            Lead.current_disposition_id.in_(d_ids or [-1]))
    if bucket == "casual":
        # Opportunity Status "CASUAL ENQUIRY", or (older/imported leads) a
        # lost reason containing "casual".
        r = db.query(LostReason).filter(LostReason.name.ilike("%casual%")).first()
        o_ids = _ids_named(db, OpportunityStatus, "CASUAL ENQUIRY")
        return query.filter((Lead.lost_reason_id == (r.id if r else -1)) |
                            Lead.opportunity_status_id.in_(o_ids or [-1]))
    return query
