"""Booking & payment records.

One BOOKING per lead (created when its first payment is saved) and many
PAYMENTS under it — one row per payment actually received. Payments are only
ever added (never edited or deleted); every one gets its own receipt number.

Money figures (total paid, outstanding, payment status) are NOT stored: they
are worked out from the payment rows every time (payments/service.py), so they
can't drift out of step.
"""
import enum

from sqlalchemy import (Column, Date, DateTime, ForeignKey, Integer, Numeric,
                        String, Text, UniqueConstraint)
from sqlalchemy.orm import relationship

from app.core.database import Base, now_ist


class PaymentMode(str, enum.Enum):
    CASH = "CASH"
    CHEQUE = "CHEQUE"
    UPI = "UPI"
    BANK_TRANSFER = "BANK_TRANSFER"   # NEFT / RTGS / bank transfer
    CARD = "CARD"
    FINANCE = "FINANCE"               # loan amount received from the finance company


class PaymentStatus(str, enum.Enum):
    PENDING = "PENDING"               # nothing paid yet
    PARTIALLY_PAID = "PARTIALLY_PAID"
    PAID = "PAID"


class Booking(Base):
    __tablename__ = "booking"
    booking_id = Column(Integer, primary_key=True)
    booking_no = Column(String, unique=True, index=True, nullable=False)   # e.g. BKA12746-0001
    lead_id = Column(Integer, ForeignKey("lead.lead_id"), unique=True, nullable=False)
    customer_id = Column(Integer, ForeignKey("customer.customer_id"), nullable=False)
    branch_id = Column(Integer, ForeignKey("branch.branch_id"))
    # the quotation the total vehicle cost is read from (live, so a corrected
    # quotation price flows through)
    quotation_id = Column(Integer, ForeignKey("quotation.quotation_id"))
    created_by_user_id = Column(Integer, ForeignKey("app_user.user_id"))
    created_at = Column(DateTime, default=now_ist, nullable=False)

    # finance (EMI) choice for this booking — the ROI is typed in, not fixed
    finance_bank_name = Column(String)
    emi_tenure_months = Column(Integer)
    roi_percent = Column(Numeric(5, 2))

    lead = relationship("Lead")
    quotation = relationship("Quotation")
    payments = relationship("Payment", back_populates="booking",
                            order_by="Payment.receipt_seq", cascade="all, delete-orphan")


class Payment(Base):
    __tablename__ = "payment"
    payment_id = Column(Integer, primary_key=True)
    booking_id = Column(Integer, ForeignKey("booking.booking_id"), nullable=False)
    lead_id = Column(Integer, ForeignKey("lead.lead_id"), nullable=False, index=True)
    receipt_seq = Column(Integer, nullable=False)          # 1, 2, 3 ... within the booking
    payment_date = Column(Date, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    mode = Column(String, nullable=False)                  # a PaymentMode value
    reference = Column(String)                             # UTR / UPI id / cheque no. / card slip
    finance_bank_name = Column(String)                     # when mode = FINANCE
    remark = Column(Text)

    # optional photo of the transaction (same file rules as KYC uploads)
    photo_original_name = Column(String)
    photo_stored_path = Column(String)
    photo_content_type = Column(String)
    photo_size_bytes = Column(Integer)

    recorded_by_user_id = Column(Integer, ForeignKey("app_user.user_id"))
    created_at = Column(DateTime, default=now_ist, nullable=False)

    # customer "I AGREE" acknowledgement, given on a secure link (no login)
    agree_token = Column(String, unique=True, index=True)   # created when the link is first requested
    agreed_at = Column(DateTime)                             # when the customer confirmed
    agreed_ip = Column(String)
    agreed_user_agent = Column(String)
    agreed_receipt_snapshot = Column(Text)                   # what the customer saw: receipt no, amount, totals

    booking = relationship("Booking", back_populates="payments")
    recorded_by = relationship("AppUser")

    __table_args__ = (UniqueConstraint("booking_id", "receipt_seq", name="uq_payment_receipt"),)

    @property
    def receipt_no(self) -> str:
        return f"{self.booking.booking_no}-R{self.receipt_seq}"

    @property
    def payment_type(self) -> str:
        """CASH, or FINANCE (with the bank name) — as the requirement lists it."""
        return "FINANCE" if self.mode == PaymentMode.FINANCE.value else "CASH"
