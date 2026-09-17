"""Read-only endpoints for viewing change history.

Restricted to Owner/GM/Admin — a PBA can see that a lead was edited via the
existing Follow-up log, but the *field-level audit trail* (who changed a
customer's email from X to Y) is a management-oversight feature, not
something every PBA needs on their own screen.
"""
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_roles
from app.modules.audit.models import AuditLog
from app.modules.audit.schemas import AuditLogListResponse, AuditLogOut
from app.modules.users.models import AppUser

router = APIRouter(prefix="/audit-log", tags=["audit-log"])

VIEW_ROLES = ("OWNER", "GM", "ADMIN")
MAX_PAGE_SIZE = 100


def _to_out(r: AuditLog) -> AuditLogOut:
    return AuditLogOut(
        id=r.id, entity_type=r.entity_type, entity_id=r.entity_id,
        field_name=r.field_name, old_value=r.old_value, new_value=r.new_value,
        changed_by_name=(r.changed_by.full_name if r.changed_by else None),
        changed_at=r.changed_at,
    )


@router.get("", response_model=AuditLogListResponse,
           dependencies=[Depends(require_roles(*VIEW_ROLES))])
def list_all_history(db: Session = Depends(get_db), entity_type: str | None = None,
                     changed_by_user_id: int | None = None, date_from: datetime | None = None,
                     date_to: datetime | None = None, page: int = 1, page_size: int = 25):
    """System-wide activity feed for the standalone Admin 'Activity Log' page —
    every field change across every customer/lead/user, filterable, newest first.
    """
    page = max(page, 1)
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))

    q = db.query(AuditLog)
    if entity_type:
        q = q.filter(AuditLog.entity_type == entity_type)
    if changed_by_user_id:
        q = q.filter(AuditLog.changed_by_user_id == changed_by_user_id)
    if date_from:
        q = q.filter(AuditLog.changed_at >= date_from)
    if date_to:
        q = q.filter(AuditLog.changed_at <= date_to)

    total = q.count()
    rows = (q.order_by(AuditLog.changed_at.desc())
             .offset((page - 1) * page_size).limit(page_size).all())

    # For the filter dropdown — everyone who has ever made a tracked change.
    staff = (db.query(AppUser.user_id, AppUser.full_name)
             .join(AuditLog, AuditLog.changed_by_user_id == AppUser.user_id)
             .distinct().order_by(AppUser.full_name).all())

    return AuditLogListResponse(
        total=total, page=page, page_size=page_size,
        rows=[_to_out(r) for r in rows],
        staff=[{"user_id": s.user_id, "full_name": s.full_name} for s in staff],
    )


@router.get("/{entity_type}/{entity_id}", response_model=list[AuditLogOut],
           dependencies=[Depends(require_roles(*VIEW_ROLES))])
def entity_history(entity_type: str, entity_id: int, db: Session = Depends(get_db)):
    rows = (db.query(AuditLog)
             .filter(AuditLog.entity_type == entity_type, AuditLog.entity_id == entity_id)
             .order_by(AuditLog.changed_at.desc())
             .limit(200)
             .all())
    return [_to_out(r) for r in rows]
