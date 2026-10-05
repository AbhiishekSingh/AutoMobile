"""Dropdown data for the logged-in user's own screens.

  GET /me/branches                 -> the branches this user works in
                                      (CRE: their 1-2 branches; PBA: their own;
                                       Owner/GM/Admin: all active branches)
                                      Feeds the CRE branch filter and the
                                      walk-in form's Branch dropdown.
  GET /me/branches/{id}/pbas       -> active PBAs in that branch, for the
                                      walk-in form's "Assign to PBA" dropdown.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.modules.users.access import (MANAGER_ROLES, SALES_ROLES,
                                      check_branch_access, is_cre)
from app.modules.users.models import AppUser, Branch, Role
from app.modules.users.schemas import BranchOption, PbaOption

router = APIRouter(prefix="/me", tags=["me"])
ROLES = SALES_ROLES + MANAGER_ROLES


@router.get("/branches", response_model=list[BranchOption],
            dependencies=[Depends(require_roles(*ROLES))])
def my_branches(user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(Branch)
    if is_cre(user):
        q = q.filter(Branch.branch_id.in_(user.branch_ids or [-1]))
    elif user.role == Role.PBA:
        q = q.filter(Branch.branch_id == (user.branch_id or -1))
    else:
        q = q.filter(Branch.is_active.is_(True))
    return q.order_by(Branch.name).all()


@router.get("/branches/{branch_id}/pbas", response_model=list[PbaOption],
            dependencies=[Depends(require_roles(*ROLES))])
def branch_pbas(branch_id: int, user: AppUser = Depends(get_current_user),
                db: Session = Depends(get_db)):
    check_branch_access(user, branch_id)
    return (db.query(AppUser)
            .filter(AppUser.role == Role.PBA, AppUser.is_active.is_(True),
                    AppUser.branch_id == branch_id)
            .order_by(AppUser.full_name).all())
