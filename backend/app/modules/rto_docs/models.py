from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String

from app.core.database import Base, now_ist


class RtoDocProfile(Base):
    """Which RTO paper-set a customer needs: own house / rented (registered or notarized agreement),
    and whether the mobile number is linked to Aadhaar. One row per lead; exists before the RTO case does."""
    __tablename__ = "rto_doc_profile"
    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer, ForeignKey("lead.lead_id"), unique=True, nullable=False)
    residence = Column(String)                 # OWN / RENTED
    rent_option = Column(String)               # REGISTERED / NOTARIZED (when RENTED)
    aadhaar_mobile_linked = Column(Boolean)    # mobile number linked to Aadhaar confirmed
    updated_by_user_id = Column(Integer, ForeignKey("app_user.user_id"))
    updated_at = Column(DateTime, default=now_ist, onupdate=now_ist)
