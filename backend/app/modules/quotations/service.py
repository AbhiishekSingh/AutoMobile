"""Reusable helpers for the quotations module (kept out of the router)."""
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import now_ist
from app.modules.leads.models import EnquiryStage, Lead
from app.modules.quotations.models import (DEFAULT_DOCUMENTS,
                                           DEFAULT_EMI_TENURES,
                                           DEFAULT_INCLUSIONS, Quotation,
                                           QuotationDocument,
                                           QuotationEmiOption,
                                           QuotationInclusion)
from app.modules.users.access import MANAGER_ROLES, scope_leads
from app.modules.users.models import AppUser

VALIDITY_DAYS = 15


def scope(query, user: AppUser):
    """A user sees a quotation if they can see its LEAD (same rule as the
    Leads screen — app/modules/users/access.py). Owner/GM/Admin see all."""
    if user.role.value in MANAGER_ROLES:
        return query
    visible_leads = scope_leads(select(Lead.lead_id), user)
    return query.filter(Quotation.lead_id.in_(visible_leads))


def next_quotation_no(db: Session) -> str:
    seq = (db.query(func.count(Quotation.quotation_id)).scalar() or 0) + 1
    return f"QUO{100000 + seq}"


def seed_defaults(db: Session, quotation: Quotation) -> None:
    """Populate a freshly created quotation with the standard inclusion list,
    the four EMI tenure rows, and the standard documents checklist."""
    for i, desc in enumerate(DEFAULT_INCLUSIONS):
        db.add(QuotationInclusion(quotation_id=quotation.quotation_id,
                                  description=desc, included=True, sort_order=i))

    for months in DEFAULT_EMI_TENURES:
        db.add(QuotationEmiOption(quotation_id=quotation.quotation_id,
                                  tenure_months=months))

    for name in DEFAULT_DOCUMENTS:
        db.add(QuotationDocument(quotation_id=quotation.quotation_id,
                                 document_name=name, required=True))


def check_choices(data: dict) -> None:
    """Validate the cash/EMI choice, warranty years and money fields (raises ValueError)."""
    if data.get("payment_type") is not None and data["payment_type"] not in ("CASH", "EMI"):
        raise ValueError("Payment must be Cash or EMI")
    if data.get("engine_warranty_years") is not None and data["engine_warranty_years"] not in (5, 10):
        raise ValueError("Engine warranty must be 5 or 10 years")
    for f in ("discounted_price", "down_payment"):
        if data.get(f) is not None and data[f] < 0:
            raise ValueError("Amounts cannot be negative")
    price, disc, down = data.get("on_road_price"), data.get("discounted_price"), data.get("down_payment")
    if price is not None and disc is not None and disc > price:
        raise ValueError("The discounted price cannot be more than the on-road price")
    if disc is not None and down is not None and down > disc:
        raise ValueError("The down payment cannot be more than the discounted price")
    if price is not None and down is not None and disc is None and down > price:
        raise ValueError("The down payment cannot be more than the on-road price")


def monthly_emi(loan, tenure_months: int, roi_percent):
    """Standard reducing-balance EMI. roi_percent is the yearly rate typed in by the PBA."""
    from decimal import Decimal
    loan, roi = Decimal(loan), Decimal(roi_percent)
    if loan <= 0 or tenure_months <= 0:
        return None
    r = roi / Decimal(1200)
    if r == 0:
        return (loan / tenure_months).quantize(Decimal("1"))
    f = (1 + r) ** tenure_months
    return (loan * r * f / (f - 1)).quantize(Decimal("1"))


def mark_lead_quoted(lead: Lead) -> None:
    """Kept so existing callers still work. Creating a quotation no longer
    changes the lead's stage (QUOTED was removed from the journey) — whether
    a quotation was shared is tracked by the quotation's own status."""
    return None

def default_valid_until():
    return now_ist() + timedelta(days=VALIDITY_DAYS)
