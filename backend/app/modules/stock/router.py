from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_roles
from app.modules.leads.models import EnquiryStage, Lead
from app.modules.stock import service as svc
from app.modules.stock.models import StockItem, StockKind, StockMovement
from app.modules.users.models import AppUser, Role

router = APIRouter(tags=["stock"])
MANAGE = ("OWNER", "ADMIN")
VIEW_ALL = ("OWNER", "GM", "ADMIN")


class ItemIn(BaseModel):
    kind: str
    name: str
    variant: str = ""
    color: str = ""


class MoveIn(BaseModel):
    item_id: int
    move_type: str
    from_branch_id: int | None = None
    to_branch_id: int | None = None
    qty: int | None = None
    counted_qty: int | None = None
    reference: str | None = None
    received_by: str | None = None
    note: str | None = None


def _my_branches(user):
    ids = list(user.branch_ids or [])
    if user.branch_id and user.branch_id not in ids:
        ids.append(user.branch_id)
    return ids


@router.get("/stock/summary")
def stock_summary(branch_id: int | None = None, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role.value in VIEW_ALL:
        out = svc.summary(db, [branch_id] if branch_id else None)
        flow = dict(db.query(Lead.enquiry_stage, func.count(Lead.lead_id))
                    .filter(Lead.enquiry_stage.in_([EnquiryStage.BOOKED, EnquiryStage.INSURANCE_DONE, EnquiryStage.RTO_DONE,
                                                    EnquiryStage.INVOICED, EnquiryStage.DELIVERED]))
                    .group_by(Lead.enquiry_stage).all()) if not branch_id else {}
        g = lambda *s: sum(v for k, v in flow.items() if (k.value if hasattr(k, "value") else k) in s)
        out["vehicle_flow"] = {"booked": g("BOOKED", "INSURANCE_DONE", "RTO_DONE"), "invoiced": g("INVOICED"),
                               "delivered": g("DELIVERED")}
        out["can_manage"] = user.role.value in MANAGE
        out["can_record"] = user.role.value in MANAGE or user.role == Role.GM
        return out
    mine = _my_branches(user)
    if user.role.value not in ("PBA", "CRE"):
        raise HTTPException(403, "Insufficient permissions")
    if branch_id:
        if branch_id not in mine:
            raise HTTPException(403, "You don't have access to this branch")
        mine = [branch_id]
    out = svc.summary(db, mine)
    out["can_manage"] = out["can_record"] = False
    return out


@router.get("/stock/items", dependencies=[Depends(require_roles(*VIEW_ALL))])
def items(db: Session = Depends(get_db)):
    return [svc.item_dict(i) for i in db.query(StockItem).filter(StockItem.is_active == True)  # noqa: E712
            .order_by(StockItem.kind, StockItem.name).all()]


@router.post("/stock/items")
def add_item(body: ItemIn, user: AppUser = Depends(require_roles(*MANAGE)), db: Session = Depends(get_db)):
    if body.kind not in [k.value for k in StockKind]:
        raise HTTPException(400, "Unknown stock type")
    name, variant, color = body.name.strip(), body.variant.strip(), body.color.strip()
    if not name:
        raise HTTPException(400, "Enter the name")
    ex = db.query(StockItem).filter(StockItem.kind == body.kind, StockItem.name == name,
                                    StockItem.variant == variant, StockItem.color == color).first()
    if ex:
        if ex.is_active:
            raise HTTPException(400, "This item already exists")
        ex.is_active = True; i = ex
    else:
        i = StockItem(kind=body.kind, name=name, variant=variant, color=color); db.add(i)
    db.commit()
    return svc.item_dict(i)


@router.post("/stock/movements")
def add_move(body: MoveIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role.value not in VIEW_ALL:
        raise HTTPException(403, "Insufficient permissions")
    svc.record(db, user, body.model_dump())
    db.commit()
    return {"ok": True}


@router.get("/stock/movements", dependencies=[Depends(require_roles(*VIEW_ALL))])
def movements(item_id: int | None = None, branch_id: int | None = None, move_type: str | None = None,
              date_from: date | None = None, date_to: date | None = None, limit: int = 200,
              db: Session = Depends(get_db)):
    q = db.query(StockMovement)
    if item_id: q = q.filter(StockMovement.item_id == item_id)
    if move_type: q = q.filter(StockMovement.move_type == move_type.upper())
    if branch_id: q = q.filter((StockMovement.from_branch_id == branch_id) | (StockMovement.to_branch_id == branch_id))
    if date_from: q = q.filter(StockMovement.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to: q = q.filter(StockMovement.created_at < datetime.combine(date_to + timedelta(days=1), datetime.min.time()))
    from app.modules.users.models import Branch
    names = {b.branch_id: b.name for b in db.query(Branch).all()}
    out = []
    for m in q.order_by(StockMovement.created_at.desc(), StockMovement.id.desc()).limit(min(limit, 1000)).all():
        out.append({"id": m.id, "at": m.created_at, "type": m.move_type, "item": svc.item_dict(m.item)["label"],
                    "kind": m.item.kind, "qty": m.qty, "counted_qty": m.counted_qty, "reference": m.reference,
                    "from": names.get(m.from_branch_id, "Warehouse") if m.move_type in ("TRANSFER", "ISSUE") else None,
                    "to": (names.get(m.to_branch_id, "Warehouse")
                           if m.move_type in ("ALLOCATE", "TRANSFER", "RECEIPT", "RECEIVE", "COUNT") else None),
                    "by": m.by_user.full_name if m.by_user else None, "received_by": m.received_by, "note": m.note})
    return out
