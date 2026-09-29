"""Small, safe database updates that run automatically on backend startup
(see app/main.py).

This project has no migration tool (Alembic) yet, and SQLAlchemy's
`create_all()` only creates MISSING TABLES — it never adds a new column to a
table that already exists. So new columns are added here with
`ADD COLUMN IF NOT EXISTS`, which does nothing when the column is already
there. Safe to run on every start.

Current updates:
  - lead.branch_code  (showroom code from the LeadSquared "Enquiry Branch
                       Code" column; separate from dealer_code)
"""
from sqlalchemy import text


def apply_schema_updates(engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE lead ADD COLUMN IF NOT EXISTS branch_code VARCHAR"))