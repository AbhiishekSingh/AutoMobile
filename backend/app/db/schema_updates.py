"""Small, safe database updates that run automatically on backend startup
(see app/main.py).

This project has no migration tool (Alembic) yet, and SQLAlchemy's
`create_all()` only creates MISSING TABLES — it never adds a new column to a
table that already exists. So new columns are added here with
`ADD COLUMN IF NOT EXISTS`, which does nothing when the column is already
there, and new tables are created only if they don't exist yet. Safe to run
on every start.

Current updates:
  - lead.branch_code  (showroom code from the LeadSquared "Enquiry Branch
                       Code" column; separate from dealer_code)
  - user_branch table (which branches each CRE covers — set by Admin on the
                       Users page)
"""
from sqlalchemy import text

from app.core.database import Base


def apply_schema_updates(engine) -> None:
    # imported here so every model is registered before create_all runs
    from app.modules.users.models import UserBranch

    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE lead ADD COLUMN IF NOT EXISTS branch_code VARCHAR"))
        # checkfirst=True (the default): does nothing if the table exists
        Base.metadata.create_all(bind=conn, tables=[UserBranch.__table__])
