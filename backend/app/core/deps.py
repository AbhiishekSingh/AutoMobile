import re

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.modules.users.models import AppUser, Role

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


_LEAD_PATHS = ((re.compile(r"/leads/(\d+)"), None), (re.compile(r"/quotations/(\d+)"), "quotation"),
               (re.compile(r"/test-rides/(\d+)"), "ride"), (re.compile(r"/payments/(\d+)"), "payment"),
               (re.compile(r"/documents/(\d+)"), "document"))


def _lead_id_in_path(db: Session, path: str):
    """The lead a write request is about, read from its URL (None if it isn't about one lead)."""
    from app.modules.documents.models import CustomerDocument
    from app.modules.leads.models import TestRide
    from app.modules.payments.models import Payment
    from app.modules.quotations.models import Quotation
    for rx, kind in _LEAD_PATHS:
        m = rx.search(path)
        if not m:
            continue
        n = int(m.group(1))
        if kind is None:
            return n
        model = {"quotation": Quotation, "ride": TestRide, "payment": Payment, "document": CustomerDocument}[kind]
        row = db.get(model, n)
        return getattr(row, "lead_id", None) if row else None
    return None


def _enforce_view_only(request: Request, db: Session, pba: AppUser) -> None:
    """A PBA under a branch login may look at a colleague's customer, never change it."""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    lead_id = _lead_id_in_path(db, request.url.path)
    if lead_id is None:
        return
    from app.modules.leads.models import Lead
    lead = db.get(Lead, lead_id)
    if lead and lead.assigned_user_id not in (None, pba.user_id):
        owner = db.get(AppUser, lead.assigned_user_id)
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            f"View only: this customer belongs to {owner.full_name if owner else 'another PBA'}.")


def user_from_payload(db: Session, payload: dict) -> AppUser | None:
    """The user a token stands for. A token with `act` is a BRANCH login with a PBA picked: it acts as that PBA."""
    base = db.query(AppUser).filter(AppUser.login_id == payload.get("sub")).first()
    if not base or not base.is_active or not base.login_enabled:
        return None
    act = payload.get("act")
    if not act:
        return base
    if base.role != Role.BRANCH:
        return None
    pba = db.get(AppUser, act)
    if not pba or not pba.is_active or pba.role != Role.PBA or pba.branch_id != base.branch_id:
        return None
    pba.via_branch = True
    return pba


def get_current_user(request: Request, token: str = Depends(oauth2_scheme),
                     db: Session = Depends(get_db)) -> AppUser:
    creds_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise creds_error
    user = user_from_payload(db, payload)
    if not user:
        raise creds_error
    if user.via_branch:
        _enforce_view_only(request, db, user)
    return user


def get_branch_login(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> AppUser:
    """The BRANCH login behind the token - whether or not a PBA is currently picked."""
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Could not validate credentials")
    base = db.query(AppUser).filter(AppUser.login_id == payload.get("sub")).first()
    if not base or not base.is_active or base.role != Role.BRANCH:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This is only for a branch login")
    return base


def require_roles(*roles: str):
    def checker(user: AppUser = Depends(get_current_user)) -> AppUser:
        if user.role.value not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Insufficient permissions")
        return user
    return checker
