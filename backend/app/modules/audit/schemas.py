from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AuditLogOut(BaseModel):
    id: int
    entity_type: str
    entity_id: int
    field_name: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    changed_by_name: Optional[str] = None   # resolved name, not just an id — the
                                            # whole point is "who did this", so the
                                            # screen shouldn't have to make a second
                                            # lookup just to show a human a name.
    changed_at: datetime

    class Config:
        from_attributes = True


class StaffOption(BaseModel):
    user_id: int
    full_name: str


class AuditLogListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    rows: list[AuditLogOut]
    staff: list[StaffOption]   # for the "filter by user" dropdown
