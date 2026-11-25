"""Departments: the default set, and which one a role belongs to unless Admin chooses otherwise."""
from sqlalchemy.orm import Session

from app.modules.users.models import AppUser, Department

# (name, description, roles that default into it, sort)
DEFAULTS = [
    ("Sales (PBA)", "Walk-ins, enquiries, quotations, bookings and payments", ["PBA"], 10),
    ("Customer Relations (CRE)", "Follow-ups, LeadSquared leads and final reviews", ["CRE"], 20),
    ("Branch logins", "Shared showroom logins; PBAs pick their name under them", ["BRANCH"], 30),
    ("Insurance", "Policies, nominee details and policy PDFs", ["INSURANCE"], 40),
    ("RTO", "Registration and RTO documents", ["RTO"], 50),
    ("Accounts", "Payments, bills, bank reconciliation and refunds", [], 60),
    ("Management", "Owner and General Managers: approvals, dashboards, KPIs", ["OWNER", "GM"], 70),
    ("Administration", "Users, branches, imports and logs", ["ADMIN"], 80),
]


def default_department_id(db: Session, role) -> int | None:
    r = getattr(role, "value", role)
    for name, _, roles, _ in DEFAULTS:
        if r in roles:
            d = db.query(Department).filter(Department.name == name).first()
            return d.id if d else None
    return None


def ensure_defaults(db: Session) -> None:
    """Create the default departments once, and give every user without a department the usual one for their role."""
    if db.query(Department).count() == 0:
        for name, about, _, order in DEFAULTS:
            db.add(Department(name=name, description=about, sort_order=order))
        db.flush()
    for u in db.query(AppUser).filter(AppUser.department_id.is_(None)).all():
        u.department_id = default_department_id(db, u.role)
    db.commit()
