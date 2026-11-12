"""Dealership links (Google review, Instagram, KTM app): showroom-specific value, else the default."""
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.whatsapp.models import DealerLink


def get_link(db: Session, branch_id, key: str) -> str | None:
    rows = db.query(DealerLink).filter(DealerLink.key == key,
                                       (DealerLink.branch_id == branch_id) | (DealerLink.branch_id.is_(None))).all()
    by = {r.branch_id: (r.value or "").strip() for r in rows}
    v = by.get(branch_id) or by.get(None)
    if not v and key == "GOOGLE_REVIEW_URL":
        v = settings.GOOGLE_REVIEW_URL or None
    return v or None
