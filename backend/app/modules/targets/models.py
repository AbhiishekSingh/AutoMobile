"""Monthly booking targets: one row per (month, PBA, bike model)."""
from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base, now_ist


class SalesTarget(Base):
    __tablename__ = "sales_target"
    __table_args__ = (UniqueConstraint("month", "user_id", "model_id", name="uq_sales_target"),)
    id = Column(Integer, primary_key=True)
    month = Column(Date, nullable=False, index=True)          # always the 1st of the month
    user_id = Column(Integer, ForeignKey("app_user.user_id"), nullable=False, index=True)   # the PBA
    model_id = Column(Integer, ForeignKey("bike_model.id"), nullable=False)
    qty = Column(Integer, nullable=False)
    set_by_user_id = Column(Integer, ForeignKey("app_user.user_id"))
    updated_at = Column(DateTime, default=now_ist, onupdate=now_ist)

    user = relationship("AppUser", foreign_keys=[user_id])
    model = relationship("BikeModel")
