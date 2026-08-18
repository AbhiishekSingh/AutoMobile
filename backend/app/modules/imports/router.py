"""Admin-only: upload a LeadSquared CSV to bulk-import leads."""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_roles
from app.modules.imports.service import import_leads_csv
from app.modules.users.models import Branch

router = APIRouter(prefix="/admin", tags=["admin-imports"])


@router.get("/branches", dependencies=[Depends(require_roles("ADMIN"))])
def branches(db: Session = Depends(get_db)):
    rows = db.query(Branch).order_by(Branch.name).all()
    return [{"branch_id": b.branch_id, "name": b.name} for b in rows]


@router.post("/leads/import", dependencies=[Depends(require_roles("ADMIN"))])
async def import_leads(
    file: UploadFile = File(...),
    branch_id: int | None = Form(None),   # optional: force one branch for the whole file
    db: Session = Depends(get_db),
):
    name = (file.filename or "").lower()
    if not name.endswith(".csv"):
        raise HTTPException(400, "Please upload a .csv file")
    content = await file.read()
    if not content:
        raise HTTPException(400, "The file is empty")
    summary = import_leads_csv(content, db, default_branch_id=branch_id)
    return {"filename": file.filename, **summary}