"""Insurance team rules: which documents a policy type needs, and the dashboard numbers."""
from fastapi import HTTPException

from app.modules.documents.models import CustomerDocument
from app.modules.handoffs.models import InsuranceCase

# policy type -> documents that MUST be uploaded before the policy can be completed
REQUIRED_DOCS = {
    "MBO_ACKO": ["TAX_INVOICE", "AADHAAR", "PAN"],
    "CUSTOMER_BAGIC": ["AADHAAR_FB", "TAX_INVOICE"],
}
LABELS = {"TAX_INVOICE": "Tax Invoice", "AADHAAR": "Aadhaar Card", "PAN": "PAN Card",
          "AADHAAR_FB": "Aadhaar Card - Front & Back (single PDF)"}
PDF_ONLY = {"AADHAAR_FB"}      # BAGIC: front and back must come together as one PDF


def required_types(case) -> list[str]:
    return REQUIRED_DOCS.get(case.policy_type, []) if case else []


def docs_of(db, lead_id) -> dict:
    """Latest uploaded document per type for the lead."""
    out = {}
    rows = (db.query(CustomerDocument).filter(CustomerDocument.lead_id == lead_id,
            CustomerDocument.doc_type.in_(list(LABELS))).order_by(CustomerDocument.uploaded_at.asc()).all())
    for d in rows:
        out[d.doc_type] = d
    return out


def checklist(db, lead, case) -> list[dict]:
    have = docs_of(db, lead.lead_id)
    out = []
    for t in required_types(case):
        d = have.get(t)
        out.append({"doc_type": t, "label": LABELS[t], "pdf_only": t in PDF_ONLY, "uploaded": bool(d),
                    "doc_id": d.id if d else None, "file_name": d.original_name if d else None,
                    "uploaded_at": d.uploaded_at if d else None,
                    "uploaded_by": d.uploaded_by.full_name if d and d.uploaded_by else None})
    return out


def missing_documents(db, lead, case) -> list[str]:
    return [c["label"] for c in checklist(db, lead, case) if not c["uploaded"]]


def doc_status(db, lead, case) -> str:
    """NO_POLICY_TYPE / PENDING / COMPLETE"""
    if not case or case.policy_type not in REQUIRED_DOCS:
        return "NO_POLICY_TYPE"
    return "COMPLETE" if not missing_documents(db, lead, case) else "PENDING"


def check_upload(case, doc_type: str, filename: str) -> None:
    if case.policy_type not in REQUIRED_DOCS:
        raise HTTPException(400, "Select the insurance policy type first")
    if doc_type not in REQUIRED_DOCS[case.policy_type]:
        raise HTTPException(400, "This document is not needed for the selected policy type")
    if doc_type in PDF_ONLY and not (filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "Aadhaar front and back must be uploaded together as ONE PDF")
