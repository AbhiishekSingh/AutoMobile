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
  - customer_document table (KYC / customer documents uploaded by PBA)
  - customer_detail_history table (earlier versions of a customer's details,
                       kept when a LeadSquared import brings newer ones)
  - booking + payment tables (booking & payment records — see
                       app/modules/payments/)
  - lead_stage_history table (one row per real stage change — see
                       app/modules/leads/stages.py)
  - enquirystage enum: adds INSURANCE_DONE / RTO_DONE / DELIVERED, and moves
                       any old QUOTED lead back to OPEN (QUOTED was removed —
                       see app/modules/leads/stages.py)
"""
from sqlalchemy import text

from app.core.database import Base


NEW_STAGE_VALUES = ("INSURANCE_DONE", "RTO_DONE", "DELIVERED")


def _update_stage_enum(engine) -> None:
    """Add the new stage labels to the existing Postgres enum (a brand-new
    database already gets them from create_all) and retire QUOTED."""
    # ALTER TYPE ... ADD VALUE must run outside a transaction block
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        if conn.execute(text("SELECT 1 FROM pg_type WHERE typname = 'enquirystage'")).first():
            for v in NEW_STAGE_VALUES:
                conn.execute(text(f"ALTER TYPE enquirystage ADD VALUE IF NOT EXISTS '{v}'"))
            # compare as text so this also works on a type that never had QUOTED
            conn.execute(text("UPDATE lead SET enquiry_stage = 'OPEN' "
                              "WHERE enquiry_stage::text = 'QUOTED'"))


def _update_role_enum(engine) -> None:
    """Add the BRANCH role to the existing Postgres role enum."""
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        if conn.execute(text("SELECT 1 FROM pg_type WHERE typname = 'role'")).first():
            conn.execute(text("ALTER TYPE role ADD VALUE IF NOT EXISTS 'BRANCH'"))
            conn.execute(text("ALTER TYPE role ADD VALUE IF NOT EXISTS 'INSURANCE'"))


def apply_schema_updates(engine) -> None:
    _update_stage_enum(engine)
    _update_role_enum(engine)

    # imported here so every model is registered before create_all runs
    from app.modules.documents.models import CustomerDocument
    from app.modules.leads.models import CustomerDetailHistory, LeadModelInterest, StageHistory
    from app.modules.handoffs.models import (AtwApproval, DeliveryRecord, InsuranceCase,
                                             InvoiceDetail, OwnerApproval, RtoCase)
    from app.modules.payments.models import Booking, Payment
    from app.modules.stock.models import StockItem, StockMovement
    from app.modules.targets.models import SalesTarget
    from app.modules.whatsapp.models import DealerLink, WhatsappMessage
    from app.modules.users.models import UserBranch
    from app.modules.accounts.models import PaymentRecon, Refund, VendorBill
    from app.modules.final_review.models import FinalReview

    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE lead ADD COLUMN IF NOT EXISTS branch_code VARCHAR"))
        conn.execute(text("ALTER TABLE app_user ADD COLUMN IF NOT EXISTS phone VARCHAR"))
        conn.execute(text("ALTER TABLE app_user ADD COLUMN IF NOT EXISTS login_enabled BOOLEAN NOT NULL DEFAULT TRUE"))
        conn.execute(text("ALTER TABLE app_user ADD COLUMN IF NOT EXISTS pin_hash VARCHAR"))
        conn.execute(text("ALTER TABLE app_user ADD COLUMN IF NOT EXISTS ls_email VARCHAR"))
        conn.execute(text("ALTER TABLE app_user ADD COLUMN IF NOT EXISTS ls_name VARCHAR"))
        conn.execute(text("ALTER TABLE app_user ADD COLUMN IF NOT EXISTS pin_failed INTEGER NOT NULL DEFAULT 0"))
        conn.execute(text("ALTER TABLE app_user ADD COLUMN IF NOT EXISTS pin_locked_until TIMESTAMP"))
        conn.execute(text("ALTER TABLE branch ADD COLUMN IF NOT EXISTS whatsapp_number VARCHAR"))
        for col, typ in (("showroom_visit", "VARCHAR"), ("test_ride_interest", "VARCHAR"),
                         ("callback_remind_at", "TIMESTAMP"), ("callback_notified", "BOOLEAN DEFAULT FALSE")):
            conn.execute(text(f"ALTER TABLE lead ADD COLUMN IF NOT EXISTS {col} {typ}"))
        # checkfirst=True (the default): does nothing if the table exists
        Base.metadata.create_all(bind=conn, tables=[UserBranch.__table__, PaymentRecon.__table__, VendorBill.__table__, Refund.__table__, FinalReview.__table__,
                                                    CustomerDetailHistory.__table__,
                                                    CustomerDocument.__table__,
                                                    StageHistory.__table__,
                                                    LeadModelInterest.__table__,
                                                    Booking.__table__,
                                                    Payment.__table__,
                                                    InsuranceCase.__table__, RtoCase.__table__,
                                                    OwnerApproval.__table__, AtwApproval.__table__,
                                                    InvoiceDetail.__table__, DeliveryRecord.__table__,
                                                    StockItem.__table__, StockMovement.__table__,
                                                    SalesTarget.__table__, WhatsappMessage.__table__, DealerLink.__table__])
        # "I AGREE" columns on payment (table may already exist without them)
        for col, typ in (("agree_token", "VARCHAR"), ("agreed_at", "TIMESTAMP"), ("agreed_ip", "VARCHAR"),
                         ("agreed_user_agent", "VARCHAR"), ("agreed_receipt_snapshot", "TEXT")):
            conn.execute(text(f"ALTER TABLE payment ADD COLUMN IF NOT EXISTS {col} {typ}"))
        for col, typ in (("discounted_price", "NUMERIC(12,2)"), ("payment_type", "VARCHAR DEFAULT 'CASH'"),
                         ("down_payment", "NUMERIC(12,2)"), ("acc_helmet", "BOOLEAN"),
                         ("acc_parking_cover", "BOOLEAN"), ("rsa_one_year", "BOOLEAN"),
                         ("engine_warranty_years", "INTEGER")):
            conn.execute(text(f"ALTER TABLE quotation ADD COLUMN IF NOT EXISTS {col} {typ}"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_payment_agree_token ON payment (agree_token)"))
