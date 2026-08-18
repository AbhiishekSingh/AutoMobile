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


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[Role] = None
    branch_id: Optional[int] = None
    is_active: Optional[bool] = None


class PasswordReset(BaseModel):
    new_password: str
