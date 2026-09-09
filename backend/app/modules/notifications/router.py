"""Every endpoint here derives "whose notifications" from the authenticated
session (`get_current_user`) — never from a client-supplied user id. That is
the single rule that guarantees a user only ever sees/touches their own rows.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.modules.notifications.models import Notification
from app.modules.notifications.schemas import (MarkReadResponse,
                                                NotificationListResponse,
                                                UnreadCountResponse)
from app.modules.users.models import AppUser

router = APIRouter(prefix="/notifications", tags=["notifications"])

MAX_PAGE_SIZE = 50  # hard cap so a huge page_size can't be used to pull excessive rows


def _unread_count(db: Session, user_id: int) -> int:
    return db.query(func.count(Notification.id)).filter(
        Notification.user_id == user_id, Notification.is_read.is_(False)).scalar() or 0


@router.get("", response_model=NotificationListResponse)
def list_notifications(user: AppUser = Depends(get_current_user), db: Session = Depends(get_db),
                       unread_only: bool = False, page: int = 1, page_size: int = 20):
    page = max(page, 1)
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))

    q = db.query(Notification).filter(Notification.user_id == user.user_id)
    if unread_only:
        q = q.filter(Notification.is_read.is_(False))

    total = q.count()
    rows = (q.order_by(Notification.created_at.desc(), Notification.id.desc())
             .offset((page - 1) * page_size).limit(page_size).all())

    return NotificationListResponse(total=total, unread_count=_unread_count(db, user.user_id),
                                    page=page, page_size=page_size, rows=rows)


@router.get("/unread-count", response_model=UnreadCountResponse)
def unread_count(user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return UnreadCountResponse(unread_count=_unread_count(db, user.user_id))


@router.patch("/{notification_id}/read", response_model=MarkReadResponse)
def mark_read(notification_id: int, user: AppUser = Depends(get_current_user),
              db: Session = Depends(get_db)):
    n = db.query(Notification).filter(Notification.id == notification_id,
                                      Notification.user_id == user.user_id).first()
    if not n:
        # Deliberately 404 rather than 403: this tells a caller "no such
        # notification" instead of confirming that some OTHER user's
        # notification with this id exists (which 403 would leak).
        raise HTTPException(404, "Notification not found")
    if not n.is_read:          # idempotent: re-marking an already-read row is a harmless no-op
        n.is_read = True
        db.commit()
    return MarkReadResponse(ok=True, unread_count=_unread_count(db, user.user_id))


@router.patch("/read-all", response_model=MarkReadResponse)
def mark_all_read(user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    # Single scoped UPDATE — only ever touches rows for THIS user, and running
    # it twice in a row (e.g. a double click) is a no-op the second time.
    db.query(Notification).filter(Notification.user_id == user.user_id,
                                  Notification.is_read.is_(False)).update(
        {Notification.is_read: True}, synchronize_session=False)
    db.commit()
    return MarkReadResponse(ok=True, unread_count=0)
