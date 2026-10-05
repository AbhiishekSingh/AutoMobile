"""WHO CAN SEE WHICH LEADS — the one place this rule lives.

Every screen that lists or opens leads (Leads, Customers, Follow Ups,
Dashboard, Quotations, lead detail) goes through `scope_leads()` below, so
the rule can't drift between screens.

  OWNER / GM / ADMIN  -> every lead
  PBA                 -> leads assigned to them (any branch)
                         + unassigned leads in their own branch
  CRE                 -> every lead in the 1-2 branches Admin gave them
                         (whoever it's assigned to — the lead stays with its PBA)

Branch filter (`branch_id`): the dropdown at the top of the CRE screens. It
narrows the list to one branch; it can never widen it — a CRE asking for a
branch that isn't theirs gets a 403, not data.
"""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.leads.models import Lead
from app.modules.users.models import AppUser, Role

# Roles that work leads day to day (same screens). Import this instead of
# writing ("PBA", "CRE") in each router, so a new sales role is a one-line change.
SALES_ROLES = ("PBA", "CRE")
MANAGER_ROLES = ("OWNER", "GM", "ADMIN")

# A CRE covers at least 1 and at most this many branches.
CRE_MAX_BRANCHES = 2


def is_cre(user: AppUser) -> bool:
    return user.role == Role.CRE


def check_branch_access(user: AppUser, branch_id: int | None) -> None:
    """Raise 403 if a CRE asks for a branch they don't cover."""
    if branch_id is not None and is_cre(user) and branch_id not in user.branch_ids:
        raise HTTPException(403, "You don't have access to this branch")


def scope_leads(query, user: AppUser, branch_id: int | None = None):
    """Limit a Lead query (ORM Query or select()) to the leads `user` may see,
    optionally narrowed to one branch."""
    if user.role == Role.PBA:
        if user.branch_id:
            query = query.filter(
                (Lead.assigned_user_id == user.user_id) |
                ((Lead.assigned_user_id.is_(None)) & (Lead.branch_id == user.branch_id))
            )
        else:   # PBA with no branch: only their own leads (never "everything")
            query = query.filter(Lead.assigned_user_id == user.user_id)
    elif is_cre(user):
        query = query.filter(Lead.branch_id.in_(user.branch_ids or [-1]))
    elif user.role.value not in MANAGER_ROLES:
        query = query.filter(Lead.lead_id == -1)   # any other role: nothing

    if branch_id is not None:
        check_branch_access(user, branch_id)
        query = query.filter(Lead.branch_id == branch_id)
    return query


def dashboard_branch(user: AppUser, branch_id: int | None) -> int | None:
    """The branch a dashboard shows. A CRE always sees ONE branch (their first
    if none was picked); everyone else may pass None for "all"."""
    if is_cre(user) and branch_id is None:
        return user.branch_ids[0] if user.branch_ids else None   # no branches: shows 0s
    return branch_id


def get_visible_lead(db: Session, user: AppUser, lead_id: int) -> Lead:
    """The lead, if `user` may see it — otherwise 404 (not 403, so we don't
    reveal that the lead exists)."""
    lead = scope_leads(db.query(Lead), user).filter(Lead.lead_id == lead_id).first()
    if not lead:
        raise HTTPException(404, "Lead not found")
    return lead
