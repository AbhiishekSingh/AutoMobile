from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class PaymentCreate(BaseModel):
    amount: Decimal
    mode: str                                   # a PaymentMode value
    payment_date: Optional[date] = None         # default: today
    reference: Optional[str] = None             # UTR / UPI id / cheque no. / card slip
    finance_bank_name: Optional[str] = None     # for mode FINANCE
    remark: Optional[str] = None


class FinanceUpdate(BaseModel):
    finance_bank_name: Optional[str] = None
    emi_tenure_months: Optional[int] = None
    roi_percent: Optional[Decimal] = None       # variable input
