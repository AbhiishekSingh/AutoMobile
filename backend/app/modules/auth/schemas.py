from pydantic import BaseModel

from app.modules.users.schemas import UserOut


class LoginRequest(BaseModel):
    login_id: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut
