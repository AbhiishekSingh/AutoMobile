"""One-time fill of lead.branch_code for leads imported BEFORE the importer
started saving the "Enquiry Branch Code" column.

The database never stored that column, so this re-reads the file(s) you
imported (CSV or Excel), matches rows by Enquiry Number, and fills in the
Branch Code — only on leads where it's still empty. Nothing else changes.

Usage (from the backend folder, with the virtualenv active):

    python -m app.seeds.fill_branch_codes Dashboard_Test_Leads.xlsx Branch_Test_Leads_10.xlsx          # dry run
    python -m app.seeds.fill_branch_codes Dashboard_Test_Leads.xlsx Branch_Test_Leads_10.xlsx --apply  # save

Safe to run more than once.
"""
import sys

from app.core.database import SessionLocal
from app.db import base as _base  # noqa: F401  (register all models)
from app.modules.imports.service import _clean, _rows_from_csv, _rows_from_excel
from app.modules.leads.models import Lead


def run(paths: list[str], apply: bool) -> None:
    db = SessionLocal()
    filled = matched = 0
    try:
        for path in paths:
            content = open(path, "rb").read()
            rows = (_rows_from_excel(content) if path.lower().endswith((".xlsx", ".xls"))
                    else _rows_from_csv(content))
            for _line, row in rows:
                enquiry_no = _clean(row.get("Enquiry Number"))
                code = _clean(row.get("Enquiry Branch Code"))
                if not enquiry_no or not code:
                    continue
                lead = db.query(Lead).filter(Lead.enquiry_no == enquiry_no).first()
                if not lead:
                    continue
                matched += 1
                if not lead.branch_code:
                    lead.branch_code = code
                    filled += 1
        print(f"Rows matched to existing leads: {matched}")
        print(f"Leads given a Branch Code: {filled}")
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
    files = [a for a in sys.argv[1:] if a != "--apply"]
    if not files:
        print(__doc__)
        sys.exit(1)
    run(files, apply="--apply" in sys.argv)