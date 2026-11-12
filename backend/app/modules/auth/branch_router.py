"""Branch login: pick which PBA is working (name + personal PIN), switch, lock."""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db, now_ist
from app.core.deps import get_branch_login
from app.core.security import create_access_token, create_refresh_token, verify_password
from app.modules.auth.schemas import TokenResponse
from app.modules.users.models import AppUser, Branch, Role
from app.modules.users.schemas import UserOut

router = APIRouter(prefix="/branch", tags=["branch-login"])
MAX_WRONG = 5
LOCK_MINUTES = 5


class SelectIn(BaseModel):
    user_id: int
    pin: str


@router.get("/profiles")
def profiles(branch: AppUser = Depends(get_branch_login), db: Session = Depends(get_db)):
    b = db.get(Branch, branch.branch_id)
    pbas = (db.query(AppUser).filter(AppUser.role == Role.PBA, AppUser.branch_id == branch.branch_id,
                                     AppUser.is_active == True).order_by(AppUser.full_name).all())  # noqa: E712
    now = now_ist()
    return {"branch": b.name if b else None,
            "pbas": [{"user_id": p.user_id, "full_name": p.full_name, "has_pin": p.has_pin,
                      "locked": bool(p.pin_locked_until and p.pin_locked_until > now)} for p in pbas]}


@router.post("/select", response_model=TokenResponse)
def select(body: SelectIn, branch: AppUser = Depends(get_branch_login), db: Session = Depends(get_db)):
    pba = db.get(AppUser, body.user_id)
    if not pba or not pba.is_active or pba.role != Role.PBA or pba.branch_id != branch.branch_id:
        raise HTTPException(404, "That name is not in this branch")
    if not pba.pin_hash:
        raise HTTPException(400, "No PIN is set for this name. Ask Admin to set one.")
    now = now_ist()
    if pba.pin_locked_until and pba.pin_locked_until > now:
        mins = int((pba.pin_locked_until - now).total_seconds() // 60) + 1
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, f"Too many wrong PINs. Try again in {mins} minute(s).")
    if not verify_password((body.pin or "").strip(), pba.pin_hash):
        pba.pin_failed = (pba.pin_failed or 0) + 1
        msg = "Wrong PIN."
        if pba.pin_failed >= MAX_WRONG:
            pba.pin_locked_until = now + timedelta(minutes=LOCK_MINUTES); pba.pin_failed = 0
            msg = f"Too many wrong PINs. This name is locked for {LOCK_MINUTES} minutes."
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, msg)
    pba.pin_failed = 0; pba.pin_locked_until = None
    db.commit()
    pba.via_branch = True
    return TokenResponse(access_token=create_access_token(branch.login_id, branch.role.value, pba.user_id),
                         refresh_token=create_refresh_token(branch.login_id, branch.role.value, pba.user_id),
                         user=UserOut.model_validate(pba))


@router.post("/lock", response_model=TokenResponse)
def lock(branch: AppUser = Depends(get_branch_login)):
    """Back to the plain branch login (no PBA picked) - used by Switch PBA and the idle lock."""
    return TokenResponse(access_token=create_access_token(branch.login_id, branch.role.value),
                         refresh_token=create_refresh_token(branch.login_id, branch.role.value),
                         user=UserOut.model_validate(branch))
