from app.modules.sync_log.models import SyncFailure


def log_failure(db, source, message, *, ref_type=None, ref_id=None, ref_label=None, user=None):
    """Add a failure row to the session (committed with the caller's transaction). Never raises."""
    try:
        db.add(SyncFailure(source=source, message=str(message)[:1000], ref_type=ref_type, ref_id=ref_id,
                           ref_label=(ref_label or None), created_by_user_id=getattr(user, "user_id", None)))
    except Exception:
        pass
