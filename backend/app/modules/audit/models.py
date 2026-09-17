"""Field-level change history.

One row = one field that actually changed value. A single save that edits
3 fields produces 3 rows, not one vague "something changed" row — so the
history reads as "Email changed from A to B", not "record was updated".
"""
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base, now_ist


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True)

    entity_type = Column(String, nullable=False)   # "customer" | "lead" | "user"
    entity_id = Column(Integer, nullable=False)
    field_name = Column(String, nullable=False)     # e.g. "email"
    old_value = Column(Text)                        # always stored as text — the diff is
    new_value = Column(Text)                        # for a human to read, not to re-parse

    # Who made the change — resolved server-side from the authenticated session
    # at write time (see audit/service.py), never trusted from client input.
    changed_by_user_id = Column(Integer, ForeignKey("app_user.user_id"))
    changed_at = Column(DateTime, default=now_ist, nullable=False)

    changed_by = relationship("AppUser")

    __table_args__ = (
        # Powers "show me this record's history, newest first".
        Index("ix_audit_entity", "entity_type", "entity_id", "changed_at"),
    )
