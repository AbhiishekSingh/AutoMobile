"""Payment receipt PDF (one per payment), in English or Marathi.

Header comes from the lead's Branch row (name, address, phone). Marathi needs
two things on the server that plain reportlab does not have:
  1. `pip install uharfbuzz`   (joins Devanagari letters correctly)
  2. a Devanagari font file at app/static/fonts/NotoSansDevanagari-Regular.ttf
     (and optionally ...-Bold.ttf). Any Devanagari TTF works if renamed.
If either is missing, `marathi_ready()` is False and the API says so, instead
of producing a broken PDF.
"""
import io
import os
from datetime import date, datetime
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

STATIC = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static")
FONT_DIR = os.path.join(STATIC, "fonts")
NAVY = colors.HexColor("#2b2560")
ORANGE = colors.HexColor("#f5820c")

# Marathi wording (machine-drafted — have a Marathi speaker approve before go-live)
LABELS = {
    "en": {"title": "PAYMENT RECEIPT", "receipt_no": "Receipt No", "date": "Date",
           "booking_no": "Booking No", "quotation_no": "Quotation No",
           "received_from": "Received from", "mobile": "Mobile", "vehicle": "Vehicle",
           "mode": "Payment mode", "reference": "Reference / UTR / Cheque", "bank": "Finance bank",
           "amount": "Amount received", "in_words": "In words", "total": "Total vehicle cost",
           "paid": "Total paid till date", "outstanding": "Balance outstanding",
           "status": "Payment status", "remark": "Remark", "by": "Received by",
           "sign": "Authorised signatory", "note": "This is a computer-generated receipt.",
           "PENDING": "Pending", "PARTIALLY_PAID": "Partially Paid", "PAID": "Paid",
           "phone": "Phone"},
    "mr": {"title": "पेमेंट पावती", "receipt_no": "पावती क्रमांक", "date": "दिनांक",
           "booking_no": "बुकिंग क्रमांक", "quotation_no": "कोटेशन क्रमांक",
           "received_from": "यांच्याकडून स्वीकारले", "mobile": "मोबाईल", "vehicle": "वाहन",
           "mode": "पेमेंट पद्धत", "reference": "संदर्भ / UTR / चेक क्रमांक", "bank": "फायनान्स बँक",
           "amount": "स्वीकारलेली रक्कम", "in_words": "अक्षरी", "total": "वाहनाची एकूण किंमत",
           "paid": "आजपर्यंत भरलेली एकूण रक्कम", "outstanding": "शिल्लक रक्कम",
           "status": "पेमेंट स्थिती", "remark": "शेरा", "by": "स्वीकारणारा",
           "sign": "अधिकृत स्वाक्षरी", "note": "ही संगणकीय पावती आहे.",
           "PENDING": "प्रलंबित", "PARTIALLY_PAID": "अंशतः भरलेले", "PAID": "पूर्ण भरलेले",
           "phone": "फोन"},
}
MODE_MR = {"CASH": "रोख", "CHEQUE": "चेक", "UPI": "UPI", "BANK_TRANSFER": "बँक ट्रान्सफर",
           "CARD": "कार्ड", "FINANCE": "फायनान्स"}

_MR_REG = os.path.join(FONT_DIR, "NotoSansDevanagari-Regular.ttf")
_MR_BOLD = os.path.join(FONT_DIR, "NotoSansDevanagari-Bold.ttf")


def marathi_ready() -> bool:
    try:
        import uharfbuzz  # noqa: F401
    except Exception:
        return False
    return os.path.exists(_MR_REG)


def _fonts(lang: str):
    """(regular, bold) font names for the language."""
    if lang != "mr":
        return "Helvetica", "Helvetica-Bold"
    if "NotoMr" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("NotoMr", _MR_REG))
        pdfmetrics.registerFont(TTFont("NotoMr-B", _MR_BOLD if os.path.exists(_MR_BOLD) else _MR_REG))
    return "NotoMr", "NotoMr-B"


# ---- amount in words (Indian numbering) ----
_ONES = ("Zero One Two Three Four Five Six Seven Eight Nine Ten Eleven Twelve Thirteen Fourteen "
         "Fifteen Sixteen Seventeen Eighteen Nineteen").split()
_TENS = "_ _ Twenty Thirty Forty Fifty Sixty Seventy Eighty Ninety".split()


