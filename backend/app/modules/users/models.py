import enum
from datetime import datetime

from sqlalchemy import (Boolean, Column, DateTime, Enum, ForeignKey, Integer,
                        String)
from sqlalchemy.orm import relationship

from app.core.database import Base, now_ist


class Role(str, enum.Enum):
    OWNER = "OWNER"
    GM = "GM"
    PBA = "PBA"
    CRE = "CRE"
    RTO = "RTO"
    ADMIN = "ADMIN"


class Branch(Base):
    __tablename__ = "branch"
    branch_id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    dealer_code = Column(String, unique=True)
    city = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=now_ist)
    updated_at = Column(DateTime, default=now_ist, onupdate=now_ist)

    users = relationship("AppUser", back_populates="branch")


class AppUser(Base):
    __tablename__ = "app_user"
    user_id = Column(Integer, primary_key=True, index=True)
    login_id = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(Role), nullable=False)
    branch_id = Column(Integer, ForeignKey("branch.branch_id"))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=now_ist)
    updated_at = Column(DateTime, default=now_ist, onupdate=now_ist)

    branch = relationship("Branch", back_populates="users")