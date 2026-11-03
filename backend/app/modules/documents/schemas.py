from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DocumentTypeOption(BaseModel):
    value: str
    label: str
    required: bool
    either_with: Optional[str] = None


class DocumentSettings(BaseModel):
    """What the upload form needs: types, size limit, allowed files."""
    types: list[DocumentTypeOption]
    max_mb: int
    allowed_extensions: list[str]
    max_files_per_lead: int


class DocumentOut(BaseModel):
    id: int
    lead_id: int
    doc_type: str
    note: Optional[str] = None
    original_name: str
    content_type: str
    size_bytes: int
    uploaded_by: Optional[str] = None
    uploaded_by_user_id: Optional[int] = None
    uploaded_at: datetime
