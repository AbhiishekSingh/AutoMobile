"""LeadSquared 'Enquiry Statement Report' importer — CSV and Excel (.xlsx/.xls).

Reads the exact 35-column export, dedupes customers by phone, skips leads whose
Enquiry Number already exists, and auto-creates lookup values (mode, model,
opportunity status, disposition, lost reason) that aren't in the DB yet.

Salesperson assignment: tries "Salesperson Email Address" first, falls back to
"Salesperson Name" (case-insensitive) against a PBA's full name, and only ever
matches an active PBA account. See `_find_salesperson` for the full rationale.

CSV and Excel files both funnel into the same `_process_rows` — only the
"turn the uploaded bytes into a list of {column: value} dicts" step differs
(`_rows_from_csv` / `_rows_from_excel`), so every rule above applies identically
regardless of which file type was uploaded.
"""
import csv
import io
from datetime import datetime, timedelta

from openpyxl import load_workbook
from sqlalchemy.orm import Session

from app.core.database import now_ist
from app.modules.leads.models import (BikeModel, Customer, Disposition,
                                      EnquiryMode, EnquiryStage, Lead,
                                      LeadSource, LeadType, LostReason,
                                      OpportunityStatus, SLAFlag, TestRide,
                                      TestRideStatus)
from app.modules.notifications.service import create_bulk_assignment_notifications
from app.modules.users.models import AppUser, Branch, Role


# ---------- small parsing helpers ----------
def _clean(v):
    return (v or "").strip()


def _digits(v):
    return "".join(ch for ch in (v or "") if ch.isdigit())


