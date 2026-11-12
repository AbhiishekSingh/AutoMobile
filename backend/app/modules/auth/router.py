from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, user_from_payload
from app.core.security import (create_access_token, create_refresh_token,
                               decode_token, verify_password)
from app.modules.auth.schemas import (LoginRequest, RefreshRequest,
                                       TokenResponse)
from app.modules.users.models import AppUser
from app.modules.users.schemas import UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(AppUser).filter(AppUser.login_id == body.login_id).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid Login ID or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account is deactivated")
    if not user.login_enabled:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This name has no login of its own. Sign in with your branch account, then choose your name.")
    role = user.role.value
    return TokenResponse(access_token=create_access_token(user.login_id, role),
                         refresh_token=create_refresh_token(user.login_id, role),
                         user=UserOut.model_validate(user))


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    user = user_from_payload(db, payload)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User no longer valid")
    base_login = payload.get("sub")
    act = payload.get("act")
    role = payload.get("role") or user.role.value
    return TokenResponse(access_token=create_access_token(base_login, role, act),
                         refresh_token=create_refresh_token(base_login, role, act),
                         user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: AppUser = Depends(get_current_user)):
    return user
