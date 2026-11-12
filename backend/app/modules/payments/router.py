"""Booking & payment endpoints.

  GET   /leads/{lead_id}/booking           booking summary: totals, status, payments
  POST  /leads/{lead_id}/payments          record one payment (PBA)
  PATCH /leads/{lead_id}/booking/finance   bank / EMI tenure / ROI (PBA)
  POST  /payments/{payment_id}/photo       attach a photo of the transaction (PBA)
  GET   /payments/{payment_id}/photo       view / download that photo

Who can see a booking follows the normal lead rule (users/access.py).
Only a PBA records payments.
"""
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.modules.audit.service import record_changes
from app.modules.documents import service as docs
from app.modules.payments import receipt_pdf
from app.modules.payments import service as svc
from app.modules.payments.models import Payment
from app.modules.payments.schemas import FinanceUpdate, PaymentCreate
from app.modules.users.access import MANAGER_ROLES, SALES_ROLES, get_visible_lead
from app.modules.users.models import AppUser

router = APIRouter(tags=["payments"])
READ_ROLES = SALES_ROLES + MANAGER_ROLES
WRITE_ROLES = ("PBA",)


@router.get("/leads/{lead_id}/booking", dependencies=[Depends(require_roles(*READ_ROLES))])
def get_booking_summary(lead_id: int, user: AppUser = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    lead = get_visible_lead(db, user, lead_id)
    return svc.summary(db, lead)


@router.post("/leads/{lead_id}/payments", status_code=201,
             dependencies=[Depends(require_roles(*WRITE_ROLES))])
def add_payment(lead_id: int, body: PaymentCreate, user: AppUser = Depends(get_current_user),
                db: Session = Depends(get_db)):
    lead = get_visible_lead(db, user, lead_id)
    pay = svc.add_payment(db, lead, user, amount=body.amount, mode=body.mode,
                          payment_date=body.payment_date, reference=body.reference,
                          finance_bank_name=body.finance_bank_name, remark=body.remark)
    record_changes(db, entity_type="payment", entity_id=pay.payment_id,
                   before={"amount": None, "mode": None}, after=pay,
                   fields=("amount", "mode"), changed_by_user_id=user.user_id)
    db.commit()
    db.refresh(lead)
    out = svc.summary(db, lead)
    out["new_payment_id"] = pay.payment_id
    return out


@router.patch("/leads/{lead_id}/booking/finance",
              dependencies=[Depends(require_roles(*WRITE_ROLES))])
def update_finance(lead_id: int, body: FinanceUpdate, user: AppUser = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    lead = get_visible_lead(db, user, lead_id)
    booking = svc.get_booking(db, lead_id)
    if not booking:
        raise HTTPException(400, "Record the first payment before choosing a finance plan")
    data = body.model_dump(exclude_unset=True)
    if data.get("emi_tenure_months") is not None and data["emi_tenure_months"] <= 0:
        raise HTTPException(400, "Tenure must be more than 0 months")
    if data.get("roi_percent") is not None and not (0 <= data["roi_percent"] <= 100):
        raise HTTPException(400, "ROI must be between 0 and 100")
    fields = ("finance_bank_name", "emi_tenure_months", "roi_percent")
    before = {f: getattr(booking, f) for f in fields}
    for f in fields:
        if f in data:
            v = data[f]
            setattr(booking, f, (v.strip() or None) if isinstance(v, str) else v)
    record_changes(db, entity_type="booking", entity_id=booking.booking_id, before=before,
                   after=booking, fields=fields, changed_by_user_id=user.user_id)
    db.commit()
    return svc.summary(db, lead)


def _visible_payment(db: Session, user: AppUser, payment_id: int) -> Payment:
    pay = db.get(Payment, payment_id)
    if not pay:
        raise HTTPException(404, "Payment not found")
    get_visible_lead(db, user, pay.lead_id)      # 404 if this user can't see the lead
    return pay


@router.post("/payments/{payment_id}/photo", dependencies=[Depends(require_roles(*WRITE_ROLES))])
def upload_payment_photo(payment_id: int, file: UploadFile = File(...),
                         user: AppUser = Depends(get_current_user),
                         db: Session = Depends(get_db)):
    pay = _visible_payment(db, user, payment_id)
    lead = get_visible_lead(db, user, pay.lead_id)
    saved = docs.save_upload(file, lead.customer_id)   # same size / type checks as KYC files
    old = pay.photo_stored_path
    pay.photo_original_name = saved["original_name"]
    pay.photo_stored_path = saved["stored_path"]
    pay.photo_content_type = saved["content_type"]
    pay.photo_size_bytes = saved["size_bytes"]
    try:
        db.commit()
    except Exception:
        db.rollback()
        docs.delete_file(saved["stored_path"])
        raise
    if old:
        docs.delete_file(old)
    return {"ok": True, "has_photo": True}


@router.get("/payments/{payment_id}/photo", dependencies=[Depends(require_roles(*READ_ROLES))])
def get_payment_photo(payment_id: int, download: bool = False,
                      user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    pay = _visible_payment(db, user, payment_id)
    if not pay.photo_stored_path:
        raise HTTPException(404, "No photo attached to this payment")
    return FileResponse(docs.full_path_of(pay.photo_stored_path), media_type=pay.photo_content_type,
                        filename=pay.photo_original_name,
                        content_disposition_type="attachment" if download else "inline")


@router.get("/payments/{payment_id}/receipt.pdf",
            dependencies=[Depends(require_roles(*READ_ROLES))])
def download_receipt(payment_id: int, lang: str = Query("en", pattern="^(en|mr)$"),
                     user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """Receipt PDF for one payment, in English (en) or Marathi (mr)."""
    pay = db.get(Payment, payment_id)
    if not pay:
        raise HTTPException(404, "Payment not found")
    lead = get_visible_lead(db, user, pay.lead_id)      # same visibility as the lead itself
    if lang == "mr" and not receipt_pdf.marathi_ready():
        raise HTTPException(503, "Marathi receipts are not set up on this server yet "
                                 "(needs uharfbuzz and a Devanagari font). Use English for now.")
    summ = svc.summary(db, lead)
    entry = next(p for p in summ["payments"] if p["payment_id"] == payment_id)
    model = getattr(lead, "model", None)
    vehicle = " ".join(x for x in [getattr(model, "name", None), lead.color] if x)
    data = receipt_pdf.build_receipt(lang=lang, branch=lead.branch,
                                     customer_name=lead.customer.full_name,
                                     mobile=lead.customer.phone, vehicle=vehicle,
                                     summary=summ, payment=entry)
    return Response(data, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{entry["receipt_no"]}-{lang}.pdf"'})


@router.get("/payments/receipt-languages", dependencies=[Depends(require_roles(*READ_ROLES))])
def receipt_languages():
    return {"en": True, "mr": receipt_pdf.marathi_ready()}
