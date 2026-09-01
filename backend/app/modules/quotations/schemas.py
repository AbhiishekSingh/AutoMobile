"""Pydantic schemas for the Quotations module."""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from app.modules.quotations.models import HsprRegistrationType, QuotationStatus


# ---------- inclusions ----------
class InclusionIn(BaseModel):
    description: str
    included: bool = True


class InclusionOut(InclusionIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    sort_order: int


class InclusionUpdate(BaseModel):
    id: Optional[int] = None          # None = new row being added
    description: str
    included: bool = True
    sort_order: int = 0


# ---------- EMI options ----------
class EmiOptionIn(BaseModel):
    tenure_months: int
    down_payment: Optional[Decimal] = None
    monthly_emi: Optional[Decimal] = None
    roi_percent: Optional[Decimal] = None


class EmiOptionOut(EmiOptionIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ---------- documents ----------
class DocumentIn(BaseModel):
    document_name: str
    required: bool = True


class DocumentOut(DocumentIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ---------- quotation header ----------
class QuotationCreate(BaseModel):
    customer_name: str
    contact_no: str
    email: Optional[str] = None
    model_id: Optional[int] = None
    color: Optional[str] = None
    on_road_price: Decimal
    hspr_registration_type: HsprRegistrationType = HsprRegistrationType.REGULAR
    sales_manager_name: Optional[str] = None
    finance_bank_name: Optional[str] = None
    finance_financer_name: Optional[str] = None


class QuotationUpdate(BaseModel):
    customer_name: Optional[str] = None
    contact_no: Optional[str] = None
    email: Optional[str] = None
    model_id: Optional[int] = None
    color: Optional[str] = None
    on_road_price: Optional[Decimal] = None
    hspr_registration_type: Optional[HsprRegistrationType] = None
    sales_manager_name: Optional[str] = None
    finance_bank_name: Optional[str] = None
    finance_financer_name: Optional[str] = None


class QuotationStatusUpdate(BaseModel):
    status: QuotationStatus


class InclusionsBulkUpdate(BaseModel):
    inclusions: List[InclusionUpdate]


class EmiBulkUpdate(BaseModel):
    emi_options: List[EmiOptionIn]


class DocumentsBulkUpdate(BaseModel):
    documents: List[DocumentIn]


# ---------- output ----------
class QuotationListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    quotation_id: int
    quotation_no: str
    lead_id: int
    customer_id: int
    customer_name: str
    contact_no: str
    on_road_price: Decimal
    status: QuotationStatus
    valid_until: Optional[datetime] = None
    created_at: datetime


class QuotationDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    quotation_id: int
    quotation_no: str
    lead_id: int
    customer_id: int
    branch_id: Optional[int] = None
    customer_name: str
    contact_no: str
    email: Optional[str] = None
    model_id: Optional[int] = None
    color: Optional[str] = None
    on_road_price: Decimal
    hspr_registration_type: HsprRegistrationType
    sales_manager_name: Optional[str] = None
    finance_bank_name: Optional[str] = None
    finance_financer_name: Optional[str] = None
    status: QuotationStatus
    valid_until: Optional[datetime] = None
    created_at: datetime
    inclusions: List[InclusionOut] = []
    emi_options: List[EmiOptionOut] = []
    documents: List[DocumentOut] = []