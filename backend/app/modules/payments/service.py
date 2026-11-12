"""Booking & payment rules — the one place they live.

  - The payment section opens only when the lead's Opportunity Status is
    BOOKING DONE, and the lead has a quotation (the total vehicle cost comes
    from the latest quotation's on-road price).
  - The FIRST saved payment creates the booking (booking number
    BK<branch code>-<running number>) and moves the lead to BOOKED
    (leads/stages.py mark_booked: stage history + alerts).
  - Every payment is its own row with its own receipt number
    (<booking no>-R1, -R2 ...). Rows are never edited or deleted.
  - Total paid, outstanding amount and payment status are worked out from
    the rows each time — never stored.
  - A payment can't be more than the outstanding amount, and can't be dated
    in the future.
"""
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func

from app.core.database import now_ist
from app.modules.leads.lookup_names import lookup_key
from app.modules.leads.models import EnquiryStage, Lead
from app.modules.leads.stages import mark_booked
from app.modules.payments.models import (Booking, Payment, PaymentMode,
                                         PaymentStatus)
from app.modules.quotations.models import Quotation, QuotationStatus

TRIGGER_STATUS = "BOOKING DONE"
# modes that need a reference (UTR / UPI id / cheque number / card slip no.)
NEEDS_REFERENCE = (PaymentMode.CHEQUE, PaymentMode.UPI, PaymentMode.BANK_TRANSFER,
                   PaymentMode.CARD)
MODE_LABELS = {
    PaymentMode.CASH: "Cash", PaymentMode.CHEQUE: "Cheque", PaymentMode.UPI: "UPI",
    PaymentMode.BANK_TRANSFER: "NEFT / RTGS / Bank Transfer", PaymentMode.CARD: "Card",
    PaymentMode.FINANCE: "Finance",
}
TWO_DP = Decimal("0.01")


def money(v) -> Decimal:
    return Decimal(str(v or 0)).quantize(TWO_DP)


def latest_quotation(db, lead_id: int) -> Quotation | None:
    """The lead's most recent quotation that hasn't been rejected or expired."""
    return (db.query(Quotation).filter(
        Quotation.lead_id == lead_id,
        Quotation.status.notin_([QuotationStatus.REJECTED, QuotationStatus.EXPIRED]))
        .order_by(Quotation.created_at.desc(), Quotation.quotation_id.desc()).first())


def get_booking(db, lead_id: int) -> Booking | None:
    return db.query(Booking).filter(Booking.lead_id == lead_id).first()


def payment_status(total_cost: Decimal | None, total_paid: Decimal) -> str:
    if total_paid <= 0:
        return PaymentStatus.PENDING.value
    if total_cost is not None and total_paid >= total_cost:
        return PaymentStatus.PAID.value
    return PaymentStatus.PARTIALLY_PAID.value


def _cost(booking: Booking | None, quotation: Quotation | None) -> Decimal | None:
    q = booking.quotation if (booking and booking.quotation) else quotation
    return money(q.on_road_price) if q is not None else None


def blocked_reason(db, lead: Lead, booking: Booking | None, quotation: Quotation | None,
                   outstanding: Decimal | None) -> str | None:
    """Why a payment can't be added right now (None = it can). Shown on screen."""
    if lead.enquiry_stage == EnquiryStage.CLOSED:
        return "This lead is closed. Reopen it before recording a payment."
    if booking is None:
        status = lead.opportunity.name if lead.opportunity else ""
        if lookup_key(status) != lookup_key(TRIGGER_STATUS):
            return f"Set the Opportunity Status to {TRIGGER_STATUS} to start the booking."
        if quotation is None:
            return "Create a quotation first — the total vehicle cost comes from it."
        if lead.enquiry_stage != EnquiryStage.OPEN:
            return "This lead is not open for a new booking."
    if outstanding is not None and outstanding <= 0:
        return "The booking is fully paid."
    return None


