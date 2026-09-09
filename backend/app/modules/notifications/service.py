"""Write-side rules for notifications.

This is the ONLY place that should call `Notification(...)` / `db.add(Notification...)`
elsewhere in the codebase — routers/services should go through `create_notification`
(or `create_bulk_assignment_notifications` for CSV imports) so every edge case below
is handled consistently no matter which feature triggers a notification later.

Edge cases handled here:
  - No recipient (assigned_user_id is None)              -> skipped, nothing to notify.
  - Recipient is the same person who did the action       -> skipped (no self-notifying).
  - Recipient doesn't exist / was deleted                 -> skipped (defensive; FK would
                                                               also reject it, but we check
                                                               first so a bad id never raises
                                                               mid-transaction).
  - Recipient account is deactivated                      -> skipped (they can't log in to
                                                               read it, so it would just be
                                                               clutter waiting for reactivation).
  - Bulk (CSV import) assigning many leads to one person   -> collapsed into ONE summary
                                                               notification per person per
                                                               import, not one row per lead.
"""
from sqlalchemy.orm import Session

from app.modules.notifications.models import Notification, NotificationType
from app.modules.users.models import AppUser


def _valid_recipient(db: Session, user_id: int | None, actor_user_id: int | None) -> bool:
    if not user_id:
        return False
    if actor_user_id and user_id == actor_user_id:
        return False
    recipient = db.get(AppUser, user_id)
    return bool(recipient and recipient.is_active)


def create_notification(db: Session, *, user_id: int | None, type_: NotificationType,
                        title: str, message: str | None = None,
                        reference_type: str | None = None, reference_id: int | None = None,
                        actor_user_id: int | None = None) -> Notification | None:
    """Create (add, not commit) a single notification for `user_id`.

    `actor_user_id` is whoever performed the action that triggered this — pass it
    so we never notify someone about something they did themselves. Caller is
    expected to `db.commit()` as part of its own transaction (so the notification
    is atomic with whatever action created it: if the lead update rolls back, the
    notification never existed either).
    """
    if not _valid_recipient(db, user_id, actor_user_id):
        return None
    n = Notification(user_id=user_id, type=type_.value, title=title, message=message,
                     reference_type=reference_type, reference_id=reference_id)
    db.add(n)
    return n


def create_bulk_assignment_notifications(db: Session, *, counts_by_user_id: dict[int, int],
                                         actor_user_id: int | None = None) -> int:
    """One summary notification per recipient, e.g. "42 new leads assigned to you"
    from a CSV import — instead of flooding someone with hundreds of individual rows.

    `counts_by_user_id` maps assigned_user_id -> number of leads assigned to them
    in this import batch. Returns how many notifications were actually created
    (recipients that failed validation are silently skipped, same as the single-
    notification path).
    """
    created = 0
    for user_id, count in counts_by_user_id.items():
        if count <= 0:
            continue
        noun = "lead" if count == 1 else "leads"
        n = create_notification(
            db, user_id=user_id, type_=NotificationType.LEADS_BULK_ASSIGNED,
            title=f"{count} new {noun} assigned to you",
            message=f"{count} {noun} were assigned to you from a bulk import.",
            reference_type="lead_import", reference_id=None,
            actor_user_id=actor_user_id,
        )
        if n is not None:
            created += 1
    return created
