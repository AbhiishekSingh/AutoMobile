"""Create tables and seed branches + one user per role.

Run once:  python -m app.seed
Default passwords are for local development only — change them in production.
"""
from app.core.database import Base, SessionLocal, engine
from app.db import base as _base  # register models
from app.modules.users.models import AppUser, Branch, Role
from app.core.security import hash_password

BRANCHES = [
    {"name": "S.K KTM Thane", "dealer_code": "C12746", "city": "Thane"},
    {"name": "S.K KTM Chembur", "dealer_code": "A12746", "city": "Mumbai"},
    {"name": "S.K KTM Dombivali", "dealer_code": "D12746", "city": "Dombivali"},
    {"name": "S.K KTM Ulhasnagar", "dealer_code": "U12746", "city": "Ulhasnagar"},
    {"name": "S.K KTM Nerul", "dealer_code": "BRN01", "city": "Navi Mumbai"},
    {"name": "S.K KTM Bhiwandi", "dealer_code": "B12746", "city": "Bhiwandi"},
]

# login_id, full_name, password, role
USERS = [
    ("OWNER",   "Suresh Kadam",   "owner123", Role.OWNER),
    ("GM-001",  "Deepak Rane",    "gm123",    Role.GM),
    ("PBA-014", "Rohan Sur",      "pba123",   Role.PBA),
    ("CRE-003", "Sneha Kulkarni", "cre123",   Role.CRE),
    ("RTO-001", "Ramesh Patil",   "rto123",   Role.RTO),
    ("ADMIN",   "Farhan Sheikh",  "admin123", Role.ADMIN),
]


def run():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(Branch).count() == 0:
            for b in BRANCHES:
                db.add(Branch(**b, is_active=True))
            db.commit()
        thane = db.query(Branch).filter(Branch.name == "S.K KTM Thane").first()

        for login_id, name, pw, role in USERS:
            if db.query(AppUser).filter(AppUser.login_id == login_id).first():
                continue
            db.add(AppUser(
                login_id=login_id,
                full_name=name,
                email=f"{login_id.lower()}@skautomobiles.in",
                hashed_password=hash_password(pw),
                role=role,
                branch_id=thane.branch_id if thane else None,
                is_active=True,
            ))
        db.commit()
        print("Seed complete. Logins:")
        for login_id, _, pw, role in USERS:
            print(f"  {login_id:10} / {pw:10} ({role.value})")
    finally:
        db.close()


if __name__ == "__main__":
    run()
