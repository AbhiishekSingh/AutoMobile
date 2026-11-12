import secrets
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.core.security import hash_password
from app.modules.audit.service import record_changes
from app.modules.users.access import CRE_MAX_BRANCHES
from app.modules.users.models import AppUser, Branch, Role, UserBranch
from app.modules.users.schemas import (PasswordReset, PinSet, UserCreate, UserOut,
                                        UserUpdate)

router = APIRouter(prefix="/users", tags=["users"],
                   dependencies=[Depends(require_roles("ADMIN"))])

USER_TRACKED_FIELDS = ("full_name", "email", "role", "branch_id", "is_active", "login_enabled")


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


# ---------- branch login / PBA profile rules ----------
def _clean_pin(pin: str | None) -> str:
    pin = (pin or "").strip()
    if not (pin.isdigit() and 4 <= len(pin) <= 6):
        raise HTTPException(400, "The PIN must be 4 to 6 digits")
    return pin


def _check_branch_login(db: Session, role: Role, branch_id, skip_user_id=None) -> None:
    """A BRANCH login belongs to exactly one branch, and a branch has only one."""
    if role != Role.BRANCH:
        return
    if not branch_id or not db.get(Branch, branch_id):
        raise HTTPException(400, "A branch login needs its branch")
    q = db.query(AppUser).filter(AppUser.role == Role.BRANCH, AppUser.branch_id == branch_id, AppUser.is_active == True)  # noqa: E712
    if skip_user_id:
        q = q.filter(AppUser.user_id != skip_user_id)
    if q.first():
        raise HTTPException(409, "This branch already has a branch login")


def _check_profile(role: Role, login_enabled: bool, branch_id) -> None:
    if not login_enabled:
        if role != Role.PBA:
            raise HTTPException(400, "Only a PBA can work without their own login")
        if not branch_id:
            raise HTTPException(400, "A PBA without their own login needs a branch")


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
    login_enabled = True if body.role != Role.PBA else body.login_enabled
    _check_profile(body.role, login_enabled, branch_id)
    _check_branch_login(db, body.role, branch_id)
    if login_enabled:
        if not body.password or len(body.password) < 6:
            raise HTTPException(400, "Give a password of at least 6 characters")
        pw = body.password
    else:       # profile: nobody can sign in with this account; the PIN is how the PBA proves who they are
        pw = secrets.token_urlsafe(32)
    pin_hash = hash_password(_clean_pin(body.pin)) if (not login_enabled or body.pin) else None
    user = AppUser(login_id=body.login_id, full_name=body.full_name, email=body.email, phone=body.phone,
                   hashed_password=hash_password(pw), login_enabled=login_enabled, pin_hash=pin_hash, role=body.role,
                   ls_email=(body.ls_email or "").strip() or None, ls_name=(body.ls_name or "").strip() or None,
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
    new_pin = data.pop("pin", None)

    before = {f: getattr(user, f, None) for f in USER_TRACKED_FIELDS}
    old_cre_ids = list(user.branch_ids)
    for field, value in data.items():
        setattr(user, field, value)

    if user.role != Role.PBA and user.role != Role.BRANCH:
        user.login_enabled = True
    if user.role != Role.PBA and user.role != Role.BRANCH:
        user.pin_hash = None
    _check_profile(user.role, user.login_enabled, user.branch_id)
    _check_branch_login(db, user.role, user.branch_id, skip_user_id=user.user_id)
    if new_pin:
        user.pin_hash = hash_password(_clean_pin(new_pin))
    if not user.login_enabled and not user.pin_hash:
        raise HTTPException(400, "Set a PIN before making this PBA a profile without a login")
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


@router.post("/{user_id}/set-pin", response_model=UserOut)
def set_pin(user_id: int, body: PinSet, actor: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.get(AppUser, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    if user.role != Role.PBA:
        raise HTTPException(400, "Only a PBA has a PIN")
    user.pin_hash = hash_password(_clean_pin(body.pin))
    db.commit(); db.refresh(user)
    return user
