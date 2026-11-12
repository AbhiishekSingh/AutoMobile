"""Builds one receipt's PDF bytes from a Payment row (shared by the staff and customer routes)."""
from app.modules.payments import receipt_pdf
from app.modules.payments import service as svc


def receipt_bytes(db, pay, lang: str):
    lead = pay.booking.lead
    summ = svc.summary(db, lead)
    entry = next(p for p in summ["payments"] if p["payment_id"] == pay.payment_id)
    model = getattr(lead, "model", None)
    vehicle = " ".join(x for x in [getattr(model, "name", None), lead.color] if x)
    data = receipt_pdf.build_receipt(lang=lang, branch=lead.branch, customer_name=lead.customer.full_name,
                                     mobile=lead.customer.phone, vehicle=vehicle, summary=summ, payment=entry)
    return data, entry, summ
