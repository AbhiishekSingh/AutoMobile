"""In-app notifications.

One row = one notification for exactly one recipient (`user_id`). There is no
"broadcast" concept here on purpose: every insert is scoped to a single user
at creation time, and every read is scoped to `current_user` at query time.
That's what keeps a PBA from ever seeing another PBA's notifications — see
`service.py` for the write-side guardrails and `router.py` for the read-side
scoping.
"""
import enum

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base, now_ist


class NotificationType(str, enum.Enum):
    LEAD_ASSIGNED = "LEAD_ASSIGNED"              # a single lead was (re)assigned to you
    LEADS_BULK_ASSIGNED = "LEADS_BULK_ASSIGNED"   # a CSV import assigned N leads to you


class Notification(Base):
    __tablename__ = "notification"

    id = Column(Integer, primary_key=True)

    # Who this notification belongs to. NOT NULL on purpose — a notification
    # with no owner is a bug, not a "broadcast to everyone" state.
    user_id = Column(Integer, ForeignKey("app_user.user_id"), nullable=False)

    type = Column(String, nullable=False)
    title = Column(String, nullable=False)
    message = Column(Text)

    # Optional deep-link target, e.g. reference_type="lead", reference_id=<lead_id>.
    reference_type = Column(String)
    reference_id = Column(Integer)

    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=now_ist, nullable=False)

    user = relationship("AppUser")

    __table_args__ = (
        # Powers "unread count for this user" and "list this user's unread first".
        Index("ix_notification_user_unread", "user_id", "is_read"),
        # Powers "list this user's notifications, newest first".
        Index("ix_notification_user_created", "user_id", "created_at"),
    )
