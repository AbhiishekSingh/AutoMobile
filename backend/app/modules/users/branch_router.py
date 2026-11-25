"""Admin: create and edit branches (name, dealer code, branch WhatsApp number)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from sqlalchemy import func
from app.core.deps import get_current_user, require_roles
from app.modules.users.models import AppUser, Branch, Department, Role

router = APIRouter(prefix="/admin/branch-setup", tags=["branches"], dependencies=[Depends(require_roles("ADMIN", "OWNER"))])


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


def _guard_member(actor, user):
    if user.role == Role.ADMIN and actor.role != Role.ADMIN:
        raise HTTPException(403, "Only an Admin can change an Admin account")


def _member(u, names):
    return {"user_id": u.user_id, "full_name": u.full_name, "login_id": u.login_id, "role": u.role.value,
            "is_active": bool(u.is_active), "login_enabled": u.login_enabled,
            "branches": [names.get(i, str(i)) for i in (u.branch_ids if u.role == Role.CRE else ([u.branch_id] if u.branch_id else []))]}


class DeptIn(BaseModel):
    name: str
    description: str | None = None
    head_user_id: int | None = None


def _check_dept(db, body: DeptIn, dept_id=None):
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "Enter the department name")
    q = db.query(Department).filter(Department.name.ilike(name))
    if dept_id:
        q = q.filter(Department.id != dept_id)
    if q.first():
        raise HTTPException(409, "A department with this name already exists")
    if body.head_user_id:
        h = db.get(AppUser, body.head_user_id)
        if not h or not h.is_active:
            raise HTTPException(400, "Choose an active user as the head")
    return name, (body.description or "").strip() or None


@router.get("/departments")
def departments(db: Session = Depends(get_db)):
    """Departments with their head and members, plus everyone (so people can be assigned)."""
    names = {b.branch_id: b.name for b in db.query(Branch).all()}
    users = db.query(AppUser).order_by(AppUser.full_name).all()
    out = []
    for d in db.query(Department).order_by(Department.is_active.desc(), Department.sort_order, Department.name).all():
        mem = [u for u in users if u.department_id == d.id]
        head = next((u for u in users if u.user_id == d.head_user_id), None)
        out.append({"id": d.id, "name": d.name, "description": d.description, "is_active": d.is_active,
                    "head_user_id": d.head_user_id, "head_name": head.full_name if head else None,
                    "active": sum(1 for u in mem if u.is_active), "total": len(mem),
                    "members": [_member(u, names) for u in mem]})
    people = [{"user_id": u.user_id, "full_name": u.full_name, "role": u.role.value, "is_active": bool(u.is_active),
               "department_id": u.department_id} for u in users]
    return {"departments": out, "people": people}


@router.post("/departments", status_code=201)
def create_department(body: DeptIn, db: Session = Depends(get_db)):
    name, about = _check_dept(db, body)
    d = Department(name=name, description=about, head_user_id=body.head_user_id,
                   sort_order=(db.query(func.max(Department.sort_order)).scalar() or 0) + 10)
    db.add(d); db.commit()
    return {"id": d.id}


@router.put("/departments/{dept_id}")
def update_department(dept_id: int, body: DeptIn, db: Session = Depends(get_db)):
    d = db.get(Department, dept_id)
    if not d:
        raise HTTPException(404, "Department not found")
    d.name, d.description = _check_dept(db, body, dept_id)
    d.head_user_id = body.head_user_id
    db.commit()
    return {"ok": True}


@router.post("/departments/{dept_id}/deactivate")
def deactivate_department(dept_id: int, db: Session = Depends(get_db)):
    d = db.get(Department, dept_id)
    if not d:
        raise HTTPException(404, "Department not found")
    n = db.query(AppUser).filter(AppUser.department_id == d.id, AppUser.is_active == True).count()  # noqa: E712
    if n:
        raise HTTPException(400, f"Move the {n} active member(s) to another department first")
    d.is_active = False
    d.head_user_id = None
    db.commit()
    return {"ok": True}


@router.post("/departments/{dept_id}/activate")
def activate_department(dept_id: int, db: Session = Depends(get_db)):
    d = db.get(Department, dept_id)
    if not d:
        raise HTTPException(404, "Department not found")
    d.is_active = True
    db.commit()
    return {"ok": True}


class AssignIn(BaseModel):
    user_id: int
    department_id: int | None = None


@router.post("/departments/assign")
def assign(body: AssignIn, actor: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    u = db.get(AppUser, body.user_id)
    if not u:
        raise HTTPException(404, "User not found")
    _guard_member(actor, u)
    if body.department_id:
        d = db.get(Department, body.department_id)
        if not d or not d.is_active:
            raise HTTPException(400, "Choose an active department")
    old = u.department_id
    u.department_id = body.department_id
    if old and old != body.department_id:      # a head who moves out is no longer head of the old team
        od = db.get(Department, old)
        if od and od.head_user_id == u.user_id:
            od.head_user_id = None
    db.commit()
    return {"ok": True}


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
