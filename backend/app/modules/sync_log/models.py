from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.core.database import Base, now_ist


class SyncFailure(Base):
    """A data hand-over that failed (LeadSquare import row, WhatsApp send, ...). Visible to Admin."""
    __tablename__ = "sync_failure"
    id = Column(Integer, primary_key=True)
    source = Column(String, nullable=False)        # LEADSQUARE_IMPORT / WHATSAPP / ...
    ref_type = Column(String)                      # lead / import / whatsapp_message
    ref_id = Column(Integer)
    ref_label = Column(String)                     # human text: file name, enquiry no., kind
    message = Column(Text, nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("app_user.user_id"))
    created_at = Column(DateTime, default=now_ist, nullable=False)
    resolved_at = Column(DateTime)
    resolved_by_user_id = Column(Integer, ForeignKey("app_user.user_id"))
