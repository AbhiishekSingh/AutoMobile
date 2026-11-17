"""RTO document checklist (from the RTO requirement file). Papers must be PDF, at most 100 KB each."""
from app.modules.documents.models import CustomerDocument

MAX_KB = 100
LABELS = {
    "TAX_INVOICE": "Tax Invoice", "AADHAAR": "Aadhaar Card", "PAN": "PAN Card",
    "ELECTRICITY_BILL": "Electricity Bill (address must match Aadhaar)", "PHOTO": "Passport-size Photograph",
    "VOTER_ID": "Voter ID Card", "REGISTERED_RENT_AGREEMENT": "Registered Rent Agreement", "INDEX_II": "Index II",
    "POLICE_NOC": "Police NOC", "NOTARIZED_RENT_AGREEMENT": "Notarized Rent Agreement",
}
RENT_PAPERS = ("REGISTERED_RENT_AGREEMENT", "NOTARIZED_RENT_AGREEMENT")
BASE = ["TAX_INVOICE", "AADHAAR", "PAN", "ELECTRICITY_BILL", "PHOTO", "VOTER_ID"]
RENT = {"REGISTERED": ["REGISTERED_RENT_AGREEMENT", "INDEX_II", "POLICE_NOC"],
        "NOTARIZED": ["NOTARIZED_RENT_AGREEMENT", "POLICE_NOC"]}


def required(profile) -> list[str]:
    out = list(BASE)
    if profile and profile.residence == "RENTED" and profile.rent_option in RENT:
        out += RENT[profile.rent_option]
    return out


def checklist(db, lead_id, profile) -> list[dict]:
    have = {}
    for d in (db.query(CustomerDocument).filter(CustomerDocument.lead_id == lead_id, CustomerDocument.doc_type.in_(list(LABELS)))
              .order_by(CustomerDocument.uploaded_at.asc()).all()):
        have[d.doc_type] = d
    # the Rent Agreement uploaded in Customer documents (generic type) is the same paper as the Registered /
    # Notarized one asked here, so it ticks that line too
    kyc_rent = (db.query(CustomerDocument).filter(CustomerDocument.lead_id == lead_id, CustomerDocument.doc_type == "RENT_AGREEMENT")
                .order_by(CustomerDocument.uploaded_at.desc()).first())
    out = []
    for t in required(profile):
        d = have.get(t)
        via_kyc = False
        if not d and t in RENT_PAPERS and kyc_rent:
            d, via_kyc = kyc_rent, True
        out.append({"via_kyc": via_kyc, "doc_type": t, "label": LABELS[t], "uploaded": bool(d), "doc_id": d.id if d else None,
                    "file_name": d.original_name if d else None, "size_bytes": d.size_bytes if d else None,
                    "content_type": d.content_type if d else None, "uploaded_at": d.uploaded_at if d else None,
                    "uploaded_by": d.uploaded_by.full_name if d and d.uploaded_by else None})
    return out


def missing(db, lead_id, profile) -> list[str]:
    m = [c["label"] for c in checklist(db, lead_id, profile) if not c["uploaded"]]
    if not (profile and profile.aadhaar_mobile_linked):
        m.append("Mobile number linked to Aadhaar (confirm)")
    if profile and profile.residence == "RENTED" and profile.rent_option not in RENT:
        m.append("Rent agreement type (Registered / Notarized)")
    return m


def status(db, lead_id, profile) -> str:
    return "COMPLETE" if not missing(db, lead_id, profile) else "PENDING"