def _parse_dt(s):
    """LeadSquared uses dd-mm-YYYY and dd-mm-YYYY HH:MM."""
    s = _clean(s)
    if not s:
        return None
    for fmt in ("%d-%m-%Y %H:%M", "%d-%m-%Y %H:%M:%S", "%d-%m-%Y",
                "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _parse_enquiry_at(date_s, time_s):
    d = _parse_dt(date_s)
    if not d:
        return None
    t = _clean(time_s)
    if t:
        try:
            hh, mm = t.split(":")[:2]
            d = d.replace(hour=int(hh), minute=int(mm))
        except (ValueError, TypeError):
            pass
    return d


def _yes(v):
    return _clean(v).lower() in ("yes", "y", "true", "1")


def _int(v):
    try:
        return int(float(_clean(v)))
    except (ValueError, TypeError):
        return 0


_STAGE_MAP = {"open": EnquiryStage.OPEN, "closed": EnquiryStage.CLOSED,
              "booked": EnquiryStage.BOOKED, "invoiced": EnquiryStage.INVOICED}


def _stage(v):
    return _STAGE_MAP.get(_clean(v).lower(), EnquiryStage.OPEN)


def _get_or_create(db, Model, name, cache):
    """Find a lookup row by name (case-insensitive), creating it if missing.
    `cache` avoids repeat queries within one file."""
    name = _clean(name)
    if not name:
        return None
    key = (Model.__name__, name.lower())
    if key in cache:
        return cache[key]
    obj = db.query(Model).filter(Model.name.ilike(name)).first()
    if not obj:
        obj = Model(name=name)
        db.add(obj)
        db.flush()
    cache[key] = obj
    return obj


def _find_salesperson(db, email: str, name: str, cache: dict):
    """Resolve a CSV row's salesperson to an actual PBA account.

    Real-world exports (e.g. from LeadSquared/Bajaj) often carry a
    "Salesperson Email Address" that isn't the PBA's login email at all
    (a phone-number-style @bajajauto.co.in address, for example) — matching
    on email alone silently leaves the lead unassigned in that case. So:

      1. Try an exact-ish, case-insensitive match on email.
      2. If that fails, fall back to a case-insensitive match on the
         "Salesperson Name" column against the PBA's full name.
      3. Either way, only ever match an ACTIVE PBA — never an Owner/GM/Admin/
         CRE/RTO account, and never a deactivated user, even if their email
         or name happens to coincide.

    Returns the matched AppUser, or None (caller decides how to report that).
    `cache` memoizes lookups within one import so a file with 500 rows for
    the same salesperson only queries the DB once.
    """
    email = _clean(email)
    name = _clean(name)
    key = ("salesperson", email.lower(), name.lower())
    if key in cache:
        return cache[key]

    sp = None
    if email:
        sp = (db.query(AppUser)
                .filter(AppUser.email.ilike(email),
                        AppUser.role == Role.PBA, AppUser.is_active.is_(True))
                .first())
    if not sp and name:
        sp = (db.query(AppUser)
                .filter(AppUser.full_name.ilike(name),
                        AppUser.role == Role.PBA, AppUser.is_active.is_(True))
                .first())

    cache[key] = sp
    return sp


def _rows_from_csv(content: bytes):
    """Yield (line_no, row_dict) from CSV bytes. line_no matches the row's
    actual line in the file (header is line 1) so error messages point
    somewhere the person can actually find in their file."""
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    for line_no, row in enumerate(reader, start=2):
        yield line_no, row


def _rows_from_excel(content: bytes):
    """Yield (line_no, row_dict) from an .xlsx/.xls workbook's first sheet.

    Header is read from row 1; every cell is coerced to a string so downstream
    parsing (`_clean`, `_parse_dt`, `_digits`, etc.) behaves identically to the
    CSV path — Excel would otherwise hand back native `int`/`float`/`datetime`
    objects for numeric-looking or date-looking cells (e.g. a phone number or
    an enquiry number that Excel auto-formatted as a number), which would
    silently break `.strip()`/digit-extraction downstream if left as-is.
    """
    wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    ws = wb.worksheets[0]
    rows_iter = ws.iter_rows(values_only=True)
    try:
        header = [(_clean(str(h)) if h is not None else "") for h in next(rows_iter)]
    except StopIteration:
        return
    for line_no, values in enumerate(rows_iter, start=2):
        row = {}
        for col, val in zip(header, values):
            if not col:
                continue
            if val is None:
                row[col] = ""
            elif isinstance(val, datetime):
                row[col] = val.strftime("%d-%m-%Y %H:%M")
            elif isinstance(val, float) and val.is_integer():
                row[col] = str(int(val))   # avoid "9822010001.0" for numeric-looking cells
            else:
                row[col] = str(val)
        yield line_no, row


def import_leads_file(content: bytes, filename: str, db: Session,
                      default_branch_id: int | None = None,
                      actor_user_id: int | None = None) -> dict:
    """Entry point for both CSV and Excel uploads — picks the right row
    parser by extension, then runs the exact same processing either way."""
    name = (filename or "").lower()
    if name.endswith((".xlsx", ".xls")):
        rows = _rows_from_excel(content)
    else:
        rows = _rows_from_csv(content)
    return _process_rows(rows, db, default_branch_id=default_branch_id,
                         actor_user_id=actor_user_id)


def import_leads_csv(content: bytes, db: Session, default_branch_id: int | None = None,
                     actor_user_id: int | None = None) -> dict:
    """Back-compat wrapper — CSV only. Prefer `import_leads_file`, which also
    handles Excel uploads."""
    return _process_rows(_rows_from_csv(content), db, default_branch_id=default_branch_id,
                         actor_user_id=actor_user_id)


def _process_rows(rows, db: Session, default_branch_id: int | None = None,
                  actor_user_id: int | None = None) -> dict:
    cache = {}   # memoizes _get_or_create / _find_salesperson lookups within this one import
    # Collapsed into ONE notification per assignee at the end of the import,
    # instead of one per lead — a 500-row CSV assigning 300 leads to the same
    # PBA should produce a single "300 new leads assigned to you", not 300
    # separate rows flooding their bell.
    assigned_counts: dict[int, int] = {}
    summary = {"rows_read": 0, "leads_created": 0, "customers_new": 0,
               "customers_matched": 0, "test_rides_created": 0,
               "skipped_duplicates": 0, "skipped_invalid": 0,
               "salesperson_matched": 0, "salesperson_unmatched": 0, "errors": []}

    for line_no, row in rows:
        try:
            enquiry_no = _clean(row.get("Enquiry Number"))
            name = _clean(row.get("Customer"))
            phone = _digits(row.get("Mobile"))

            # a totally empty / trailing line
            if not enquiry_no and not name and not phone:
                continue
            summary["rows_read"] += 1

            if not enquiry_no:
                summary["skipped_invalid"] += 1
                summary["errors"].append(f"Row {line_no}: missing Enquiry Number")
                continue

            # idempotency: skip if this enquiry already imported
            if db.query(Lead).filter(Lead.enquiry_no == enquiry_no).first():
                summary["skipped_duplicates"] += 1
                continue

            # ---- customer dedupe by phone ----
            cust = None
            if phone:
                cust = db.query(Customer).filter(Customer.phone == phone).first()
            if cust:
                summary["customers_matched"] += 1
            else:
                cust = Customer(phone=phone or f"NA-{enquiry_no}", full_name=name or "Unknown",
                                pincode=_clean(row.get("PIN Code")))
                db.add(cust)
                db.flush()
                summary["customers_new"] += 1

            # ---- branch: fixed pick, else by CSV branch name ----
            if default_branch_id:
                branch_id = default_branch_id
            else:
                bname = _clean(row.get("Enquiry Branch Name"))
                branch = None
                if bname:
                    branch = db.query(Branch).filter(Branch.name.ilike(bname)).first()
                    if not branch:
                        branch = Branch(name=bname)
                        db.add(branch)
                        db.flush()
                branch_id = branch.branch_id if branch else None

            # ---- salesperson: email first, then fall back to name — see
            # _find_salesperson for why (real exports rarely carry the PBA's
            # actual login email). Only ever resolves to an active PBA. ----
            sp_name = _clean(row.get("Salesperson Name"))
            sp_email = _clean(row.get("Salesperson Email Address"))
            sp = _find_salesperson(db, sp_email, sp_name, cache)
            if sp_email or sp_name:
                if sp:
                    summary["salesperson_matched"] += 1
                else:
                    summary["salesperson_unmatched"] += 1
                    if len(summary["errors"]) < 50:
                        summary["errors"].append(
                            f"Row {line_no}: no active PBA matched salesperson "
                            f"'{sp_name or sp_email}' — lead left unassigned")

            # ---- lookups (auto-create) ----
            mode = _get_or_create(db, EnquiryMode, row.get("Enquiry Mode"), cache)
            model = _get_or_create(db, BikeModel, row.get("Model"), cache)
            opp = _get_or_create(db, OpportunityStatus, row.get("Opportunity Status"), cache)
            disp = _get_or_create(db, Disposition, row.get("Follow Up Dispositions"), cache)
            lost = _get_or_create(db, LostReason, row.get("Lost Reason"), cache)

            enquiry_at = _parse_enquiry_at(row.get("Enquiry Date"), row.get("Enquiry Time"))
            first_contact = _parse_dt(row.get("First Follow Up DateTime"))
            next_fu = _parse_dt(row.get("Next Follow Up DateTime"))

            # SLA flag from first-contact timing
            sla = SLAFlag.YELLOW
            if first_contact and enquiry_at:
                sla = SLAFlag.GREEN if (first_contact - enquiry_at) <= timedelta(hours=3) else SLAFlag.RED

            lead = Lead(
                enquiry_no=enquiry_no, customer_id=cust.customer_id, branch_id=branch_id,
                assigned_user_id=sp.user_id if sp else None,
                mode_id=mode.id if mode else None, model_id=model.id if model else None,
                color=_clean(row.get("Color")), sku_code=_clean(row.get("SKU Code")),
                lead_type=LeadType.SALES, source=LeadSource.CSV,
                enquiry_stage=_stage(row.get("Enquiry Stage")),
                opportunity_status_id=opp.id if opp else None,
                current_disposition_id=disp.id if disp else None,
                lost_reason_id=lost.id if lost else None,
                sla_flag=sla, enquiry_at=enquiry_at or now_ist(),
                first_contact_at=first_contact, next_followup_at=next_fu,
                ageing_days=_int(row.get("Ageing Days")),
                dealer_code=_clean(row.get("Enquiry Dealer Code")),
                salesperson_email=sp_email or None,
            )
            db.add(lead)
            db.flush()
            summary["leads_created"] += 1
            if lead.assigned_user_id:
                assigned_counts[lead.assigned_user_id] = (
                    assigned_counts.get(lead.assigned_user_id, 0) + 1)

            # ---- optional test ride ----
            tr_status = _clean(row.get("Test Ride Status"))
            tr_completed = _yes(row.get("Test Ride Completed"))
            tr_booked = _yes(row.get("Test Ride Booked"))
            if tr_status or tr_completed or tr_booked:
                status = TestRideStatus.COMPLETED if tr_completed else TestRideStatus.BOOKED
                db.add(TestRide(
                    lead_id=lead.lead_id, model_id=model.id if model else None,
                    color=_clean(row.get("Color")), status=status, completed=tr_completed,
                    scheduled_at=_parse_dt(row.get("Test Ride Booking (Scheduled) Date")),
                    slot=_clean(row.get("Test Ride Slot")),
                    preferred_location=_clean(row.get("Test Ride preferred location")),
                ))
                summary["test_rides_created"] += 1

        except Exception as e:   # never let one bad row abort the whole file
            summary["skipped_invalid"] += 1
            if len(summary["errors"]) < 50:
                summary["errors"].append(f"Row {line_no}: {e}")

    # One grouped notification per assignee, added to the same transaction as
    # the leads themselves — if the commit below fails, neither the leads nor
    # the notifications persist, so there's never a "notified but lead missing"
    # (or vice versa) state.
    if assigned_counts:
        create_bulk_assignment_notifications(db, counts_by_user_id=assigned_counts,
                                             actor_user_id=actor_user_id)

    db.commit()
    return summary