"""WhatsApp send log + the dealership links used in messages."""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint

from app.core.database import Base, now_ist


class WhatsappMessage(Base):
    __tablename__ = "whatsapp_message"
    id = Column(Integer, primary_key=True)
    kind = Column(String, nullable=False, index=True)     # WELCOME / RECEIPT / INSURANCE / DELIVERY / ENGAGEMENT / REVIEW / TEST_RIDE
    ref_id = Column(Integer)                              # payment_id / test_ride_id / lead_id depending on kind
    lead_id = Column(Integer, ForeignKey("lead.lead_id"), index=True)
    customer_id = Column(Integer, ForeignKey("customer.customer_id"))
    branch_id = Column(Integer, ForeignKey("branch.branch_id"))
    recipient = Column(String, nullable=False, default="CUSTOMER")    # CUSTOMER / PBA
    to_number = Column(String)
    template = Column(String)
    body_params = Column(Text)                            # JSON list, kept so a retry sends the same text
    lang = Column(String)                                 # receipt language, when relevant
    status = Column(String, nullable=False, default="PENDING")   # SENT / DELIVERED / READ / FAILED
    wa_message_id = Column(String, index=True)
    error = Column(Text)
    auto = Column(Integer, default=0)                     # 1 = sent automatically by the system
    retry_of_id = Column(Integer, ForeignKey("whatsapp_message.id"))
    created_by_user_id = Column(Integer, ForeignKey("app_user.user_id"))
    created_at = Column(DateTime, default=now_ist, nullable=False, index=True)
    delivered_at = Column(DateTime)
    read_at = Column(DateTime)


class DealerLink(Base):
    """Links editable by Owner/GM. branch_id NULL = the default for every showroom;
    a row with a branch overrides it for that showroom (e.g. its own Google review link)."""
    __tablename__ = "dealer_link"
    __table_args__ = (UniqueConstraint("branch_id", "key", name="uq_dealer_link"),)
    id = Column(Integer, primary_key=True)
    branch_id = Column(Integer, ForeignKey("branch.branch_id"))
    key = Column(String, nullable=False)        # GOOGLE_REVIEW_URL / INSTAGRAM_URL / KTM_APP_URL
    value = Column(String)
    updated_by_user_id = Column(Integer, ForeignKey("app_user.user_id"))
    updated_at = Column(DateTime, default=now_ist, onupdate=now_ist)
