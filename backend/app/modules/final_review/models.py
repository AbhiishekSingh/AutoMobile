"""CRE final review of a delivered customer. A delivered customer is only CLOSED after a COMPLETED review."""
from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base, now_ist


class FinalReview(Base):
    __tablename__ = "final_review"
    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer, ForeignKey("lead.lead_id"), unique=True, nullable=False)
    review_date = Column(Date, nullable=False)
    customer_feedback = Column(Text, nullable=False)
    product_satisfaction = Column(Integer, nullable=False)     # 1 (very dissatisfied) .. 5 (very satisfied)
    customer_experience = Column(Integer, nullable=False)      # 1 .. 5
    cre_remarks = Column(Text, nullable=False)
    status = Column(String, nullable=False)                    # COMPLETED / CALLBACK_NEEDED / NOT_REACHABLE / ISSUE_RAISED(not used to close)
    attempts = Column(Integer, nullable=False, default=1)      # how many times the CRE saved this review
    reviewed_by_user_id = Column(Integer, ForeignKey("app_user.user_id"))
    closed_at = Column(DateTime)
    created_at = Column(DateTime, default=now_ist, nullable=False)
    updated_at = Column(DateTime, default=now_ist, onupdate=now_ist)

    reviewed_by = relationship("AppUser")
