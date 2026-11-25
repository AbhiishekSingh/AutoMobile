import enum
from datetime import datetime

from sqlalchemy import (Boolean, Column, DateTime, Enum, ForeignKey, Integer,
                        String, UniqueConstraint)
from sqlalchemy.orm import relationship

from app.core.database import Base, now_ist


class Role(str, enum.Enum):
    OWNER = "OWNER"
    GM = "GM"
    PBA = "PBA"
    CRE = "CRE"
    RTO = "RTO"
    ADMIN = "ADMIN"
    INSURANCE = "INSURANCE"   # separate insurance team login (all branches)
    BRANCH = "BRANCH"   # shared branch login; the PBAs working under it are PBA "profiles"


class Branch(Base):
    __tablename__ = "branch"
    branch_id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    dealer_code = Column(String, unique=True)
    city = Column(String)
    address = Column(String)
    contact_no = Column(String)
    whatsapp_number = Column(String)   # branch number that receives PBA alerts
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=now_ist)
    updated_at = Column(DateTime, default=now_ist, onupdate=now_ist)

    users = relationship("AppUser", back_populates="branch")


class Department(Base):
    """A team the dealership manages (Sales, Customer Relations, Accounts...). A user has a role (what they may do) and a
    department (which team they belong to); the two are separate so a team can hold more than one role, or a role that
    has no screen of its own (Accounts)."""
    __tablename__ = "department"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    description = Column(String)
    head_user_id = Column(Integer)          # the department head (a user); plain id so users and departments don't point at each other
    sort_order = Column(Integer, default=100, nullable=False, server_default="100")
    is_active = Column(Boolean, default=True, nullable=False, server_default="true")
    created_at = Column(DateTime, default=now_ist)


class AppUser(Base):
    __tablename__ = "app_user"
    user_id = Column(Integer, primary_key=True, index=True)
    login_id = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True)
    phone = Column(String)       # mobile / WhatsApp number (used for WhatsApp alerts to staff)
    hashed_password = Column(String, nullable=False)
    # A PBA "profile" has no login of its own (login_enabled False): the PBA works under their branch's
    # shared login and proves who they are with a personal PIN.
    login_enabled = Column(Boolean, default=True, nullable=False, server_default="true")
    pin_hash = Column(String)
    # How this PBA appears in LeadSquared exports (Salesperson email / name), when it differs from the CRM's own
    ls_email = Column(String)
    ls_name = Column(String)
    pin_failed = Column(Integer, default=0, nullable=False, server_default="0")   # wrong PINs in a row
    pin_locked_until = Column(DateTime)
    role = Column(Enum(Role), nullable=False)
    branch_id = Column(Integer, ForeignKey("branch.branch_id"))
    department_id = Column(Integer, ForeignKey("department.id"))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=now_ist)
    updated_at = Column(DateTime, default=now_ist, onupdate=now_ist)

    branch = relationship("Branch", back_populates="users")
    department = relationship("Department", lazy="joined")
    # CRE only: the 1-2 branches this CRE covers (set by Admin on the Users
    # page). Other roles have none and use `branch_id` above.
    branch_links = relationship("UserBranch", cascade="all, delete-orphan",
                                lazy="selectin", order_by="UserBranch.branch_id")

    via_branch = False      # set per request when this PBA is working under the branch login

    @property
    def department_name(self):
        return self.department.name if self.department else None

    @property
    def has_pin(self) -> bool:
        return bool(self.pin_hash)

    @property
    def branch_ids(self) -> list[int]:
        """Branches a CRE covers (empty for every other role)."""
        return [link.branch_id for link in self.branch_links]


class UserBranch(Base):
    """Which branches a CRE covers. One row per (CRE, branch).

    A CRE can have 1 or 2 branches (CRE_MAX_BRANCHES in users/access.py), and
    two CREs may share a branch (e.g. to cover leave). Created on startup by
    app/db/schema_updates.py — no manual SQL needed.
    """
    __tablename__ = "user_branch"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("app_user.user_id", ondelete="CASCADE"),
                     nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branch.branch_id"), nullable=False)
    created_at = Column(DateTime, default=now_ist)

    branch = relationship("Branch")

    __table_args__ = (UniqueConstraint("user_id", "branch_id", name="uq_user_branch"),)