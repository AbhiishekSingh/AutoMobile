"""Admin-only: upload a LeadSquared CSV or Excel (.xlsx/.xls) file to bulk-import leads."""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.modules.imports.service import import_leads_file
from app.modules.users.models import AppUser, Branch

router = APIRouter(prefix="/admin", tags=["admin-imports"])

ALLOWED_EXTENSIONS = (".csv", ".xlsx", ".xls")


@router.get("/branches", dependencies=[Depends(require_roles("ADMIN"))])
def branches(db: Session = Depends(get_db)):
    rows = db.query(Branch).order_by(Branch.name).all()
    return [{"branch_id": b.branch_id, "name": b.name} for b in rows]


@router.post("/leads/import", dependencies=[Depends(require_roles("ADMIN"))])
async def import_leads(
    file: UploadFile = File(...),
    branch_id: int | None = Form(None),   # optional: force one branch for the whole file
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    name = (file.filename or "").lower()
    if not name.endswith(ALLOWED_EXTENSIONS):
        raise HTTPException(400, "Please upload a .csv, .xlsx, or .xls file")
    content = await file.read()
    if not content:
        raise HTTPException(400, "The file is empty")
    try:
        summary = import_leads_file(content, file.filename, db, default_branch_id=branch_id,
                                    actor_user_id=user.user_id)
    except Exception as e:
        # A corrupt/unreadable workbook (wrong format inside a .xlsx extension,
        # password-protected file, etc.) shouldn't come back as a raw 500 —
        # nothing has been committed at this point, so it's safe to just report it.
        db.rollback()
        raise HTTPException(400, f"Couldn't read this file: {e}")
    return {"filename": file.filename, **summary}