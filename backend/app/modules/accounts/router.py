"""Accounts section (Owner / GM / Admin).

  GET  /accounts/summary                  headline numbers
  GET  /accounts/payments                 every customer payment + bank-reconciliation state
  POST /accounts/payments/reconcile       mark payments Reconciled (ids, bank_ref)   |  DELETE .../{id}/reconcile  to undo
  GET/POST/PATCH /accounts/bills          payables (vendor bills);  POST /accounts/bills/{id}/pay
  GET  /accounts/cancellations            cancelled bookings + refund state;  PUT /accounts/cancellations/{lead_id}/refund
  GET  /accounts/customers  (+ /{lead_id})  customer-wise price breakup and payments
Every change is written to the audit log with the user and time.
"""
from datetime import date
from types import SimpleNamespace
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db, now_ist
from app.core.deps import get_current_user, require_roles
from app.modules.accounts import service as svc
from app.modules.accounts.models import PaymentRecon, Refund, VendorBill
from app.modules.audit.service import record_changes
from app.modules.leads.models import Lead
from app.modules.owner.service import sales_snapshot
from app.modules.payments.models import Booking, Payment
from app.modules.payments.service import MODE_LABELS, latest_quotation, money
from app.modules.users.models import AppUser, Branch

ROLES = ("OWNER", "GM", "ADMIN")
router = APIRouter(prefix="/accounts", tags=["accounts"], dependencies=[Depends(require_roles(*ROLES))])


def _f(v): return float(v) if v is not None else None


@router.get("/summary")
def summary(branch_id: Optional[int] = None, db: Session = Depends(get_db)):
    snap = sales_snapshot(db, branch_id)
    cost = sum((r["cost"] or 0) for r in snap); paid = sum(r["paid"] for r in snap)
    out = sum(r["outstanding"] for r in snap)
    today = date.today()
    cq = db.query(func.coalesce(func.sum(Payment.amount), 0)).join(Booking, Booking.booking_id == Payment.booking_id)
    if branch_id: cq = cq.filter(Booking.branch_id == branch_id)
    day = cq.filter(Payment.payment_date == today).scalar()
    month = cq.filter(func.extract("year", Payment.payment_date) == today.year, func.extract("month", Payment.payment_date) == today.month).scalar()
    t = svc.all_totals(db, branch_id)
    return {**t, "booked_value": _f(cost), "received": _f(paid), "receivable": _f(out), "collection_today": _f(day), "collection_month": _f(month),
            "status_counts": {k: sum(1 for r in snap if r["pay_status"] == k) for k in ("PAID", "PARTIALLY_PAID", "PENDING")},
            "branches": [{"id": b.branch_id, "name": b.name} for b in db.query(Branch).order_by(Branch.name).all()]}


# ---------- payments + reconciliation ----------
@router.get("/payments")
def payments(branch_id: Optional[int] = None, date_from: Optional[date] = None, date_to: Optional[date] = None,
             mode: Optional[str] = None, recon: Optional[str] = None, q: Optional[str] = None, db: Session = Depends(get_db)):
    qq = (db.query(Payment, Booking, Lead, PaymentRecon).join(Booking, Booking.booking_id == Payment.booking_id)
          .join(Lead, Lead.lead_id == Payment.lead_id).outerjoin(PaymentRecon, PaymentRecon.payment_id == Payment.payment_id))
    if branch_id: qq = qq.filter(Booking.branch_id == branch_id)
    if date_from: qq = qq.filter(Payment.payment_date >= date_from)
    if date_to: qq = qq.filter(Payment.payment_date <= date_to)
    if mode: qq = qq.filter(Payment.mode == mode)
    if recon == "RECONCILED": qq = qq.filter(PaymentRecon.id.isnot(None))
    if recon == "PENDING": qq = qq.filter(PaymentRecon.id.is_(None))
    bn = {b.branch_id: b.name for b in db.query(Branch).all()}
    out = []
    for p, bk, l, rc in qq.order_by(Payment.payment_date.desc(), Payment.payment_id.desc()).limit(1000).all():
        row = {"payment_id": p.payment_id, "receipt_no": p.receipt_no, "payment_date": p.payment_date, "amount": _f(money(p.amount)),
               "mode": p.mode, "mode_label": MODE_LABELS.get(p.mode, p.mode), "reference": p.reference, "booking_no": bk.booking_no,
               "customer": l.customer.full_name, "lead_id": l.lead_id, "branch": bn.get(bk.branch_id),
               "reconciled": bool(rc), "bank_ref": rc.bank_ref if rc else None, "reconciled_at": rc.reconciled_at if rc else None,
               "reconciled_by": rc.reconciled_by.full_name if rc and rc.reconciled_by else None}
        if q and q.lower() not in " ".join(str(row[k] or "") for k in ("receipt_no", "customer", "booking_no", "reference")).lower(): continue
        out.append(row)
    return out