def summary(db, lead: Lead) -> dict:
    """Everything the payment section / receipt needs about a lead's booking."""
    booking = get_booking(db, lead.lead_id)
    quotation = latest_quotation(db, lead.lead_id)
    cost = _cost(booking, quotation)
    payments = list(booking.payments) if booking else []
    paid = sum((money(p.amount) for p in payments), Decimal("0.00"))
    outstanding = (cost - paid) if cost is not None else None
    q = booking.quotation if (booking and booking.quotation) else quotation
    return {
        "booking_no": booking.booking_no if booking else None,
        "quotation_no": q.quotation_no if q else None,
        "total_vehicle_cost": cost,
        "total_paid": paid,
        "outstanding": outstanding,
        "payment_status": payment_status(cost, paid),
        "finance": {
            "finance_bank_name": booking.finance_bank_name if booking else None,
            "emi_tenure_months": booking.emi_tenure_months if booking else None,
            "roi_percent": booking.roi_percent if booking else None,
        },
        "can_add_payment": blocked_reason(db, lead, booking, quotation, outstanding) is None,
        "blocked_reason": blocked_reason(db, lead, booking, quotation, outstanding),
        "payments": [{
            "payment_id": p.payment_id, "receipt_no": p.receipt_no, "receipt_seq": p.receipt_seq,
            "payment_date": p.payment_date, "amount": money(p.amount), "mode": p.mode,
            "mode_label": MODE_LABELS.get(PaymentMode(p.mode), p.mode),
            "payment_type": p.payment_type, "reference": p.reference,
            "finance_bank_name": p.finance_bank_name, "remark": p.remark,
            "has_photo": bool(p.photo_stored_path), "recorded_at": p.created_at,
            "agreed_at": p.agreed_at, "has_agree_link": bool(p.agree_token),
            "recorded_by": p.recorded_by.full_name if p.recorded_by else None,
        } for p in payments],
        "modes": [{"value": m.value, "label": MODE_LABELS[m],
                   "needs_reference": m in NEEDS_REFERENCE} for m in PaymentMode],
    }


def _next_booking_no(db, lead: Lead) -> str:
    code = (lead.branch_code or (lead.branch.dealer_code if lead.branch else None) or "NA")
    code = "".join(ch for ch in str(code) if ch.isalnum()).upper() or "NA"
    prefix = f"BK{code}-"
    last = (db.query(func.max(Booking.booking_no))
            .filter(Booking.booking_no.like(prefix + "%")).scalar())
    n = int(last.rsplit("-", 1)[1]) + 1 if last else 1
    return f"{prefix}{n:04d}"


def add_payment(db, lead: Lead, user, *, amount, mode, payment_date=None, reference=None,
                finance_bank_name=None, remark=None) -> Payment:
    """Validate and save one payment (first one also creates the booking and
    marks the lead BOOKED). Does not commit."""
    try:
        mode = PaymentMode(str(mode).upper())
    except ValueError:
        raise HTTPException(400, "Please choose a payment mode from the list")

    booking = get_booking(db, lead.lead_id)
    quotation = latest_quotation(db, lead.lead_id)
    cost = _cost(booking, quotation)
    paid = (sum((money(p.amount) for p in booking.payments), Decimal("0.00"))
            if booking else Decimal("0.00"))
    outstanding = (cost - paid) if cost is not None else None

    reason = blocked_reason(db, lead, booking, quotation, outstanding)
    if reason:
        raise HTTPException(400, reason)

    amount = money(amount)
    if amount <= 0:
        raise HTTPException(400, "Enter the amount received (more than 0)")
    if outstanding is not None and amount > outstanding:
        raise HTTPException(400, f"This is more than the outstanding amount "
                                 f"(₹{outstanding:,.2f})")

    pay_date = payment_date or now_ist().date()
    if pay_date > now_ist().date():
        raise HTTPException(400, "The payment date can't be in the future")

    reference = (reference or "").strip() or None
    if mode in NEEDS_REFERENCE and not reference:
        raise HTTPException(400, "Enter the UTR / transaction / cheque number for this payment")
    bank = (finance_bank_name or "").strip() or None
    if mode == PaymentMode.FINANCE:
        bank = bank or (booking.finance_bank_name if booking else None)
        if not bank:
            raise HTTPException(400, "Enter the finance bank name")

    first = booking is None
    if first:
        booking = Booking(booking_no=_next_booking_no(db, lead), lead_id=lead.lead_id,
                          customer_id=lead.customer_id, branch_id=lead.branch_id,
                          quotation_id=quotation.quotation_id,
                          created_by_user_id=user.user_id)
        db.add(booking)
        db.flush()
    if mode == PaymentMode.FINANCE and bank and not booking.finance_bank_name:
        booking.finance_bank_name = bank

    seq = (max((p.receipt_seq for p in booking.payments), default=0)) + 1
    pay = Payment(booking_id=booking.booking_id, lead_id=lead.lead_id, receipt_seq=seq,
                  payment_date=pay_date, amount=amount, mode=mode.value, reference=reference,
                  finance_bank_name=bank, remark=(remark or "").strip() or None,
                  recorded_by_user_id=user.user_id)
    pay.booking = booking
    db.add(pay)
    db.flush()

    if first:
        mark_booked(db, lead, user.user_id)     # stage -> BOOKED (+ history + alerts)
    return pay
