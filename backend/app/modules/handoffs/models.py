"""Hand-offs after a booking: Insurance -> RTO, and the Owner's approvals.

One row per lead in each table (a lead has one booking).
  InsuranceCase  starts as soon as the PBA sets Opportunity Status = BOOKING DONE
  RtoCase        starts when the insurance policy PDF is uploaded
  OwnerApproval  the PBA asks the Owner to approve the deal (special items + delivery date)
  AtwApproval    Owner approves / rejects the 10-year engine warranty for this customer
"""
from sqlalchemy import (Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import relationship

from app.core.database import Base, now_ist


class InsuranceCase(Base):
    __tablename__ = "insurance_case"
    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer, ForeignKey("lead.lead_id"), unique=True, nullable=False)
    status = Column(String, nullable=False, default="PENDING")   # PENDING / IN_PROGRESS / COMPLETED
    policy_type = Column(String)            # MBO_ACKO or CUSTOMER_BAGIC
    nominee_name = Column(String)
    nominee_age = Column(Integer)
    nominee_relation = Column(String)
    nominee_relation_other = Column(String)
    hypothecation = Column(String)          # HP: bank / financer name, empty = none
    policy_no = Column(String, unique=True)
    policy_start = Column(Date)
    policy_expiry = Column(Date)
    premium = Column(Numeric(12, 2))
    pdf_original_name = Column(String)
    pdf_stored_path = Column(String)
    pdf_size_bytes = Column(Integer)
    completed_at = Column(DateTime)
    completed_by_user_id = Column(Integer, ForeignKey("app_user.user_id"))
    updated_by_user_id = Column(Integer, ForeignKey("app_user.user_id"))
    created_at = Column(DateTime, default=now_ist, nullable=False)
    updated_at = Column(DateTime, default=now_ist, onupdate=now_ist)

    completed_by = relationship("AppUser", foreign_keys=[completed_by_user_id])


class RtoCase(Base):
    __tablename__ = "rto_case"
    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer, ForeignKey("lead.lead_id"), unique=True, nullable=False)
    status = Column(String, nullable=False, default="PENDING")   # PENDING / IN_PROCESS / REGISTERED
    registration_type = Column(String)      # REGULAR / CHOICE / BH_PASSING
    registration_no = Column(String)        # the online registration number
    registration_date = Column(Date)
    delivery_date = Column(Date)            # bike delivery date, as told to the PBA
    updated_by_user_id = Column(Integer, ForeignKey("app_user.user_id"))
    created_at = Column(DateTime, default=now_ist, nullable=False)   # = when insurance finished
    updated_at = Column(DateTime, default=now_ist, onupdate=now_ist)


class InvoiceDetail(Base):
    """What the PBA records once the invoice exists (invoice copy + vehicle numbers).
    Chassis and engine numbers are mandatory. One row per lead; editable until delivery."""
    __tablename__ = "invoice_detail"
    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer, ForeignKey("lead.lead_id"), unique=True, nullable=False)
    invoice_no = Column(String)
    invoice_date = Column(Date)
    chassis_no = Column(String, unique=True, nullable=False)
    engine_no = Column(String, unique=True, nullable=False)
    registration_type = Column(String)          # REGULAR / CHOICE / BH_PASSING
    hypothecation = Column(String)              # HP: bank name, empty = none
    nominee_name = Column(String)
    nominee_relation = Column(String)
    insurance_addon = Column(String)            # add-on covers asked for
    delivery_date = Column(Date)                # planned bike delivery date
    file_original_name = Column(String)
    file_stored_path = Column(String)
    file_content_type = Column(String)
    file_size_bytes = Column(Integer)
    created_by_user_id = Column(Integer, ForeignKey("app_user.user_id"))
    created_at = Column(DateTime, default=now_ist, nullable=False)
    updated_at = Column(DateTime, default=now_ist, onupdate=now_ist)


class OwnerApproval(Base):
    __tablename__ = "owner_approval"
    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer, ForeignKey("lead.lead_id"), unique=True, nullable=False)
    status = Column(String, nullable=False, default="PENDING")   # PENDING / APPROVED / REJECTED
    special_items = Column(String)          # comma list: PRICE, CHOICE_NO, ...
    note = Column(Text)                     # PBA's note to the Owner
    delivery_date = Column(Date)            # final bike delivery date asked for
    requested_by_user_id = Column(Integer, ForeignKey("app_user.user_id"))
    requested_at = Column(DateTime, default=now_ist)
    decided_by_user_id = Column(Integer, ForeignKey("app_user.user_id"))
    decided_at = Column(DateTime)
    decision_note = Column(Text)            # reason (required when rejected)

    requested_by = relationship("AppUser", foreign_keys=[requested_by_user_id])
    decided_by = relationship("AppUser", foreign_keys=[decided_by_user_id])


class AtwApproval(Base):
    __tablename__ = "atw_approval"
    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer, ForeignKey("lead.lead_id"), unique=True, nullable=False)
    status = Column(String, nullable=False, default="PENDING")   # PENDING / APPROVED / REJECTED
    model_name = Column(String)             # vehicle the approval is for
    chassis_no = Column(String)             # filled when the invoice details are entered
    requested_by_user_id = Column(Integer, ForeignKey("app_user.user_id"))
    requested_at = Column(DateTime, default=now_ist)
    decided_by_user_id = Column(Integer, ForeignKey("app_user.user_id"))
    decided_at = Column(DateTime)
    decision_note = Column(Text)

    requested_by = relationship("AppUser", foreign_keys=[requested_by_user_id])
    decided_by = relationship("AppUser", foreign_keys=[decided_by_user_id])


class DeliveryRecord(Base):
    """The bike handover: delivery receipt, Owner's exception and the customer's I AGREE.
    One row per lead. Created when the PBA generates the receipt (or earlier, if the Owner
    records an exception for a lead that cannot yet be delivered)."""
    __tablename__ = "delivery_record"
    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer, ForeignKey("lead.lead_id"), unique=True, nullable=False)
    receipt_no = Column(String)
    delivery_date = Column(Date)                # actual handover date
    generated_at = Column(DateTime)
    generated_by_user_id = Column(Integer, ForeignKey("app_user.user_id"))
    # Owner's exception for pending approval / payment (the only thing that can be overridden)
    override_reason = Column(Text)
    override_by_user_id = Column(Integer, ForeignKey("app_user.user_id"))
    override_at = Column(DateTime)
    override_blockers = Column(Text)            # what was pending when the Owner allowed it
    # customer acknowledgement ("I AGREE") on a secure link
    ack_token = Column(String, unique=True, index=True)
    agreed_at = Column(DateTime)
    agreed_ip = Column(String)
    agreed_user_agent = Column(String)
    accepted_doc_id = Column(Integer)           # customer_document row holding the accepted PDF
    created_at = Column(DateTime, default=now_ist, nullable=False)

    generated_by = relationship("AppUser", foreign_keys=[generated_by_user_id])
    override_by = relationship("AppUser", foreign_keys=[override_by_user_id])
