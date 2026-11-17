"""RTO document checklist.
  GET   /rto-docs/{lead_id}            checklist + residence / rent option / Aadhaar-mobile confirmation
  PATCH /rto-docs/{lead_id}            save residence, rent option, Aadhaar-linked mobile
  POST  /rto-docs/{lead_id}/documents  upload one paper (PDF only, max 100 KB; replaces the earlier one of that type)
"""
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.modules.documents import service as docs
from app.modules.documents.models import CustomerDocument
from app.modules.handoffs.models import RtoCase
from app.modules.leads.models import Lead
from app.modules.rto_docs import service as svc
from app.modules.rto_docs.models import RtoDocProfile
from app.modules.users.access import get_visible_lead
from app.modules.users.models import AppUser

router = APIRouter(tags=["rto-docs"])
ROLES = ("PBA", "CRE", "RTO", "OWNER", "GM", "ADMIN")
WRITE = ("PBA", "CRE", "RTO", "ADMIN")


def _lead(db, user, lead_id) -> Lead:
    if user.role.value == "RTO":
        lead = db.get(Lead, lead_id)
        if not lead or not db.query(RtoCase).filter(RtoCase.lead_id == lead_id).first():
            raise HTTPException(404, "Lead not found")
        return lead
    return get_visible_lead(db, user, lead_id)


def _profile(db, lead_id, create=False):
    p = db.query(RtoDocProfile).filter(RtoDocProfile.lead_id == lead_id).first()
    if not p and create:
        p = RtoDocProfile(lead_id=lead_id); db.add(p)
    return p


def _state(db, lead_id):
    p = _profile(db, lead_id)
    return {"residence": p.residence if p else None, "rent_option": p.rent_option if p else None,
            "aadhaar_mobile_linked": bool(p and p.aadhaar_mobile_linked), "max_kb": svc.MAX_KB,
            "checklist": svc.checklist(db, lead_id, p), "missing": svc.missing(db, lead_id, p), "status": svc.status(db, lead_id, p)}


@router.get("/rto-docs/{lead_id}", dependencies=[Depends(require_roles(*ROLES))])
def get_state(lead_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    _lead(db, user, lead_id)
    return _state(db, lead_id)


class ProfileIn(BaseModel):
    residence: Optional[str] = None
    rent_option: Optional[str] = None
    aadhaar_mobile_linked: Optional[bool] = None


@router.patch("/rto-docs/{lead_id}", dependencies=[Depends(require_roles(*WRITE))])
def save_profile(lead_id: int, body: ProfileIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    _lead(db, user, lead_id)
    data = body.model_dump(exclude_unset=True)
    if data.get("residence") not in (None, "OWN", "RENTED"):
        raise HTTPException(400, "Residence must be Own or Rented")
    if data.get("rent_option") not in (None, "REGISTERED", "NOTARIZED"):
        raise HTTPException(400, "Rent agreement must be Registered or Notarized")
    p = _profile(db, lead_id, create=True)
    for k, v in data.items():
        setattr(p, k, v)
    if p.residence != "RENTED":
        p.rent_option = None
    p.updated_by_user_id = user.user_id
    db.commit()
    return _state(db, lead_id)


@router.post("/rto-docs/{lead_id}/documents", status_code=201, dependencies=[Depends(require_roles(*WRITE))])
def upload(lead_id: int, doc_type: str = Form(...), file: UploadFile = File(...),
           user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    lead = _lead(db, user, lead_id)
    p = _profile(db, lead_id)
    if doc_type not in svc.required(p):
        raise HTTPException(400, "This paper is not on the checklist for this customer")
    saved = docs.save_upload(file, lead.customer_id, limit_bytes=svc.MAX_KB * 1024, pdf_only=True)
    old = db.query(CustomerDocument).filter(CustomerDocument.lead_id == lead_id, CustomerDocument.doc_type == doc_type).all()
    try:
        db.add(CustomerDocument(lead_id=lead_id, customer_id=lead.customer_id, doc_type=doc_type,
                                uploaded_by_user_id=user.user_id, **saved))
        paths = [o.stored_path for o in old]
        for o in old:
            db.delete(o)
        db.commit()
    except Exception:
        db.rollback(); docs.delete_file(saved["stored_path"]); raise
    for pth in paths:
        docs.delete_file(pth)
    return _state(db, lead_id)
