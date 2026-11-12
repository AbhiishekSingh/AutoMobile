from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.deps import get_current_user, get_db, require_roles
from app.modules.leads.models import BikeModel
from app.modules.targets import service as svc
from app.modules.targets.models import SalesTarget
from app.modules.users.models import AppUser, Role

router = APIRouter(tags=["targets"])
MANAGE = ("OWNER", "GM", "ADMIN")


def _month(s):
    try:
        y, m = (s or "").split("-"); return date(int(y), int(m), 1)
    except Exception:
        t = date.today(); return date(t.year, t.month, 1)


class Cell(BaseModel):
    user_id: int
    model_id: int
    qty: int


class SaveIn(BaseModel):
    month: str
    cells: list[Cell]


@router.get("/targets")
def targets(month: str | None = None, branch_id: int | None = None,
            user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role.value not in MANAGE + ("PBA", "CRE"):
        raise HTTPException(403, "Insufficient permissions")
    m = _month(month); nxt = svc.next_month(m)
    ids = svc.pba_ids(db, user, branch_id)
    pq = db.query(AppUser).filter(AppUser.role == Role.PBA, AppUser.is_active == True)  # noqa: E712
    if ids is not None:
        pq = pq.filter(AppUser.user_id.in_(ids or [-1]))
    pbas = pq.order_by(AppUser.full_name).all()
    models = db.query(BikeModel).filter(BikeModel.is_active == True).order_by(BikeModel.name).all()  # noqa: E712
    tmap = {(t.user_id, t.model_id): t.qty for t in db.query(SalesTarget).filter(SalesTarget.month == m).all()}
    ach = svc.achieved(db, datetime.combine(m, datetime.min.time()), datetime.combine(nxt, datetime.min.time()),
                       [p.user_id for p in pbas])
    rows = []
    for p in pbas:
        cells = {mo.id: {"target": tmap.get((p.user_id, mo.id), 0), "achieved": ach.get((p.user_id, mo.id), 0)} for mo in models}
        tt = sum(c["target"] for c in cells.values()); aa = sum(c["achieved"] for c in cells.values())
        rows.append({"user_id": p.user_id, "name": p.full_name, "branch_id": p.branch_id, "cells": cells,
                     "target": tt, "achieved": aa, "pct": round(aa * 100 / tt) if tt else None})
    return {"month": m.strftime("%Y-%m"), "models": [{"id": x.id, "name": x.name} for x in models], "pbas": rows,
            "can_edit": user.role.value in MANAGE}


@router.put("/targets")
def save(body: SaveIn, user: AppUser = Depends(require_roles(*MANAGE)), db: Session = Depends(get_db)):
    m = _month(body.month)
    cur = date.today()
    if m < date(cur.year, cur.month, 1):
        raise HTTPException(400, "Targets for a past month cannot be changed")
    pba_ok = {u.user_id for u in db.query(AppUser).filter(AppUser.role == Role.PBA).all()}
    model_ok = {x.id for x in db.query(BikeModel).all()}
    ex = {(t.user_id, t.model_id): t for t in db.query(SalesTarget).filter(SalesTarget.month == m).all()}
    for c in body.cells:
        if c.qty < 0 or c.qty > 10000:
            raise HTTPException(400, "Target must be between 0 and 10000")
        if c.user_id not in pba_ok or c.model_id not in model_ok:
            raise HTTPException(400, "Unknown PBA or model")
        t = ex.get((c.user_id, c.model_id))
        if t:
            t.qty = c.qty; t.set_by_user_id = user.user_id
        elif c.qty:
            db.add(SalesTarget(month=m, user_id=c.user_id, model_id=c.model_id, qty=c.qty, set_by_user_id=user.user_id))
    db.commit()
    return {"ok": True}
