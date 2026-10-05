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


def mark_lead_quoted(lead: Lead) -> None:
    """Advance the lead to QUOTED unless it has already moved past that stage."""
    advanced_stages = {EnquiryStage.BOOKED, EnquiryStage.INVOICED, EnquiryStage.CLOSED}
    if lead.enquiry_stage not in advanced_stages:
        lead.enquiry_stage = EnquiryStage.QUOTED

def default_valid_until():
    return now_ist() + timedelta(days=VALIDITY_DAYS)