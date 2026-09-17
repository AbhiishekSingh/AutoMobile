"""The one function every editing endpoint should call: `record_changes()`.

Usage pattern (see leads/router.py and users/router.py for real hookups):

    before = {f: getattr(obj, f) for f in TRACKED_FIELDS}
    ...apply the edits to obj...
    record_changes(db, entity_type="customer", entity_id=obj.id,
                   before=before, after=obj, fields=TRACKED_FIELDS,
                   changed_by_user_id=current_user.user_id)

Only fields whose value actually changed get a row — saving a form where
nothing was actually edited produces zero audit rows, not a false "no-op
edit" entry.
"""
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditLog


def _stringify(value):
    if value is None:
        return None
    # Enums (e.g. Role, EnquiryStage) should log as "PBA", not "Role.PBA".
    if hasattr(value, "value") and not isinstance(value, (int, float, str)):
        return str(value.value)
    return str(value)


def record_changes(db: Session, *, entity_type: str, entity_id: int, before: dict,
                   after, fields: tuple, changed_by_user_id: int | None) -> int:
    """Compare `before` (a plain dict captured pre-edit) against the current
    attribute values on `after` (the live ORM object, post-edit) for each
    field in `fields`, and add one AuditLog row per field that actually
    changed. Does not commit — caller commits alongside the edit itself, so
    the audit trail and the actual change are always atomic (both happen or
    neither does).

    Returns how many audit rows were added.
    """
    added = 0
    for field in fields:
        old_val = before.get(field)
        new_val = getattr(after, field, None)
        if old_val == new_val:
            continue   # nothing actually changed for this field — no row
        db.add(AuditLog(
            entity_type=entity_type, entity_id=entity_id, field_name=field,
            old_value=_stringify(old_val), new_value=_stringify(new_val),
            changed_by_user_id=changed_by_user_id,
        ))
        added += 1
    return added
