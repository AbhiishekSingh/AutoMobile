"""Read the dealer-system 'TAX INVOICE (Vehicle)' PDF so the PBA does not retype it.

Only reads the text layer (no OCR). Picks values by their labels (Invoice No., Chassis No. ...). The Aadhaar number printed on
the invoice is deliberately ignored: it is never extracted or stored.
"""
import re
from datetime import date, datetime
from io import BytesIO

MONEY = re.compile(r"\d{1,3}(?:,\d{3})+\.\d{2}|\d+\.\d{2}")


def _first(pattern, text, flags=0):
    m = re.search(pattern, text, flags)
    return m.group(1).strip() if m else None


def pdf_text(data: bytes) -> str:
    from pypdf import PdfReader
    try:
        r = PdfReader(BytesIO(data))
        return "\n".join((p.extract_text() or "") for p in r.pages[:3])
    except Exception:
        return ""


def parse(text: str) -> dict:
    t = text.replace("\r", "")
    name_raw = _first(r"Customer Name[ \t]*:[ \t]*([^\n]+)", t) or ""
    code = _first(r"\((CUS-[\w-]+)\)", name_raw)
    name = re.sub(r"\(CUS-[\w-]+\)", "", name_raw).strip() or None
    d = _first(r"Invoice Date[ \t]*:[ \t]*(\d{2}/\d{2}/\d{4})", t)
    inv_date = None
    if d:
        try:
            inv_date = datetime.strptime(d, "%d/%m/%Y").date()
        except ValueError:
            pass
    amounts = [float(x.replace(",", "")) for x in MONEY.findall(t.split("AMOUNT IN WORDS")[0] if "AMOUNT IN WORDS" in t else t)]
    ro = _first(r"Round Off[ \t]*([\d.]+)", t)
    total = None
    if amounts:
        total = round(max(amounts) + (float(ro) if ro else 0), 2)
    return {
        "dealer_invoice": bool(re.search(r"TAX INVOICE", t, re.I)),
        "invoice_no": _first(r"Invoice No\.[ \t]*:[ \t]*([A-Z0-9/-]+)", t),
        "invoice_date": inv_date,
        "chassis_no": _first(r"Chassis No\.?[ \t]*:[ \t]*([A-Z0-9]{10,20})", t),
        "engine_no": _first(r"Engine[ \t]*:[ \t]*([A-Z0-9\-*/]{5,25})", t),
        "color": _first(r"Color[ \t]*:[ \t]*([A-Za-z ]+)", t),
        "hypothecation": _first(r"H\.P\.? ?Name[ \t]*:[ \t]*([^\n]+)", t),
        "dealer_booking_no": _first(r"Booking No\.?[ \t]*:[ \t]*([A-Z0-9]+)", t),
        "customer_name": name, "customer_code": code,
        "phone": _first(r"(?<![\d])Phone[ \t]*:[ \t]*(\d{10})\b", t),
        "model": _first(r"((?:New )?[A-Za-z]+ ?\d{2,3}[A-Za-z]*(?: \(\d{4}\))?)[ \t]*/[ \t]*\d{8}", t.replace("\n", " ")),
        "total_amount": total,
    }


def _tokens(s: str) -> set:
    return {w for w in re.split(r"[^A-Z]+", (s or "").upper()) if len(w) > 1}


def checks(f: dict, lead, other_chassis_owner=None) -> list[dict]:
    """Compare the invoice with the CRM record. level: ok / warn."""
    out = []
    phone = re.sub(r"\D", "", lead.customer.phone or "")[-10:]
    if f.get("phone"):
        out.append({"field": "Customer mobile", "level": "ok" if f["phone"] == phone else "warn",
                    "text": "matches the CRM" if f["phone"] == phone else f"invoice has {f['phone']}, CRM has {phone or 'none'}"})
    if f.get("customer_name"):
        a, b = _tokens(f["customer_name"]), _tokens(lead.customer.full_name)
        ok = bool(a and b) and len(a & b) / min(len(a), len(b)) >= 0.5
        out.append({"field": "Customer name", "level": "ok" if ok else "warn",
                    "text": "matches the CRM" if ok else f"invoice: {f['customer_name']} — CRM: {lead.customer.full_name}"})
    if f.get("color") and lead.color:
        ok = f["color"].strip().lower() == lead.color.strip().lower()
        out.append({"field": "Colour", "level": "ok" if ok else "warn",
                    "text": "matches the CRM" if ok else f"invoice: {f['color']} — CRM: {lead.color}"})
    if f.get("model") and lead.model:
        nums = re.findall(r"\d{3}", lead.model.name)
        ok = all(n in f["model"] for n in nums) if nums else True   # e.g. '200' must appear in the invoice's model
        out.append({"field": "Model", "level": "ok" if ok else "warn",
                    "text": "matches the CRM" if ok else f"invoice: {f['model']} — CRM: {lead.model.name}"})
    if other_chassis_owner:
        out.append({"field": "Chassis / engine", "level": "warn", "text": f"already used on another customer's invoice ({other_chassis_owner})"})
    return out
