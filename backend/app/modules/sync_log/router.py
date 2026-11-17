"""Admin: data-sync failures (GET /sync-failures, POST /sync-failures/{id}/resolve)."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db, now_ist
from app.core.deps import get_current_user, require_roles
from app.modules.sync_log.models import SyncFailure
from app.modules.users.models import AppUser

router = APIRouter(tags=["sync-log"], dependencies=[Depends(require_roles("ADMIN"))])


@router.get("/sync-failures")
def list_failures(source: Optional[str] = None, state: str = "OPEN", limit: int = 300, db: Session = Depends(get_db)):
    q = db.query(SyncFailure)
    if source:
        q = q.filter(SyncFailure.source == source)
    if state == "OPEN":
        q = q.filter(SyncFailure.resolved_at.is_(None))
    elif state == "RESOLVED":
        q = q.filter(SyncFailure.resolved_at.isnot(None))
    names = {u.user_id: u.full_name for u in db.query(AppUser).all()}
    rows = q.order_by(SyncFailure.id.desc()).limit(min(limit, 1000)).all()
    base = db.query(SyncFailure)
    return {"open": base.filter(SyncFailure.resolved_at.is_(None)).count(), "resolved": base.filter(SyncFailure.resolved_at.isnot(None)).count(),
            "rows": [{"id": r.id, "source": r.source, "ref_type": r.ref_type, "ref_id": r.ref_id, "ref_label": r.ref_label,
                      "message": r.message, "at": r.created_at, "by": names.get(r.created_by_user_id),
                      "resolved_at": r.resolved_at, "resolved_by": names.get(r.resolved_by_user_id)} for r in rows]}


@router.post("/sync-failures/{fid}/resolve")
def resolve(fid: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    r = db.get(SyncFailure, fid)
    if not r:
        raise HTTPException(404, "Not found")
    r.resolved_at, r.resolved_by_user_id = now_ist(), user.user_id
    db.commit()
    return {"ok": True}
