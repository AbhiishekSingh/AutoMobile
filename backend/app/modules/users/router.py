from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.core.security import hash_password
from app.modules.audit.service import record_changes
from app.modules.users.access import CRE_MAX_BRANCHES
from app.modules.users.models import AppUser, Branch, Role, UserBranch
from app.modules.users.schemas import (PasswordReset, UserCreate, UserOut,
                                        UserUpdate)

router = APIRouter(prefix="/users", tags=["users"],
                   dependencies=[Depends(require_roles("ADMIN"))])

USER_TRACKED_FIELDS = ("full_name", "email", "role", "branch_id", "is_active")


# ---------- CRE branches ----------
def _clean_cre_branches(db: Session, branch_ids: list[int] | None) -> list[int]:
    """Validate the branches picked for a CRE: 1 to CRE_MAX_BRANCHES, all real."""
    ids = list(dict.fromkeys(branch_ids or []))   # de-duplicate, keep order
    if not ids:
        raise HTTPException(400, "Please pick at least one branch for this CRE")
    if len(ids) > CRE_MAX_BRANCHES:
        raise HTTPException(400, f"A CRE can cover at most {CRE_MAX_BRANCHES} branches")
    found = {b.branch_id for b in db.query(Branch).filter(Branch.branch_id.in_(ids)).all()}
    if missing := [i for i in ids if i not in found]:
        raise HTTPException(400, f"Unknown branch id(s): {missing}")
    return ids


def _branch_names(db: Session, ids: list[int]) -> str | None:
    if not ids:
        return None
    names = {b.branch_id: b.name for b in db.query(Branch).filter(Branch.branch_id.in_(ids))}
    return ", ".join(names.get(i, str(i)) for i in sorted(ids))


def _set_branch_links(user: AppUser, ids: list[int]) -> None:
    """Make the user's branch links exactly `ids` — removes the ones no longer
    picked and adds the new ones (no delete-and-recreate, so the unique
    (user, branch) constraint is never hit mid-save)."""
    wanted = set(ids)
    for link in list(user.branch_links):
        if link.branch_id not in wanted:
            user.branch_links.remove(link)          # delete-orphan removes the row
    have = {link.branch_id for link in user.branch_links}
    for bid in ids:
        if bid not in have:
            user.branch_links.append(UserBranch(branch_id=bid))


# ---------- endpoints ----------
@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)):
    return db.query(AppUser).order_by(AppUser.user_id).all()


@router.post("", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, db: Session = Depends(get_db)):
    if db.query(AppUser).filter(AppUser.login_id == body.login_id).first():
        raise HTTPException(409, "Login ID already exists")
    branch_id = body.branch_id
    cre_ids: list[int] = []
    if body.role == Role.CRE:
        cre_ids = _clean_cre_branches(db, body.branch_ids)
        branch_id = cre_ids[0]   # "home" branch, for anything that reads branch_id
    user = AppUser(login_id=body.login_id, full_name=body.full_name, email=body.email,
                   hashed_password=hash_password(body.password), role=body.role,
                   branch_id=branch_id, is_active=True)
    _set_branch_links(user, cre_ids)
    db.add(user); db.commit(); db.refresh(user)
    return user


@router.put("/{user_id}", response_model=UserOut)
def update_user(user_id: int, body: UserUpdate, actor: AppUser = Depends(get_current_user),
                db: Session = Depends(get_db)):
    user = db.get(AppUser, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    data = body.model_dump(exclude_unset=True)
    branch_ids = data.pop("branch_ids", None)

    before = {f: getattr(user, f, None) for f in USER_TRACKED_FIELDS}
    old_cre_ids = list(user.branch_ids)
    for field, value in data.items():
        setattr(user, field, value)

    if user.role == Role.CRE:
        # keep the current branches if none were sent (e.g. only a name edit)
        ids = _clean_cre_branches(db, branch_ids if branch_ids is not None else old_cre_ids)
        _set_branch_links(user, ids)
        user.branch_id = ids[0]
    else:
        ids = []
        _set_branch_links(user, [])   # no longer a CRE -> drop their branches

    record_changes(db, entity_type="user", entity_id=user.user_id, before=before,
                   after=user, fields=USER_TRACKED_FIELDS, changed_by_user_id=actor.user_id)
    # CRE branches, logged by name ("S.K KTM Thane, S.K KTM Chembur")
    if sorted(old_cre_ids) != sorted(ids):
        record_changes(db, entity_type="user", entity_id=user.user_id,
                       before={"cre_branches": _branch_names(db, old_cre_ids)},
                       after=SimpleNamespace(cre_branches=_branch_names(db, ids)),
                       fields=("cre_branches",), changed_by_user_id=actor.user_id)
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
