"""LeadSquared 'Enquiry Statement Report' CSV importer.

Reads the exact 35-column export, dedupes customers by phone, skips leads whose
Enquiry Number already exists, and auto-creates lookup values (mode, model,
opportunity status, disposition, lost reason) that aren't in the DB yet.
"""
import csv
import io
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.database import now_ist
from app.modules.leads.models import (BikeModel, Customer, Disposition,
                                      EnquiryMode, EnquiryStage, Lead,
                                      LeadSource, LeadType, LostReason,
                                      OpportunityStatus, SLAFlag, TestRide,
                                      TestRideStatus)
from app.modules.users.models import AppUser, Branch


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


def import_leads_csv(content: bytes, db: Session, default_branch_id: int | None = None) -> dict:
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))

    cache = {}
    summary = {"rows_read": 0, "leads_created": 0, "customers_new": 0,
               "customers_matched": 0, "test_rides_created": 0,
               "skipped_duplicates": 0, "skipped_invalid": 0, "errors": []}

    for line_no, row in enumerate(reader, start=2):   # row 1 is the header
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

            # ---- salesperson by email (optional link) ----
            sp_email = _clean(row.get("Salesperson Email Address"))
            sp = db.query(AppUser).filter(AppUser.email == sp_email).first() if sp_email else None

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

    db.commit()
    return summary