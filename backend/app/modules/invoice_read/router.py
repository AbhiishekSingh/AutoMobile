"""POST /leads/{id}/invoice/read  - PBA uploads the invoice PDF, gets the fields read out of it plus checks against the CRM.
Nothing is saved here: the PBA reviews the filled form and presses Save as before."""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.modules.handoffs.models import InvoiceDetail
from app.modules.invoice_read import service as svc
from app.modules.users.access import get_visible_lead
from app.modules.users.models import AppUser

router = APIRouter(tags=["invoice-read"])
MAX_BYTES = 5 * 1024 * 1024


@router.post("/leads/{lead_id}/invoice/read", dependencies=[Depends(require_roles("PBA"))])
def read_invoice(lead_id: int, file: UploadFile = File(...), user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    lead = get_visible_lead(db, user, lead_id)
    if not (file.filename or "").lower().endswith(".pdf"):
        return {"readable": False, "message": "Only a PDF invoice can be read automatically. Fill the details by hand."}
    data = file.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(400, "The PDF is larger than 5 MB")
    text = svc.pdf_text(data)
    f = svc.parse(text) if text.strip() else {}
    if not f.get("dealer_invoice") or not (f.get("chassis_no") or f.get("invoice_no")):
        return {"readable": False, "message": "Could not read this PDF (scanned picture or a different format). Fill the details by hand."}
    owner = None
    for col, val in ((InvoiceDetail.chassis_no, f.get("chassis_no")), (InvoiceDetail.engine_no, f.get("engine_no"))):
        if val:
            row = db.query(InvoiceDetail).filter(col == val, InvoiceDetail.lead_id != lead_id).first()
            if row:
                owner = f"enquiry {row.lead_id}"
    f.pop("dealer_invoice", None)
    return {"readable": True, "fields": f, "checks": svc.checks(f, lead, owner),
            "message": "Details read from the invoice. Please check them before saving."}
