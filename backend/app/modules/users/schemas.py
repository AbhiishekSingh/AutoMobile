from typing import Optional

from pydantic import BaseModel, EmailStr

from app.modules.users.models import Role


class UserOut(BaseModel):
    user_id: int
    login_id: str
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    role: Role
    branch_id: Optional[int] = None
    branch_ids: list[int] = []      # CRE only: the 1-2 branches they cover
    is_active: bool
    login_enabled: bool = True      # False = PBA profile (no own login; works under the branch login)
    has_pin: bool = False
    ls_email: Optional[str] = None
    ls_name: Optional[str] = None
    via_branch: bool = False        # True = this PBA is working under the branch login

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    login_id: str
    full_name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    password: Optional[str] = None     # not needed for a PBA profile (login_enabled False)
    login_enabled: bool = True
    pin: Optional[str] = None          # 4-6 digits; for PBAs working under a branch login
    ls_email: Optional[str] = None     # PBA's salesperson email / name as LeadSquared writes it
    ls_name: Optional[str] = None
    role: Role
    branch_id: Optional[int] = None
    branch_ids: Optional[list[int]] = None   # required for CRE (1-2), ignored otherwise


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    role: Optional[Role] = None
    branch_id: Optional[int] = None
    branch_ids: Optional[list[int]] = None   # CRE: replaces their branches
    is_active: Optional[bool] = None
    login_enabled: Optional[bool] = None
    pin: Optional[str] = None
    ls_email: Optional[str] = None
    ls_name: Optional[str] = None


class PasswordReset(BaseModel):
    new_password: str


class BranchOption(BaseModel):
    """A branch in a dropdown (CRE branch filter, walk-in form)."""
    branch_id: int
    name: str


class PbaOption(BaseModel):
    """A PBA in the walk-in form's "Assign to PBA" dropdown."""
    user_id: int
    full_name: str
    login_id: str


class PinSet(BaseModel):
    pin: str
