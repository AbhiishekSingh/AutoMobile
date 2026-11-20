from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, user_from_payload
from app.core.security import (create_access_token, create_refresh_token,
                               decode_token, hash_password, verify_password)
from app.modules.auth.schemas import (LoginRequest, PasswordChange, ProfileUpdate,
                                       RefreshRequest, TokenResponse)
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


@router.put("/me", response_model=UserOut)
def update_me(body: ProfileUpdate, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """Everyone can fix their own name, mobile and e-mail. Role, branch and login ID stay with Admin."""
    if user.via_branch:
        raise HTTPException(403, "Sign in with your own login to change your details")
    data = body.model_dump(exclude_unset=True)
    if "full_name" in data:
        name = (data["full_name"] or "").strip()
        if not name:
            raise HTTPException(400, "Name cannot be empty")
        user.full_name = name
    if "phone" in data:
        digits = "".join(c for c in (data["phone"] or "") if c.isdigit())
        if digits and len(digits) < 10:
            raise HTTPException(400, "The mobile number must have at least 10 digits")
        user.phone = (data["phone"] or "").strip() or None
    if "email" in data:
        email = data["email"] or None
        if email and db.query(AppUser).filter(AppUser.email == email, AppUser.user_id != user.user_id).first():
            raise HTTPException(409, "This e-mail is already used by another user")
        user.email = email
    db.commit(); db.refresh(user)
    return user


@router.post("/change-password")
def change_password(body: PasswordChange, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.via_branch or not user.login_enabled:
        raise HTTPException(403, "This name has no password of its own")
    if not verify_password(body.current_password, user.hashed_password):
        raise HTTPException(400, "The current password is not correct")
    if len(body.new_password) < 6:
        raise HTTPException(400, "The new password must be at least 6 characters")
    if body.new_password == body.current_password:
        raise HTTPException(400, "The new password must be different from the current one")
    user.hashed_password = hash_password(body.new_password)
    db.commit()
    return {"ok": True}
