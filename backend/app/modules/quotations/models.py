"""Quotation module — vehicle quotations generated against a lead."""
import enum

from sqlalchemy import (Boolean, Column, DateTime, Enum, ForeignKey, Integer,
                        Numeric, String)
from sqlalchemy.orm import relationship

from app.core.database import Base, now_ist


class HsprRegistrationType(str, enum.Enum):
    REGULAR = "REGULAR"
    CHOICE = "CHOICE"
    BH_PASSING = "BH_PASSING"


class QuotationStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SHARED = "SHARED"
    ACCEPTED = "ACCEPTED"
    EXPIRED = "EXPIRED"
    REJECTED = "REJECTED"


DEFAULT_INCLUSIONS = [
    "Insurance Premium (1yr Own Damage + 5yr Third Party)",
    "RTO Road Tax & Registration",
    "ISI Certified Helmet",
    "RSA (Road Side Assistance)",
    "Standard Tool Kit & First Aid Kit",
    "Parking Cover",
    "10yrs Engine Warranty (KTM 5yr + 5yr Extended Warranty)",
]

DEFAULT_DOCUMENTS = [
    "PAN CARD", "AADHAR CARD (linked to mobile no.)", "ELECTRICITY BILL",
    "6 Month Bank Statement", "Voter ID / Passport", "BH REG. COMPANY ID",
    "FORM 60", "GST / IT RETURN",
]

DEFAULT_EMI_TENURES = [12, 24, 36, 48]


class Quotation(Base):
    __tablename__ = "quotation"
    quotation_id = Column(Integer, primary_key=True)
    quotation_no = Column(String, unique=True, index=True, nullable=False)
    lead_id = Column(Integer, ForeignKey("lead.lead_id"), nullable=False)
    customer_id = Column(Integer, ForeignKey("customer.customer_id"), nullable=False)
    branch_id = Column(Integer, ForeignKey("branch.branch_id"))
    created_by_user_id = Column(Integer, ForeignKey("app_user.user_id"))

    # snapshot fields (Aadhar name/contact may differ from lead's raw entry)
    customer_name = Column(String, nullable=False)
    contact_no = Column(String, nullable=False)
    email = Column(String)

    model_id = Column(Integer, ForeignKey("bike_model.id"))
    color = Column(String)
    on_road_price = Column(Numeric(12, 2), nullable=False)
    hspr_registration_type = Column(Enum(HsprRegistrationType),
                                    default=HsprRegistrationType.REGULAR)

    sales_manager_name = Column(String)

    finance_bank_name = Column(String)
    finance_financer_name = Column(String)

    status = Column(Enum(QuotationStatus), default=QuotationStatus.DRAFT)
    valid_until = Column(DateTime)
    created_at = Column(DateTime, default=now_ist)
    updated_at = Column(DateTime, default=now_ist, onupdate=now_ist)

    lead = relationship("Lead")
    customer = relationship("Customer")
    model = relationship("BikeModel")
    created_by = relationship("AppUser")
    inclusions = relationship("QuotationInclusion", back_populates="quotation",
                              order_by="QuotationInclusion.sort_order",
                              cascade="all, delete-orphan")
    emi_options = relationship("QuotationEmiOption", back_populates="quotation",
                               order_by="QuotationEmiOption.tenure_months",
                               cascade="all, delete-orphan")
    documents = relationship("QuotationDocument", back_populates="quotation",
                             cascade="all, delete-orphan")


class QuotationInclusion(Base):
    __tablename__ = "quotation_inclusion"
    id = Column(Integer, primary_key=True)
    quotation_id = Column(Integer, ForeignKey("quotation.quotation_id"), nullable=False)
    description = Column(String, nullable=False)
    included = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)

    quotation = relationship("Quotation", back_populates="inclusions")


class QuotationEmiOption(Base):
    __tablename__ = "quotation_emi_option"
    id = Column(Integer, primary_key=True)
    quotation_id = Column(Integer, ForeignKey("quotation.quotation_id"), nullable=False)
    tenure_months = Column(Integer, nullable=False)
    down_payment = Column(Numeric(12, 2))
    monthly_emi = Column(Numeric(12, 2))
    roi_percent = Column(Numeric(5, 2))

    quotation = relationship("Quotation", back_populates="emi_options")


class QuotationDocument(Base):
    __tablename__ = "quotation_document"
    id = Column(Integer, primary_key=True)
    quotation_id = Column(Integer, ForeignKey("quotation.quotation_id"), nullable=False)
    document_name = Column(String, nullable=False)
    required = Column(Boolean, default=True)

    quotation = relationship("Quotation", back_populates="documents")