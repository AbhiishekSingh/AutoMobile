"""Accounts data that does not come from the PBA screens.

  PaymentRecon  a customer payment matched against the bank statement (no row = still pending)
  VendorBill    money the dealership owes (bike supplier, insurance, accessories ...)
  Refund        money going back to a customer whose booking was cancelled
"""
from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base, now_ist


class PaymentRecon(Base):
    __tablename__ = "payment_recon"
    id = Column(Integer, primary_key=True)
    payment_id = Column(Integer, ForeignKey("payment.payment_id"), unique=True, nullable=False)
    bank_ref = Column(String)                 # bank statement line / UTR seen on the statement
    note = Column(Text)
    reconciled_by_user_id = Column(Integer, ForeignKey("app_user.user_id"))
    reconciled_at = Column(DateTime, default=now_ist, nullable=False)

    reconciled_by = relationship("AppUser")


class VendorBill(Base):
    __tablename__ = "vendor_bill"
    id = Column(Integer, primary_key=True)
    branch_id = Column(Integer, ForeignKey("branch.branch_id"))     # empty = head office / all branches
    vendor = Column(String, nullable=False)
    category = Column(String, nullable=False, default="OTHER")      # see service.BILL_CATEGORIES
    bill_no = Column(String)
    bill_date = Column(Date, nullable=False)
    due_date = Column(Date)
    amount = Column(Numeric(12, 2), nullable=False)
    status = Column(String, nullable=False, default="PENDING")      # PENDING / PAID
    paid_date = Column(Date)
    paid_mode = Column(String)
    paid_ref = Column(String)
    note = Column(Text)
    created_by_user_id = Column(Integer, ForeignKey("app_user.user_id"))
    updated_by_user_id = Column(Integer, ForeignKey("app_user.user_id"))
    created_at = Column(DateTime, default=now_ist, nullable=False)
    updated_at = Column(DateTime, default=now_ist, onupdate=now_ist)

    branch = relationship("Branch")


class Refund(Base):
    __tablename__ = "refund"
    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer, ForeignKey("lead.lead_id"), unique=True, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    status = Column(String, nullable=False, default="PENDING")      # PENDING / PROCESSED
    processed_date = Column(Date)
    mode = Column(String)
    reference = Column(String)
    note = Column(Text)
    created_by_user_id = Column(Integer, ForeignKey("app_user.user_id"))
    updated_by_user_id = Column(Integer, ForeignKey("app_user.user_id"))
    created_at = Column(DateTime, default=now_ist, nullable=False)
    updated_at = Column(DateTime, default=now_ist, onupdate=now_ist)
