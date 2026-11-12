"""Accounts numbers. Customer money is read from the payment rows (never copied), so it always matches the PBA side."""
from datetime import date
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.accounts.models import PaymentRecon, Refund, VendorBill
from app.modules.leads.models import EnquiryStage as S, Lead
from app.modules.leads.stages import sold_condition
from app.modules.payments.models import Booking, Payment
from app.modules.payments.service import money

BILL_CATEGORIES = {"BIKE_PURCHASE": "Bike purchase (KTM)", "INSURANCE": "Insurance", "ACCESSORIES": "Accessories",
                   "RTO": "RTO / registration", "RENT_UTILITY": "Rent & utilities", "SALARY": "Salary / incentive",
                   "OTHER": "Other"}
PAY_MODES = ("CASH", "CHEQUE", "UPI", "BANK_TRANSFER", "CARD")


def payables_totals(db: Session, branch_id=None) -> dict:
    today = date.today()
    q = db.query(VendorBill)
    if branch_id:
        q = q.filter(VendorBill.branch_id == branch_id)
    pend = [b for b in q.filter(VendorBill.status == "PENDING").all()]
    paid = q.filter(VendorBill.status == "PAID").with_entities(func.coalesce(func.sum(VendorBill.amount), 0)).scalar()
    return {"payables": float(sum(b.amount for b in pend)), "payables_count": len(pend),
            "overdue": float(sum(b.amount for b in pend if b.due_date and b.due_date < today)),
            "overdue_count": sum(1 for b in pend if b.due_date and b.due_date < today),
            "payables_paid": float(paid or 0)}


def recon_totals(db: Session, branch_id=None) -> dict:
    q = (db.query(Payment.payment_id, Payment.amount, PaymentRecon.id)
         .join(Booking, Booking.booking_id == Payment.booking_id)
         .outerjoin(PaymentRecon, PaymentRecon.payment_id == Payment.payment_id))
    if branch_id:
        q = q.filter(Booking.branch_id == branch_id)
    done = pend = 0; done_amt = pend_amt = Decimal(0)
    for _, amt, rid in q.all():
        if rid: done += 1; done_amt += money(amt)
        else: pend += 1; pend_amt += money(amt)
    return {"reconciled": done, "reconciled_amount": float(done_amt), "unreconciled": pend, "unreconciled_amount": float(pend_amt)}


def cancelled_rows(db: Session, branch_id=None):
    """Cancelled bookings: booking exists, never sold, lead closed. -> (lead, booking, received, refund or None)"""
    q = (db.query(Lead, Booking).join(Booking, Booking.lead_id == Lead.lead_id)
         .filter(~sold_condition(db), Lead.enquiry_stage == S.CLOSED))
    if branch_id:
        q = q.filter(Lead.branch_id == branch_id)
    paid = dict(db.query(Payment.booking_id, func.coalesce(func.sum(Payment.amount), 0)).group_by(Payment.booking_id).all())
    refunds = {r.lead_id: r for r in db.query(Refund).all()}
    return [(l, b, money(paid.get(b.booking_id, 0)), refunds.get(l.lead_id)) for l, b in q.all()]


def refund_totals(db: Session, branch_id=None) -> dict:
    rows = cancelled_rows(db, branch_id)
    pend = [r for *_, r in rows if r and r.status == "PENDING"]
    done = [r for *_, r in rows if r and r.status == "PROCESSED"]
    return {"refund_pending": float(sum(r.amount for r in pend)), "refund_pending_count": len(pend),
            "refund_processed": float(sum(r.amount for r in done)), "refund_processed_count": len(done),
            "cancelled_no_refund_set": sum(1 for _, _, rec, r in rows if r is None and rec > 0)}


def all_totals(db: Session, branch_id=None) -> dict:
    return {**payables_totals(db, branch_id), **recon_totals(db, branch_id), **refund_totals(db, branch_id)}
