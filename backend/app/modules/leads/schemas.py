from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class Lookup(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class Lookups(BaseModel):
    enquiry_modes: list[Lookup]
    opportunity_statuses: list[Lookup]
    dispositions: list[Lookup]
    lost_reasons: list[Lookup]
    models: list[Lookup]


class LeadRow(BaseModel):
    """One row in the All Leads table."""
    lead_id: int
    enquiry_no: str
    enquiry_at: Optional[datetime]
    enquiry_mode: Optional[str]
    customer_name: str
    contact_masked: str
    model_name: Optional[str]
    opportunity_status: Optional[str]
    disposition: Optional[str]
    sla_flag: str


class LeadListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    rows: list[LeadRow]


class TileCount(BaseModel):
    key: str
    label: str
    count: int


class FollowupOut(BaseModel):
    id: int
    created_at: datetime
    remark: Optional[str]
    disposition: Optional[str]
    opportunity_status: Optional[str]
    next_followup_at: Optional[datetime]
    by: Optional[str]


class TestRideOut(BaseModel):
    id: int
    model_name: Optional[str]
    color: Optional[str]
    status: str
    scheduled_at: Optional[datetime]
    slot: Optional[str]
    preferred_location: Optional[str]
    completed: bool


class LeadDetail(BaseModel):
    lead_id: int
    enquiry_no: str
    enquiry_date: Optional[datetime]
    enquiry_time: Optional[str]
    dealer_code: Optional[str]
    branch_name: Optional[str]
    salesperson_name: Optional[str]
    salesperson_email: Optional[str]
    first_contact_at: Optional[datetime]
    within_3hrs: Optional[bool]
    followup_enquiry_mode: Optional[str]
    customer_name: str
    mobile: str
    pincode: Optional[str]
    model_name: Optional[str]
    color: Optional[str]
    sku_code: Optional[str]
    enquiry_stage: Optional[str]
    opportunity_status: Optional[str]
    disposition: Optional[str]
    lost_reason: Optional[str]
    next_followup_at: Optional[datetime]
    ageing_days: int
    # raw ids so edit dropdowns can pre-select the current value
    mode_id: Optional[int] = None
    model_id: Optional[int] = None
    opportunity_status_id: Optional[int] = None
    disposition_id: Optional[int] = None
    lost_reason_id: Optional[int] = None
    followups: list[FollowupOut]
    test_rides: list[TestRideOut]


class LeadUpdate(BaseModel):
    """Partial update for a lead + its customer. Every field optional; only the
    keys sent are changed (used by the per-section edit on Customer Details)."""
    # customer fields
    full_name: Optional[str] = None
    phone: Optional[str] = None
    pincode: Optional[str] = None
    city: Optional[str] = None
    alt_phone: Optional[str] = None
    # lead fields
    enquiry_at: Optional[datetime] = None
    first_contact_at: Optional[datetime] = None
    dealer_code: Optional[str] = None
    salesperson_email: Optional[str] = None
    mode_id: Optional[int] = None
    model_id: Optional[int] = None
    color: Optional[str] = None
    sku_code: Optional[str] = None
    enquiry_stage: Optional[str] = None
    opportunity_status_id: Optional[int] = None
    disposition_id: Optional[int] = None
    lost_reason_id: Optional[int] = None
    next_followup_at: Optional[datetime] = None
    ageing_days: Optional[int] = None


# ---------- create payloads ----------
class LeadCreate(BaseModel):
    full_name: str
    phone: str
    alt_phone: Optional[str] = None
    city: Optional[str] = None
    pincode: Optional[str] = None
    mode_id: Optional[int] = None
    model_id: Optional[int] = None
    color: Optional[str] = None
    lead_type: str = "SALES"
    source: str = "WALKIN"


class FollowupCreate(BaseModel):
    remark: Optional[str] = None
    contacted: bool = True
    disposition_id: Optional[int] = None
    opportunity_status_id: Optional[int] = None
    next_followup_at: Optional[datetime] = None


class TestRideCreate(BaseModel):
    model_id: Optional[int] = None
    color: Optional[str] = None
    status: str = "BOOKED"
    scheduled_at: Optional[datetime] = None
    slot: Optional[str] = None
    preferred_location: Optional[str] = None


class CustomerRow(BaseModel):
    """One row in the Customers list."""
    customer_id: int
    full_name: str
    contact_masked: str
    city: Optional[str]
    pincode: Optional[str]
    leads_count: int
    latest_enquiry_no: Optional[str]
    latest_model: Optional[str]
    latest_enquiry_at: Optional[datetime]
    latest_lead_id: Optional[int]


class CustomerListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    rows: list[CustomerRow]


class FollowupRow(BaseModel):
    """One row in the Follow-Ups feed."""
    lead_id: int
    enquiry_no: str
    customer_name: str
    contact_masked: str
    model_name: Optional[str]
    opportunity_status: Optional[str]
    disposition: Optional[str]
    next_followup_at: Optional[datetime]
    sla_flag: str
    bucket: str            # overdue | today | upcoming


class FollowupListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    counts: dict           # {overdue, today, upcoming, all}
    rows: list[FollowupRow]


class PBADashboard(BaseModel):
    open_bookings: int
    booked: int
    invoiced: int
    delivered: int
    calls_today: int
    quotations_shared: int
    test_rides_completed: int
    test_rides_scheduled: int
    total_target_ratio: int
    td_completed_ratio: int