"""Admin: create and edit branches (name, dealer code, branch WhatsApp number)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_roles
from app.modules.users.models import AppUser, Branch, Role

router = APIRouter(prefix="/admin/branch-setup", tags=["branches"], dependencies=[Depends(require_roles("ADMIN"))])


class BranchIn(BaseModel):
    name: str
    dealer_code: str | None = None
    city: str | None = None
    address: str | None = None
    contact_no: str | None = None
    whatsapp_number: str | None = None
    is_active: bool = True


def _clean(b: BranchIn) -> dict:
    d = b.model_dump()
    d["name"] = d["name"].strip()
    if not d["name"]:
        raise HTTPException(400, "Enter the branch name")
    for k in ("dealer_code", "city", "address", "contact_no", "whatsapp_number"):
        d[k] = (d[k] or "").strip() or None
    if d["whatsapp_number"] and len("".join(c for c in d["whatsapp_number"] if c.isdigit())) < 10:
        raise HTTPException(400, "The WhatsApp number must have at least 10 digits")
    return d


def _out(db, b: Branch):
    login = db.query(AppUser).filter(AppUser.role == Role.BRANCH, AppUser.branch_id == b.branch_id, AppUser.is_active == True).first()  # noqa: E712
    pbas = db.query(AppUser).filter(AppUser.role == Role.PBA, AppUser.branch_id == b.branch_id, AppUser.is_active == True).all()  # noqa: E712
    return {"branch_id": b.branch_id, "name": b.name, "dealer_code": b.dealer_code, "city": b.city, "address": b.address,
            "contact_no": b.contact_no, "whatsapp_number": b.whatsapp_number, "is_active": b.is_active,
            "branch_login": login.login_id if login else None,
            "pbas": [{"user_id": p.user_id, "full_name": p.full_name, "login_enabled": p.login_enabled, "has_pin": p.has_pin} for p in pbas]}


@router.get("")
def list_branches(db: Session = Depends(get_db)):
    return [_out(db, b) for b in db.query(Branch).order_by(Branch.name).all()]


@router.post("", status_code=201)
def create_branch(body: BranchIn, db: Session = Depends(get_db)):
    d = _clean(body)
    if d["dealer_code"] and db.query(Branch).filter(Branch.dealer_code == d["dealer_code"]).first():
        raise HTTPException(409, "This branch code is already used")
    b = Branch(**d); db.add(b); db.commit(); db.refresh(b)
    return _out(db, b)


@router.put("/{branch_id}")
def update_branch(branch_id: int, body: BranchIn, db: Session = Depends(get_db)):
    b = db.get(Branch, branch_id)
    if not b:
        raise HTTPException(404, "Branch not found")
    d = _clean(body)
    if d["dealer_code"] and db.query(Branch).filter(Branch.dealer_code == d["dealer_code"], Branch.branch_id != branch_id).first():
        raise HTTPException(409, "This branch code is already used")
    for k, v in d.items():
        setattr(b, k, v)
    db.commit(); db.refresh(b)
    return _out(db, b)