def _below_1000(n: int) -> str:
    out = []
    if n >= 100:
        out.append(_ONES[n // 100] + " Hundred"); n %= 100
    if n >= 20:
        out.append(_TENS[n // 10] + ((" " + _ONES[n % 10]) if n % 10 else ""))
    elif n > 0:
        out.append(_ONES[n])
    return " ".join(out)


def amount_in_words(value) -> str:
    v = Decimal(value).quantize(Decimal("0.01"))
    rupees, paise = int(v), int((v - int(v)) * 100)
    parts = []
    for div, name in ((10**7, "Crore"), (10**5, "Lakh"), (1000, "Thousand")):
        if rupees >= div:
            parts.append(_below_1000(rupees // div) + " " + name); rupees %= div
    if rupees or not parts:
        parts.append(_below_1000(rupees) if rupees else "Zero")
    text = "Rupees " + " ".join(parts)
    if paise:
        text += " and " + _below_1000(paise) + " Paise"
    return text + " Only"


def _inr(v) -> str:
    return "Rs. " + f"{Decimal(v):,.2f}"


def _d(v) -> str:
    if isinstance(v, (datetime, date)):
        return v.strftime("%d-%m-%Y")
    return str(v or "")


def build_receipt(*, lang: str, branch, customer_name: str, mobile: str, vehicle: str,
                  summary: dict, payment: dict) -> bytes:
    """summary = payments.service.summary(); payment = one entry of summary['payments']."""
    L = LABELS[lang]
    reg, bold = _fonts(lang)
    st = lambda **k: ParagraphStyle("s", fontName=k.pop("font", reg), fontSize=k.pop("size", 10),
                                    leading=k.pop("leading", 14), **k)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=14 * mm, bottomMargin=14 * mm,
                            title=f"Receipt {payment['receipt_no']}")
    P = lambda text, **k: Paragraph(str(text), st(**k))

    s = [P("S.K AUTOMOBILES", font="Times-Bold", size=20, leading=24, alignment=TA_CENTER, textColor=NAVY),
         P(((branch.name if branch else "") or "").upper(), font=bold, size=13, leading=17, alignment=TA_CENTER)]
    addr = ", ".join(x for x in [getattr(branch, "address", None), getattr(branch, "city", None)] if x)
    if addr:
        s.append(P(addr, size=9, alignment=TA_CENTER, textColor=colors.grey))
    if getattr(branch, "contact_no", None):
        s.append(P(f"{L['phone']}: {branch.contact_no}", size=9, alignment=TA_CENTER, textColor=colors.grey))
    s += [Spacer(1, 8), P(L["title"], font=bold, size=14, leading=18, alignment=TA_CENTER, textColor=ORANGE),
          Spacer(1, 8)]

    mode = payment["mode_label"] if lang == "en" else MODE_MR.get(payment["mode"], payment["mode_label"])
    ref = payment.get("reference")
    rows = [
        (L["receipt_no"], payment["receipt_no"]), (L["date"], _d(payment["payment_date"])),
        (L["booking_no"], summary["booking_no"]), (L["quotation_no"], summary["quotation_no"] or "-"),
        (L["received_from"], customer_name), (L["mobile"], mobile),
        (L["vehicle"], vehicle or "-"), (L["mode"], mode),
    ]
    if ref:
        rows.append((L["reference"], ref))
    if payment.get("finance_bank_name"):
        rows.append((L["bank"], payment["finance_bank_name"]))
    rows.append((L["amount"], _inr(payment["amount"])))
    if lang == "en":
        rows.append((L["in_words"], amount_in_words(payment["amount"])))
    if payment.get("remark"):
        rows.append((L["remark"], payment["remark"]))
    t = Table([[P(a, font=bold), P(b)] for a, b in rows], colWidths=[55 * mm, 119 * mm])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
                           ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f4f4f4")),
                           ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    s += [t, Spacer(1, 10)]

    # running position AS OF this receipt (later payments must not change an old receipt)
    paid_till = sum((Decimal(p["amount"]) for p in summary["payments"]
                     if p["receipt_seq"] <= payment["receipt_seq"]), Decimal("0"))
    total = summary["total_vehicle_cost"]
    bal = (Decimal(total) - paid_till) if total is not None else None
    status = ("PAID" if bal is not None and bal <= 0 else "PARTIALLY_PAID" if paid_till > 0 else "PENDING")
    pos = [(L["total"], _inr(total) if total is not None else "-"), (L["paid"], _inr(paid_till)),
           (L["outstanding"], _inr(bal) if bal is not None else "-"), (L["status"], L[status])]
    t2 = Table([[P(a, font=bold), P(b, font=bold)] for a, b in pos], colWidths=[85 * mm, 89 * mm])
    t2.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.8, NAVY), ("LINEBELOW", (0, 0), (-1, -2), 0.3, colors.lightgrey),
                            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f0eefa"))]))
    s += [t2, Spacer(1, 26)]
    sig = Table([[P(f"{L['by']}: {payment.get('recorded_by') or ''}", size=9),
                  P(L["sign"], size=9, alignment=TA_CENTER)]], colWidths=[100 * mm, 74 * mm])
    sig.setStyle(TableStyle([("LINEABOVE", (1, 0), (1, 0), 0.5, colors.black)]))
    s += [sig, Spacer(1, 14), P(L["note"], size=8, textColor=colors.grey, alignment=TA_CENTER)]
    doc.build(s)
    return buf.getvalue()
