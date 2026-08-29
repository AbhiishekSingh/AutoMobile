"""Reusable helpers for the quotations module (kept out of the router)."""
from datetime import timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import now_ist
from app.modules.leads.models import EnquiryStage, Lead
from app.modules.quotations.models import (DEFAULT_DOCUMENTS,
                                           DEFAULT_EMI_TENURES,
                                           DEFAULT_INCLUSIONS, Quotation,
                                           QuotationDocument,
                                           QuotationEmiOption,
                                           QuotationInclusion)
from app.modules.users.models import AppUser, Role

VALIDITY_DAYS = 15


def scope(query, user: AppUser):
    """PBA sees only their branch's quotations; Owner/GM/Admin see all."""
    if user.role == Role.PBA and user.branch_id:
        query = query.filter(Quotation.branch_id == user.branch_id)
    return query


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