class ReconIn(BaseModel):
    payment_ids: list[int]
    bank_ref: Optional[str] = None
    note: Optional[str] = None


@router.post("/payments/reconcile")
def reconcile(body: ReconIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    if not body.payment_ids: raise HTTPException(400, "Select at least one payment")
    n = 0
    for pid in dict.fromkeys(body.payment_ids):
        if not db.get(Payment, pid): raise HTTPException(404, f"Payment {pid} not found")
        if db.query(PaymentRecon).filter(PaymentRecon.payment_id == pid).first(): continue
        rc = PaymentRecon(payment_id=pid, bank_ref=(body.bank_ref or "").strip() or None, note=(body.note or "").strip() or None,
                          reconciled_by_user_id=user.user_id)
        db.add(rc); db.flush()
        record_changes(db, entity_type="payment_recon", entity_id=pid, before={"status": "PENDING"}, after=SimpleNamespace(status="RECONCILED"),
                       fields=("status",), changed_by_user_id=user.user_id)
        n += 1
    db.commit()
    return {"reconciled": n}


@router.delete("/payments/{payment_id}/reconcile")
def unreconcile(payment_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    rc = db.query(PaymentRecon).filter(PaymentRecon.payment_id == payment_id).first()
    if not rc: raise HTTPException(404, "This payment is not reconciled")
    db.delete(rc)
    record_changes(db, entity_type="payment_recon", entity_id=payment_id, before={"status": "RECONCILED"}, after=SimpleNamespace(status="PENDING"),
                   fields=("status",), changed_by_user_id=user.user_id)
    db.commit()
    return {"ok": True}


# ---------- payables ----------
class BillIn(BaseModel):
    vendor: Optional[str] = None
    category: Optional[str] = None
    branch_id: Optional[int] = None
    bill_no: Optional[str] = None
    bill_date: Optional[date] = None
    due_date: Optional[date] = None
    amount: Optional[Decimal] = None
    note: Optional[str] = None


class PayIn(BaseModel):
    paid_date: Optional[date] = None
    paid_mode: str
    paid_ref: Optional[str] = None


def _bill(b: VendorBill) -> dict:
    return {"id": b.id, "vendor": b.vendor, "category": b.category, "category_label": svc.BILL_CATEGORIES.get(b.category, b.category),
            "branch_id": b.branch_id, "branch": b.branch.name if b.branch else "All / head office", "bill_no": b.bill_no,
            "bill_date": b.bill_date, "due_date": b.due_date, "amount": _f(b.amount), "status": b.status,
            "overdue": bool(b.status == "PENDING" and b.due_date and b.due_date < date.today()),
            "paid_date": b.paid_date, "paid_mode": b.paid_mode, "paid_ref": b.paid_ref, "note": b.note}


@router.get("/bills")
def bills(status: Optional[str] = None, branch_id: Optional[int] = None, category: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(VendorBill)
    if status: q = q.filter(VendorBill.status == status)
    if branch_id: q = q.filter(VendorBill.branch_id == branch_id)
    if category: q = q.filter(VendorBill.category == category)
    return {"bills": [_bill(b) for b in q.order_by(VendorBill.status.desc(), VendorBill.due_date.asc().nullslast(), VendorBill.id.desc()).all()],
            "categories": [{"value": k, "label": v} for k, v in svc.BILL_CATEGORIES.items()], "modes": list(svc.PAY_MODES),
            **svc.payables_totals(db, branch_id)}


def _check_bill(d: dict, creating: bool):
    if creating:
        for k, label in (("vendor", "Vendor name"), ("bill_date", "Bill date"), ("amount", "Amount")):
            if not d.get(k): raise HTTPException(400, f"{label} is required")
    if d.get("amount") is not None and d["amount"] <= 0: raise HTTPException(400, "Amount must be more than zero")
    if d.get("category") and d["category"] not in svc.BILL_CATEGORIES: raise HTTPException(400, "Unknown category")
    if d.get("due_date") and d.get("bill_date") and d["due_date"] < d["bill_date"]: raise HTTPException(400, "Due date is before the bill date")


@router.post("/bills", status_code=201)
def add_bill(body: BillIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    d = body.model_dump(exclude_unset=True); _check_bill(d, True)
    b = VendorBill(**{k: (v.strip() or None) if isinstance(v, str) else v for k, v in d.items()}, status="PENDING",
                   created_by_user_id=user.user_id, updated_by_user_id=user.user_id)
    b.category = b.category or "OTHER"
    db.add(b); db.flush()
    record_changes(db, entity_type="vendor_bill", entity_id=b.id, before={"amount": None}, after=SimpleNamespace(amount=b.amount), fields=("amount",), changed_by_user_id=user.user_id)
    db.commit()
    return _bill(b)


@router.patch("/bills/{bill_id}")
def edit_bill(bill_id: int, body: BillIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    b = db.get(VendorBill, bill_id)
    if not b: raise HTTPException(404, "Bill not found")
    if b.status == "PAID": raise HTTPException(400, "A paid bill cannot be edited")
    d = body.model_dump(exclude_unset=True)
    _check_bill({**{"bill_date": b.bill_date, "due_date": b.due_date}, **d}, False)
    before = {k: getattr(b, k) for k in d}
    for k, v in d.items(): setattr(b, k, (v.strip() or None) if isinstance(v, str) else v)
    b.updated_by_user_id = user.user_id
    record_changes(db, entity_type="vendor_bill", entity_id=b.id, before=before, after=b, fields=tuple(d), changed_by_user_id=user.user_id)
    db.commit()
    return _bill(b)


@router.post("/bills/{bill_id}/pay")
def pay_bill(bill_id: int, body: PayIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    b = db.get(VendorBill, bill_id)
    if not b: raise HTTPException(404, "Bill not found")
    if b.status == "PAID": raise HTTPException(400, "This bill is already paid")
    if body.paid_mode not in svc.PAY_MODES: raise HTTPException(400, "Choose how it was paid")
    pd = body.paid_date or date.today()
    if pd > date.today(): raise HTTPException(400, "Paid date cannot be in the future")
    b.status, b.paid_date, b.paid_mode, b.paid_ref = "PAID", pd, body.paid_mode, (body.paid_ref or "").strip() or None
    b.updated_by_user_id = user.user_id
    record_changes(db, entity_type="vendor_bill", entity_id=b.id, before={"status": "PENDING"}, after=b, fields=("status",), changed_by_user_id=user.user_id)
    db.commit()
    return _bill(b)


# ---------- cancellations + refunds ----------
class RefundIn(BaseModel):
    amount: Decimal
    status: str = "PENDING"
    processed_date: Optional[date] = None
    mode: Optional[str] = None
    reference: Optional[str] = None
    note: Optional[str] = None


@router.get("/cancellations")
def cancellations(branch_id: Optional[int] = None, db: Session = Depends(get_db)):
    bn = {b.branch_id: b.name for b in db.query(Branch).all()}
    out = []
    for l, bk, rec, rf in svc.cancelled_rows(db, branch_id):
        out.append({"lead_id": l.lead_id, "booking_no": bk.booking_no, "customer": l.customer.full_name, "branch": bn.get(l.branch_id),
                    "received": _f(rec), "refund_amount": _f(rf.amount) if rf else None,
                    "refund_status": rf.status if rf else ("NOT_SET" if rec > 0 else "NOTHING_TO_REFUND"),
                    "processed_date": rf.processed_date if rf else None, "mode": rf.mode if rf else None,
                    "reference": rf.reference if rf else None, "note": rf.note if rf else None})
    return {"rows": out, "modes": list(svc.PAY_MODES), **svc.refund_totals(db, branch_id)}


@router.put("/cancellations/{lead_id}/refund")
def set_refund(lead_id: int, body: RefundIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    row = next((r for r in svc.cancelled_rows(db) if r[0].lead_id == lead_id), None)
    if not row: raise HTTPException(404, "This is not a cancelled booking")
    _, _, received, rf = row
    if body.status not in ("PENDING", "PROCESSED"): raise HTTPException(400, "Unknown refund status")
    if body.amount <= 0 or body.amount > received: raise HTTPException(400, f"Refund must be more than 0 and at most the amount received (Rs {received:,.0f})")
    if body.status == "PROCESSED":
        if not body.mode or body.mode not in svc.PAY_MODES: raise HTTPException(400, "Choose how the refund was paid")
        if body.processed_date and body.processed_date > date.today(): raise HTTPException(400, "Refund date cannot be in the future")
    if rf and rf.status == "PROCESSED": raise HTTPException(400, "This refund is already processed")
    before = {"status": rf.status if rf else None, "amount": rf.amount if rf else None}
    if not rf:
        rf = Refund(lead_id=lead_id, amount=body.amount, created_by_user_id=user.user_id); db.add(rf)
    rf.amount, rf.status, rf.note = body.amount, body.status, (body.note or "").strip() or None
    rf.mode, rf.reference = (body.mode if body.status == "PROCESSED" else None), (body.reference or "").strip() or None
    rf.processed_date = (body.processed_date or date.today()) if body.status == "PROCESSED" else None
    rf.updated_by_user_id = user.user_id
    db.flush()
    record_changes(db, entity_type="refund", entity_id=rf.id, before=before, after=rf, fields=("status", "amount"), changed_by_user_id=user.user_id)
    db.commit()
    return {"ok": True}


# ---------- customer-wise ----------
def _breakup(db, lead, bk, cost, paid):
    q = bk.quotation if bk.quotation else latest_quotation(db, lead.lead_id)
    disc = money(q.on_road_price) - money(q.discounted_price) if q and q.discounted_price else Decimal(0)
    return {"on_road_price": _f(money(q.on_road_price)) if q else None, "discount": _f(disc) if disc > 0 else 0,
            "payable": _f(cost), "paid": _f(paid), "outstanding": _f((cost - paid) if cost is not None else None),
            "payment_type": q.payment_type if q else None, "down_payment": _f(q.down_payment) if q and q.down_payment else None,
            "finance_bank": bk.finance_bank_name, "quotation_no": q.quotation_no if q else None}


@router.get("/customers")
def customers(branch_id: Optional[int] = None, status: Optional[str] = None, q: Optional[str] = None, db: Session = Depends(get_db)):
    bn = {b.branch_id: b.name for b in db.query(Branch).all()}
    out = []
    for r in sales_snapshot(db, branch_id):
        l = r["lead"]
        if status and r["pay_status"] != status: continue
        row = {"lead_id": l.lead_id, "booking_no": r["booking"].booking_no, "customer": l.customer.full_name, "mobile": l.customer.phone,
               "branch": bn.get(l.branch_id), "stage": r["stage"].value, "cost": _f(r["cost"]), "paid": _f(r["paid"]),
               "outstanding": _f(r["outstanding"]), "pay_status": r["pay_status"]}
        if q and q.lower() not in " ".join(str(row[k] or "") for k in ("customer", "mobile", "booking_no")).lower(): continue
        out.append(row)
    out.sort(key=lambda x: -(x["outstanding"] or 0))
    return out


@router.get("/customers/{lead_id}")
def customer_detail(lead_id: int, db: Session = Depends(get_db)):
    lead = db.get(Lead, lead_id)
    bk = db.query(Booking).filter(Booking.lead_id == lead_id).first()
    if not lead or not bk: raise HTTPException(404, "No booking for this customer")
    r = next((x for x in sales_snapshot(db) if x["lead"].lead_id == lead_id), None)
    cost = r["cost"] if r else None; paid = r["paid"] if r else money(sum(money(p.amount) for p in bk.payments))
    rc = {x.payment_id: x for x in db.query(PaymentRecon).filter(PaymentRecon.payment_id.in_([p.payment_id for p in bk.payments] or [-1])).all()}
    return {"lead_id": lead_id, "customer": lead.customer.full_name, "mobile": lead.customer.phone, "booking_no": bk.booking_no,
            "stage": lead.enquiry_stage.value, **_breakup(db, lead, bk, cost, paid),
            "payments": [{"receipt_no": p.receipt_no, "payment_date": p.payment_date, "amount": _f(money(p.amount)), "mode": MODE_LABELS.get(p.mode, p.mode),
                          "reference": p.reference, "reconciled": p.payment_id in rc} for p in bk.payments]}
