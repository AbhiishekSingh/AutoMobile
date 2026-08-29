"""PBA module tables — customers, leads, follow-ups, test rides + lookups."""
import enum
from datetime import datetime

from sqlalchemy import (Boolean, Column, DateTime, Enum, ForeignKey, Integer,
                        String, Text)
from sqlalchemy.orm import relationship

from app.core.database import Base, now_ist


# ---------- lookup tables (client-managed value lists) ----------
class EnquiryMode(Base):
    __tablename__ = "enquiry_mode"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    is_active = Column(Boolean, default=True)


class OpportunityStatus(Base):
    __tablename__ = "opportunity_status"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)      # HOT LEAD, WARM LEAD, ...
    is_active = Column(Boolean, default=True)


class Disposition(Base):
    __tablename__ = "disposition"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)      # RINGING, CALL LATER, ...
    is_active = Column(Boolean, default=True)


class LostReason(Base):
    __tablename__ = "lost_reason"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)


class BikeModel(Base):
    __tablename__ = "bike_model"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)      # DUKE 390, ADV 390 X PLUS, ...
    is_active = Column(Boolean, default=True)


# ---------- enums ----------
class LeadType(str, enum.Enum):
    SALES = "SALES"
    SERVICE = "SERVICE"


class LeadSource(str, enum.Enum):
    CSV = "CSV"          # LeadSquared import (Admin)
    WALKIN = "WALKIN"    # manual (PBA)


class EnquiryStage(str, enum.Enum):
    OPEN = "OPEN"
    QUOTED = "QUOTED"
    CLOSED = "CLOSED"
    BOOKED = "BOOKED"
    INVOICED = "INVOICED"


class SLAFlag(str, enum.Enum):
    GREEN = "GREEN"      # contacted <= 3h
    YELLOW = "YELLOW"    # pending 3-24h
    RED = "RED"          # overdue > 24h


class TestRideStatus(str, enum.Enum):
    BOOKED = "BOOKED"
    COMPLETED = "COMPLETED"
    RESCHEDULED = "RESCHEDULED"
    CANCELLED = "CANCELLED"


# ---------- core tables ----------
class Customer(Base):
    __tablename__ = "customer"
    customer_id = Column(Integer, primary_key=True)
    phone = Column(String, unique=True, index=True, nullable=False)   # dedup key
    full_name = Column(String, nullable=False)
    alt_phone = Column(String)
    email = Column(String)
    city = Column(String)
    pincode = Column(String)
    created_at = Column(DateTime, default=now_ist)
    updated_at = Column(DateTime, default=now_ist, onupdate=now_ist)

    leads = relationship("Lead", back_populates="customer")


class Lead(Base):
    __tablename__ = "lead"
    lead_id = Column(Integer, primary_key=True)
    enquiry_no = Column(String, unique=True, index=True, nullable=False)
    customer_id = Column(Integer, ForeignKey("customer.customer_id"), nullable=False)
    branch_id = Column(Integer, ForeignKey("branch.branch_id"))
    assigned_user_id = Column(Integer, ForeignKey("app_user.user_id"))
    mode_id = Column(Integer, ForeignKey("enquiry_mode.id"))
    model_id = Column(Integer, ForeignKey("bike_model.id"))
    color = Column(String)
    sku_code = Column(String)
    lead_type = Column(Enum(LeadType), default=LeadType.SALES)
    source = Column(Enum(LeadSource), default=LeadSource.CSV)
    enquiry_stage = Column(Enum(EnquiryStage), default=EnquiryStage.OPEN)
    opportunity_status_id = Column(Integer, ForeignKey("opportunity_status.id"))
    current_disposition_id = Column(Integer, ForeignKey("disposition.id"))
    lost_reason_id = Column(Integer, ForeignKey("lost_reason.id"))
    sla_flag = Column(Enum(SLAFlag), default=SLAFlag.YELLOW)
    enquiry_at = Column(DateTime, default=now_ist)
    first_contact_at = Column(DateTime)
    next_followup_at = Column(DateTime)
    ageing_days = Column(Integer, default=0)
    salesperson_email = Column(String)
    dealer_code = Column(String)
    created_at = Column(DateTime, default=now_ist)
    updated_at = Column(DateTime, default=now_ist, onupdate=now_ist)

    customer = relationship("Customer", back_populates="leads")
    branch = relationship("Branch")
    mode = relationship("EnquiryMode")
    model = relationship("BikeModel")
    opportunity = relationship("OpportunityStatus")
    current_disposition = relationship("Disposition")
    lost_reason = relationship("LostReason")
    followups = relationship("LeadFollowup", back_populates="lead",
                             order_by="LeadFollowup.created_at.desc()")
    test_rides = relationship("TestRide", back_populates="lead",
                              order_by="TestRide.created_at.desc()")


class LeadFollowup(Base):
    __tablename__ = "lead_followup"
    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer, ForeignKey("lead.lead_id"), nullable=False)
    user_id = Column(Integer, ForeignKey("app_user.user_id"))
    remark = Column(Text)
    contacted = Column(Boolean, default=True)
    disposition_id = Column(Integer, ForeignKey("disposition.id"))
    opportunity_status_id = Column(Integer, ForeignKey("opportunity_status.id"))
    next_followup_at = Column(DateTime)
    created_at = Column(DateTime, default=now_ist)

    lead = relationship("Lead", back_populates="followups")
    disposition = relationship("Disposition")
    opportunity = relationship("OpportunityStatus")
    user = relationship("AppUser")


class TestRide(Base):
    __tablename__ = "test_ride"
    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer, ForeignKey("lead.lead_id"), nullable=False)
    model_id = Column(Integer, ForeignKey("bike_model.id"))
    color = Column(String)
    status = Column(Enum(TestRideStatus), default=TestRideStatus.BOOKED)
    completed = Column(Boolean, default=False)
    scheduled_at = Column(DateTime)
    slot = Column(String)
    preferred_location = Column(String)   # Showroom / Home Test Ride / Office TD
    leadsquared_ref = Column(String)
    created_at = Column(DateTime, default=now_ist)

    lead = relationship("Lead", back_populates="test_rides")
    model = relationship("BikeModel")