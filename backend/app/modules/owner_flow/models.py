"""The Owner's two approvals on a booked deal.

INITIAL  right after the booking: Owner approves the discounted price and records, separately,
         Customer Processing YES/NO and ATW YES/NO. Nothing moves on without it.
FINAL    after the Insurance policy PDF is uploaded: Owner approves / rejects the whole file.
         Approval sends the file to the RTO and enables the Delivery Challan for the PBA.
One row per lead per stage; a rejected row is re-opened (round + 1) when the PBA resubmits.
Every decision keeps who / when / remark; field-level history also goes to the audit log."""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base, now_ist


class OwnerStageApproval(Base):
    __tablename__ = "owner_stage_approval"
    __table_args__ = (UniqueConstraint("lead_id", "stage", name="uq_owner_stage_lead_stage"),)
    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer, ForeignKey("lead.lead_id"), nullable=False, index=True)
    stage = Column(String, nullable=False)                      # INITIAL / FINAL
    status = Column(String, nullable=False, default="PENDING")  # PENDING / APPROVED / REJECTED
    round_no = Column(Integer, nullable=False, default=1)       # 2, 3 ... after each resubmission
    # INITIAL stage
    quoted_price = Column(Numeric(12, 2))                       # on-road price when requested
    discounted_price = Column(Numeric(12, 2))                   # what the Owner approved
    customer_processing = Column(Boolean)                       # YES / NO
    atw_allowed = Column(Boolean)                               # YES / NO
    requested_at = Column(DateTime, default=now_ist, nullable=False)
    decided_by_user_id = Column(Integer, ForeignKey("app_user.user_id"))
    decided_at = Column(DateTime)
    remark = Column(Text)                                       # mandatory on rejection

    decided_by = relationship("AppUser", foreign_keys=[decided_by_user_id])
