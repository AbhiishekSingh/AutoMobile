"""Customer documents (KYC etc.) uploaded by the PBA against a lead.

The file itself is stored on disk (settings.UPLOAD_DIR); this table keeps
what it is, who uploaded it and where it's stored. Later stages (Owner
approval, Insurance, RTO) read the same rows.
"""
import enum

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.core.database import Base, now_ist


class DocumentType(str, enum.Enum):
    AADHAAR = "AADHAAR"
    PAN = "PAN"
    ELECTRICITY_BILL = "ELECTRICITY_BILL"   # own house
    RENT_AGREEMENT = "RENT_AGREEMENT"       # rented house (instead of electricity bill)
    BANK_STATEMENT = "BANK_STATEMENT"       # 6 months
    PHOTO = "PHOTO"
    CHEQUE = "CHEQUE"
    GST_CERTIFICATE = "GST_CERTIFICATE"
    IT_RETURN = "IT_RETURN"
    OTHER = "OTHER"


class CustomerDocument(Base):
    __tablename__ = "customer_document"
    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer, ForeignKey("lead.lead_id"), nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("customer.customer_id"), nullable=False, index=True)
    doc_type = Column(String, nullable=False)          # a DocumentType value
    note = Column(String)                              # e.g. "Back side", "Cheque 2"
    original_name = Column(String, nullable=False)     # file name as uploaded
    stored_path = Column(String, nullable=False)       # path relative to UPLOAD_DIR
    content_type = Column(String, nullable=False)
    size_bytes = Column(Integer, nullable=False)
    uploaded_by_user_id = Column(Integer, ForeignKey("app_user.user_id"))
    uploaded_at = Column(DateTime, default=now_ist, nullable=False)

    uploaded_by = relationship("AppUser")
