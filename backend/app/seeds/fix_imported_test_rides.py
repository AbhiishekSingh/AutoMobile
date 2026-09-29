"""One-time fix for test rides imported BEFORE the importer mapped
LeadSquared's "Test Ride Status" properly.

Previously every imported test ride that wasn't completed was saved as
BOOKED — including LeadSquared "Incomplete" and "Invalid" ones — so they
showed up as "scheduled" on the dashboard. They should be CANCELLED.

The database doesn't keep LeadSquared's original status text, so this
re-reads the SAME file you imported (CSV or Excel), matches rows by Enquiry
Number, and corrects only those leads' imported test ride. Nothing is
created or deleted.

Usage (from the backend folder):

    python -m app.seeds.fix_imported_test_rides "Enquiry_Statement_Report_45.csv"           # dry run
    python -m app.seeds.fix_imported_test_rides "Enquiry_Statement_Report_45.csv" --apply   # save

Safe to run more than once.
"""
import sys

from app.core.database import SessionLocal
from app.db import base as _base  # noqa: F401  (register all models)
from app.modules.imports.service import (_clean, _rows_from_csv, _rows_from_excel,
                                         test_ride_status_from_row)
from app.modules.leads.models import Lead, TestRide, TestRideStatus


def run(path: str, apply: bool) -> None:
    content = open(path, "rb").read()
    rows = (_rows_from_excel(content) if path.lower().endswith((".xlsx", ".xls"))
            else _rows_from_csv(content))

    db = SessionLocal()
    matched = fixed = 0
    changes: dict[str, int] = {}
    try:
        for _line, row in rows:
            enquiry_no = _clean(row.get("Enquiry Number"))
            if not enquiry_no:
                continue
            lead = db.query(Lead).filter(Lead.enquiry_no == enquiry_no).first()
            if not lead:
                continue
            matched += 1

            # the imported ride = the lead's first test ride
            ride = (db.query(TestRide).filter(TestRide.lead_id == lead.lead_id)
                    .order_by(TestRide.id).first())
            # only touch rides still in the "open" state the old importer
            # created; anything a PBA has since updated is left alone
            if not ride or ride.status not in (TestRideStatus.BOOKED, TestRideStatus.RESCHEDULED):
                continue
            new_status = test_ride_status_from_row(row)
            if new_status != ride.status:
                key = f"{ride.status.value} -> {new_status.value}"
                changes[key] = changes.get(key, 0) + 1
                ride.status = new_status
                ride.completed = new_status == TestRideStatus.COMPLETED
                fixed += 1

        print(f"Rows matched to existing leads: {matched}")
        print(f"Test rides corrected: {fixed}")
        for k, n in sorted(changes.items()):
            print(f"    {k}: {n}")
        if apply:
            db.commit()
            print("Saved.")
        else:
            db.rollback()
            print("DRY RUN — nothing saved. Re-run with --apply to save.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--apply"]
    if not args:
        print(__doc__)
        sys.exit(1)
    run(args[0], apply="--apply" in sys.argv)