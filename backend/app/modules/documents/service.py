"""Rules for customer document uploads — the one place they live.

  Size     : at most settings.MAX_UPLOAD_MB per file (default 5 MB). The file
             is read in chunks and rejected as soon as it passes the limit, so
             a huge upload never fills memory or disk.
  Types    : PDF, JPG/JPEG, PNG only. Checked by extension AND by the file's
             first bytes, so a renamed .exe can't get through as "aadhaar.pdf".
  Per lead : at most MAX_FILES_PER_LEAD files, so one lead can't fill the disk.
  Storage  : <UPLOAD_DIR>/customers/<customer_id>/<random>.<ext> — a random
             name, never the uploaded name, so names can't clash or escape
             the folder.
"""
import os
import uuid

from fastapi import HTTPException, UploadFile

from app.core.config import settings
from app.modules.documents.models import DocumentType

MAX_FILES_PER_LEAD = 30
CHUNK = 64 * 1024

# extension -> (content type, magic bytes the file must start with)
ALLOWED = {
    ".pdf": ("application/pdf", (b"%PDF",)),
    ".jpg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".jpeg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".png": ("image/png", (b"\x89PNG\r\n\x1a\n",)),
}

# Labels + checklist shown on the Customer Details page. "required" = KYC
# the PBA must collect at booking. Electricity bill and rent agreement are
# one requirement: either one is enough (own house / rented house).
DOC_TYPES = [
    {"value": DocumentType.AADHAAR.value, "label": "Aadhaar Card", "required": True},
    {"value": DocumentType.PAN.value, "label": "PAN Card", "required": True},
    {"value": DocumentType.ELECTRICITY_BILL.value, "label": "Electricity Bill (own house)",
     "required": True, "either_with": DocumentType.RENT_AGREEMENT.value},
    {"value": DocumentType.RENT_AGREEMENT.value, "label": "Rent Agreement (rented house)",
     "required": True, "either_with": DocumentType.ELECTRICITY_BILL.value},
    {"value": DocumentType.BANK_STATEMENT.value, "label": "Bank Statement (6 months)", "required": False},
    {"value": DocumentType.PHOTO.value, "label": "Photo (2)", "required": False},
    {"value": DocumentType.CHEQUE.value, "label": "Cheque (2)", "required": False},
    {"value": DocumentType.GST_CERTIFICATE.value, "label": "GST Certificate", "required": False},
    {"value": DocumentType.IT_RETURN.value, "label": "IT Return", "required": False},
    {"value": DocumentType.OTHER.value, "label": "Other", "required": False},
]


def max_bytes() -> int:
    return settings.MAX_UPLOAD_MB * 1024 * 1024


def upload_root() -> str:
    return os.path.abspath(settings.UPLOAD_DIR)


def check_doc_type(value: str) -> str:
    try:
        return DocumentType(value).value
    except ValueError:
        raise HTTPException(400, "Please choose the document type")


def save_upload(file: UploadFile, customer_id: int) -> dict:
    """Validate and store one upload. Returns the details to save in the DB.
    Raises a 400 with a message fit to show the PBA if the file isn't allowed."""
    name = os.path.basename(file.filename or "").strip()
    ext = os.path.splitext(name)[1].lower()
    if ext not in ALLOWED:
        raise HTTPException(400, "Only PDF, JPG or PNG files can be uploaded")
    content_type, magics = ALLOWED[ext]

    limit = max_bytes()
    folder = os.path.join(upload_root(), "customers", str(customer_id))
    os.makedirs(folder, exist_ok=True)
    rel_path = os.path.join("customers", str(customer_id), f"{uuid.uuid4().hex}{ext}")
    full_path = os.path.join(upload_root(), rel_path)

    size, head = 0, b""
    try:
        with open(full_path, "wb") as out:
            while chunk := file.file.read(CHUNK):
                size += len(chunk)
                if size > limit:
                    raise HTTPException(
                        400, f"File is too large. The limit is {settings.MAX_UPLOAD_MB} MB per file")
                if len(head) < 16:
                    head += chunk[:16]
                out.write(chunk)
        if size == 0:
            raise HTTPException(400, "The file is empty")
        if not any(head.startswith(m) for m in magics):
            raise HTTPException(400, f"This file doesn't look like a real {ext[1:].upper()} file")
    except Exception:
        if os.path.exists(full_path):
            os.remove(full_path)
        raise

    return {"original_name": name or f"document{ext}", "stored_path": rel_path,
            "content_type": content_type, "size_bytes": size}


def full_path_of(stored_path: str) -> str:
    """Absolute path for a stored file, refusing anything outside UPLOAD_DIR."""
    root = upload_root()
    path = os.path.abspath(os.path.join(root, stored_path))
    if not path.startswith(root + os.sep):
        raise HTTPException(404, "File not found")
    return path


def delete_file(stored_path: str) -> None:
    try:
        os.remove(full_path_of(stored_path))
    except (FileNotFoundError, HTTPException):
        pass
