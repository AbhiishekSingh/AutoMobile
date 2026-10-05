from typing import Optional

from pydantic import BaseModel, EmailStr

from app.modules.users.models import Role


class UserOut(BaseModel):
    user_id: int
    login_id: str
    full_name: str
    email: Optional[str] = None
    role: Role
    branch_id: Optional[int] = None
    branch_ids: list[int] = []      # CRE only: the 1-2 branches they cover
    is_active: bool

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    login_id: str
    full_name: str
    email: Optional[EmailStr] = None
    password: str
    role: Role
    branch_id: Optional[int] = None
    branch_ids: Optional[list[int]] = None   # required for CRE (1-2), ignored otherwise


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[Role] = None
    branch_id: Optional[int] = None
    branch_ids: Optional[list[int]] = None   # CRE: replaces their branches
    is_active: Optional[bool] = None


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
