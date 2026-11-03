"""Customer document upload endpoints.

  GET    /documents/settings              types, size limit, allowed files (for the form)
  GET    /leads/{lead_id}/documents       list a lead's documents
  POST   /leads/{lead_id}/documents       upload one file (PBA / CRE)
  GET    /documents/{id}/file             view / download one file
  DELETE /documents/{id}                  remove a file (only the person who uploaded it)

Who can see a lead's documents follows the normal lead visibility rule
(app/modules/users/access.py): PBA = own leads, CRE = their branches,
Owner/GM/Admin = all. Only PBA and CRE upload.
"""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.modules.audit.service import record_changes
from app.modules.documents import service as svc
from app.modules.documents.models import CustomerDocument
from app.modules.documents.schemas import DocumentOut, DocumentSettings
from app.modules.users.access import MANAGER_ROLES, SALES_ROLES, get_visible_lead
from app.modules.users.models import AppUser

router = APIRouter(tags=["documents"])
READ_ROLES = SALES_ROLES + MANAGER_ROLES
UPLOAD_ROLES = SALES_ROLES


def _out(d: CustomerDocument) -> DocumentOut:
    return DocumentOut(id=d.id, lead_id=d.lead_id, doc_type=d.doc_type, note=d.note,
                       original_name=d.original_name, content_type=d.content_type,
                       size_bytes=d.size_bytes, uploaded_at=d.uploaded_at,
                       uploaded_by_user_id=d.uploaded_by_user_id,
                       uploaded_by=d.uploaded_by.full_name if d.uploaded_by else None)


def _visible_document(db: Session, user: AppUser, doc_id: int) -> CustomerDocument:
    doc = db.get(CustomerDocument, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    get_visible_lead(db, user, doc.lead_id)   # 404 if this user can't see the lead
    return doc


@router.get("/documents/settings", response_model=DocumentSettings,
            dependencies=[Depends(require_roles(*READ_ROLES))])
def document_settings():
    return DocumentSettings(types=svc.DOC_TYPES, max_mb=svc.settings.MAX_UPLOAD_MB,
                            allowed_extensions=sorted(svc.ALLOWED),
                            max_files_per_lead=svc.MAX_FILES_PER_LEAD)


@router.get("/leads/{lead_id}/documents", response_model=list[DocumentOut],
            dependencies=[Depends(require_roles(*READ_ROLES))])
def list_documents(lead_id: int, user: AppUser = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    get_visible_lead(db, user, lead_id)
    rows = (db.query(CustomerDocument).filter(CustomerDocument.lead_id == lead_id)
            .order_by(CustomerDocument.uploaded_at.desc()).all())
    return [_out(d) for d in rows]


@router.post("/leads/{lead_id}/documents", response_model=DocumentOut, status_code=201,
             dependencies=[Depends(require_roles(*UPLOAD_ROLES))])
def upload_document(lead_id: int, doc_type: str = Form(...), note: str | None = Form(None),
                    file: UploadFile = File(...), user: AppUser = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    lead = get_visible_lead(db, user, lead_id)
    doc_type = svc.check_doc_type(doc_type)
    count = db.query(CustomerDocument).filter(CustomerDocument.lead_id == lead_id).count()
    if count >= svc.MAX_FILES_PER_LEAD:
        raise HTTPException(400, f"This lead already has {svc.MAX_FILES_PER_LEAD} files. "
                                 f"Remove one before uploading another")

    saved = svc.save_upload(file, lead.customer_id)   # validates size + type, writes the file
    doc = CustomerDocument(lead_id=lead_id, customer_id=lead.customer_id, doc_type=doc_type,
                           note=(note or "").strip() or None, uploaded_by_user_id=user.user_id,
                           **saved)
    try:
        db.add(doc); db.flush()
        record_changes(db, entity_type="document", entity_id=doc.id,
                       before={"doc_type": None, "original_name": None}, after=doc,
                       fields=("doc_type", "original_name"), changed_by_user_id=user.user_id)
        db.commit()
    except Exception:
        db.rollback()
        svc.delete_file(saved["stored_path"])   # don't leave an orphan file behind
        raise
    db.refresh(doc)
    return _out(doc)


@router.get("/documents/{doc_id}/file", dependencies=[Depends(require_roles(*READ_ROLES))])
def get_document_file(doc_id: int, download: bool = False,
                      user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = _visible_document(db, user, doc_id)
    path = svc.full_path_of(doc.stored_path)
    return FileResponse(path, media_type=doc.content_type, filename=doc.original_name,
                        content_disposition_type="attachment" if download else "inline")


@router.delete("/documents/{doc_id}", dependencies=[Depends(require_roles(*UPLOAD_ROLES))])
def delete_document(doc_id: int, user: AppUser = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    doc = _visible_document(db, user, doc_id)
    if doc.uploaded_by_user_id != user.user_id:
        raise HTTPException(403, "Only the person who uploaded this file can remove it")
    before = {"doc_type": doc.doc_type, "original_name": doc.original_name}
    stored = doc.stored_path
    db.delete(doc)
    record_changes(db, entity_type="document", entity_id=doc_id, before=before,
                   after=type("Gone", (), {"doc_type": None, "original_name": None})(),
                   fields=("doc_type", "original_name"), changed_by_user_id=user.user_id)
    db.commit()
    svc.delete_file(stored)
    return {"ok": True}
