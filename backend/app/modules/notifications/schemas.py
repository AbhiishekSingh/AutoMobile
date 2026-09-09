from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class NotificationOut(BaseModel):
    id: int
    type: str
    title: str
    message: Optional[str] = None
    reference_type: Optional[str] = None
    reference_id: Optional[int] = None
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    total: int          # total rows matching the filter (for pagination)
    unread_count: int   # unread count across ALL of this user's notifications
    page: int
    page_size: int
    rows: list[NotificationOut]


class UnreadCountResponse(BaseModel):
    unread_count: int


class MarkReadResponse(BaseModel):
    ok: bool
    unread_count: int   # updated count, so the frontend can refresh the bell badge in one round trip
