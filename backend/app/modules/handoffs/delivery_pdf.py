"""Bike Delivery Receipt PDF (English). `data` comes from delivery.delivery_data()."""
import io
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

NAVY, ORANGE, GREY = colors.HexColor("#2b2560"), colors.HexColor("#f5820c"), colors.HexColor("#f4f4f4")
ACK_TEXT = ("I hereby confirm that I have received the vehicle along with the applicable documents and "
            "accessories. I acknowledge the payment details and vehicle information mentioned in this "
            "delivery receipt.")


def _inr(v):
    return "-" if v is None else "Rs. " + f"{Decimal(v):,.2f}"


def _d(v, fmt="%d-%m-%Y"):
    return v.strftime(fmt) if v else "-"


def build_delivery_pdf(data: dict, ack: dict | None = None) -> bytes:
    """ack = {"agreed_at": datetime, "ip": str} when the customer has accepted, else None."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm,
                            topMargin=9 * mm, bottomMargin=9 * mm, title=data["receipt_no"])
    P = lambda t, font="Helvetica", size=9, **k: Paragraph(
        str(t), ParagraphStyle("s", fontName=font, fontSize=size, leading=size + 3.5, **k))
    B = lambda t, **k: P(t, "Helvetica-Bold", **k)
    story = [P("S.K AUTOMOBILES", "Times-Bold", 19, alignment=TA_CENTER, textColor=NAVY),
             B(data["branch_name"].upper(), size=12, alignment=TA_CENTER)]
    if data.get("branch_address"):
        story.append(P(data["branch_address"], size=8.5, alignment=TA_CENTER, textColor=colors.grey))
    story += [Spacer(1, 4), B("BIKE DELIVERY RECEIPT", size=13, alignment=TA_CENTER, textColor=ORANGE), Spacer(1, 4)]

    def block(title, rows, widths=(48 * mm, 126 * mm)):
        t = Table([[B(a), P(b)] for a, b in rows], colWidths=list(widths))
        t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
                               ("BACKGROUND", (0, 0), (0, -1), GREY), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                               ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
        story.extend([B(title, size=10, textColor=NAVY), Spacer(1, 1), t, Spacer(1, 5)])

    block("CUSTOMER", [("Receipt no.", data["receipt_no"]), ("Delivery date", _d(data["delivery_date"])),
                       ("Customer name", data["customer_name"]), ("Mobile", data["mobile"]),
                       ("Enquiry no. / Booking no.", f'{data["enquiry_no"]} / {data["booking_no"]}')])
    block("VEHICLE", [("Model / colour", f'{data["model"] or "-"} / {data["color"] or "-"}'),
                      ("SKU code", data["sku_code"] or "-"), ("Chassis no.", data["chassis_no"]),
                      ("Engine no.", data["engine_no"]),
                      ("Invoice no. / date", f'{data["invoice_no"] or "-"} / {_d(data["invoice_date"])}'),
                      ("Registration no.", data["registration_no"] or "-"),
                      ("Number plate type", data["plate_type"] or "-"),
                      ("Delivery location", data["branch_name"])])
    acc = lambda ok: "[X]" if ok else "[ ]"
    block("ACCESSORIES &amp; WARRANTY PROVIDED",
          [("Accessories", f'{acc(data["acc_helmet"])} Studio Helmet &nbsp;&nbsp; {acc(data["acc_parking_cover"])} Parking Cover '
                           f'&nbsp;&nbsp; {acc(data["rsa_one_year"])} RSA 1 Year'),
           ("Engine warranty", data["warranty_text"])])
    block("INSURANCE &amp; DOCUMENTS",
          [("Insurance", data["insurance_text"]), ("Documents submitted", data["documents_text"])])

    rows = [[B("Date"), B("Receipt no."), B("Mode"), B("Reference / bank"), B("Amount")]]
    for p in data["payments"]:
        rows.append([P(_d(p["payment_date"])), P(p["receipt_no"]), P(p["mode_label"]),
                     P(" ".join(x for x in (p["reference"], p["finance_bank_name"]) if x) or "-"), P(_inr(p["amount"]))])
    pt = Table(rows, colWidths=[24 * mm, 42 * mm, 28 * mm, 46 * mm, 34 * mm])
    pt.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
                            ("BACKGROUND", (0, 0), (-1, 0), GREY)]))
    story += [KeepTogether([B("PAYMENT HISTORY", size=10, textColor=NAVY), Spacer(1, 1), pt]), Spacer(1, 5)]

    tot = [("Total vehicle cost (on-road price)", _inr(data["total_cost"])),
           ("Booking amount paid", _inr(data["booking_paid"])),
           ("Subsequent payments", _inr(data["subsequent_paid"])),
           ("&nbsp;&nbsp;&nbsp;of which finance amount", _inr(data["finance_paid"])),
           ("Total amount paid by customer", _inr(data["total_paid"])),
           ("Outstanding amount", _inr(data["outstanding"]))]
    if data.get("insurance_premium") is not None:
        tot.insert(1, ("&nbsp;&nbsp;&nbsp;Insurance premium (included in on-road price)", _inr(data["insurance_premium"])))
    tt = Table([[B(a), B(b)] for a, b in tot], colWidths=[110 * mm, 64 * mm])
    tt.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.8, NAVY), ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f0eefa")),
                            ("ALIGN", (1, 0), (1, -1), "RIGHT")]))
    story += [KeepTogether([B("TOTAL AMOUNT PAID", size=10, textColor=NAVY), Spacer(1, 1), tt]), Spacer(1, 7)]
    if data.get("exception_note"):
        story += [P(f'<font color="#b3261e"><b>Note:</b> {data["exception_note"]}</font>', size=8.5), Spacer(1, 6)]

    mark = "[X]" if ack else "[ ]"
    ack_rows = [[P(ACK_TEXT, size=9)], [B(f"{mark}  I AGREE", size=11)],
                [P(f'Customer: {data["customer_name"]} &nbsp;|&nbsp; Mobile: {data["mobile"]} &nbsp;|&nbsp; '
                   f'Registration no.: {data["registration_no"] or "-"} &nbsp;|&nbsp; Delivery date: {_d(data["delivery_date"])}', size=8.5)]]
    ack_rows.append([P(f'<font color="#1b6b34"><b>Digitally acknowledged by the customer on {_d(ack["agreed_at"], "%d-%m-%Y at %H:%M")}'
                       f'{" (IP " + ack["ip"] + ")" if ack.get("ip") else ""}.</b></font>', size=8.5)] if ack
                    else [P("Customer signature / digital acknowledgement: ____________________", size=8.5)])
    at = Table(ack_rows, colWidths=[174 * mm])
    at.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.8, ORANGE), ("TOPPADDING", (0, 0), (-1, -1), 4),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    story.append(KeepTogether([B("CUSTOMER ACKNOWLEDGEMENT", size=10, textColor=NAVY), Spacer(1, 2), at]))
    if data.get("review_url"):
        story += [Spacer(1, 8), P(f'Thank you for choosing KTM. Please share your experience: {data["review_url"]}', size=8.5,
                                  alignment=TA_CENTER, textColor=colors.grey)]
    doc.build(story)
    return buf.getvalue()
