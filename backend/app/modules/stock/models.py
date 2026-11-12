"""Stock register: vehicles, helmets and parking covers, by showroom.

Quantities are never stored. Every change is a StockMovement row (append-only) and the
balance of an item at a place is the sum of its movements. A place is a Branch
(showroom) or the warehouse (branch_id = NULL).

  RECEIVE   goods arrive at the warehouse              (to warehouse)
  ALLOCATE  warehouse -> showroom                       (Owner)
  TRANSFER  showroom -> showroom                        (Owner)
  RECEIPT   showroom receives goods directly            (Owner / GM for own showroom)
  ISSUE     leaves a showroom (sold / given to customer / damaged)   (Owner / GM own)
  COUNT     physical count: stores the difference from the system figure (discrepancy)
"""
import enum

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base, now_ist


class StockKind(str, enum.Enum):
    VEHICLE = "VEHICLE"
    HELMET = "HELMET"
    PARKING_COVER = "PARKING_COVER"


MOVE_TYPES = ("RECEIVE", "ALLOCATE", "TRANSFER", "RECEIPT", "ISSUE", "COUNT")


class StockItem(Base):
    __tablename__ = "stock_item"
    __table_args__ = (UniqueConstraint("kind", "name", "variant", "color", name="uq_stock_item"),)
    id = Column(Integer, primary_key=True)
    kind = Column(String, nullable=False)          # StockKind value
    name = Column(String, nullable=False)          # vehicle model / helmet model / cover type
    variant = Column(String, nullable=False, default="")   # vehicle variant / helmet size
    color = Column(String, nullable=False, default="")
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=now_ist, nullable=False)


class StockMovement(Base):
    __tablename__ = "stock_movement"
    id = Column(Integer, primary_key=True)
    item_id = Column(Integer, ForeignKey("stock_item.id"), nullable=False, index=True)
    move_type = Column(String, nullable=False)
    from_branch_id = Column(Integer, ForeignKey("branch.branch_id"))   # NULL + RECEIVE/ALLOCATE = warehouse
    to_branch_id = Column(Integer, ForeignKey("branch.branch_id"))
    qty = Column(Integer, nullable=False)          # > 0; COUNT stores the signed difference
    counted_qty = Column(Integer)                  # COUNT only
    reference = Column(String)                     # challan / invoice no.
    received_by = Column(String)
    note = Column(Text)
    by_user_id = Column(Integer, ForeignKey("app_user.user_id"), nullable=False)
    created_at = Column(DateTime, default=now_ist, nullable=False, index=True)

    item = relationship("StockItem")
    by_user = relationship("AppUser", foreign_keys=[by_user_id])
