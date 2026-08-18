from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_roles
from app.core.security import hash_password
from app.modules.users.models import AppUser
from app.modules.users.schemas import (PasswordReset, UserCreate, UserOut,
                                        UserUpdate)

router = APIRouter(prefix="/users", tags=["users"],
                   dependencies=[Depends(require_roles("ADMIN"))])


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)):
    return db.query(AppUser).order_by(AppUser.user_id).all()


@router.post("", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, db: Session = Depends(get_db)):
    if db.query(AppUser).filter(AppUser.login_id == body.login_id).first():
        raise HTTPException(409, "Login ID already exists")
    user = AppUser(login_id=body.login_id, full_name=body.full_name, email=body.email,
                   hashed_password=hash_password(body.password), role=body.role,
                   branch_id=body.branch_id, is_active=True)
    db.add(user); db.commit(); db.refresh(user)
    return user


@router.put("/{user_id}", response_model=UserOut)
def update_user(user_id: int, body: UserUpdate, db: Session = Depends(get_db)):
    user = db.get(AppUser, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    db.commit(); db.refresh(user)
    return user


@router.patch("/{user_id}/deactivate", response_model=UserOut)
def deactivate_user(user_id: int, db: Session = Depends(get_db)):
    user = db.get(AppUser, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    user.is_active = False
    db.commit(); db.refresh(user)
    return user


@router.patch("/{user_id}/activate", response_model=UserOut)
def activate_user(user_id: int, db: Session = Depends(get_db)):
    user = db.get(AppUser, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    user.is_active = True
    db.commit(); db.refresh(user)
    return user


@router.post("/{user_id}/reset-password", response_model=UserOut)
def reset_password(user_id: int, body: PasswordReset, db: Session = Depends(get_db)):
    user = db.get(AppUser, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    user.hashed_password = hash_password(body.new_password)
    db.commit(); db.refresh(user)
    return user
