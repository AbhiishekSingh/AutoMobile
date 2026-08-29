"""Generates the 3-page S.K Automobiles quotation PDF."""
import io
import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                Paragraph, Spacer, Image, PageBreak,
                                HRFlowable)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from app.modules.quotations.models import Quotation

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static")
LOGO_PATH = os.path.join(STATIC_DIR, "logo_placeholder.png")
KTM_BADGE_PATH = os.path.join(STATIC_DIR, "ktm_placeholder.png")

NAVY = colors.HexColor("#2b2560")
ORANGE = colors.HexColor("#f5820c")
GREEN = colors.HexColor("#2e9e4f")
LIGHT_GREY = colors.HexColor("#e9e9e9")
BORDER_ORANGE = colors.HexColor("#f0c48a")

styles = getSampleStyleSheet()
brand_style = ParagraphStyle("brand", parent=styles["Normal"], fontName="Times-Bold",
                             fontSize=20, textColor=NAVY, alignment=TA_CENTER)
branch_style = ParagraphStyle("branch", parent=styles["Normal"], fontName="Helvetica-Bold",
                              fontSize=14, alignment=TA_CENTER)
title_style = ParagraphStyle("title", parent=styles["Normal"], fontName="Helvetica-Bold",
                             fontSize=13, textColor=ORANGE, alignment=TA_CENTER)
label_bold = ParagraphStyle("label_bold", parent=styles["Normal"], fontName="Helvetica-Bold",
                            fontSize=10)
normal = ParagraphStyle("normal", parent=styles["Normal"], fontName="Helvetica", fontSize=10)
small_grey = ParagraphStyle("small_grey", parent=styles["Normal"], fontName="Helvetica",
                            fontSize=8, textColor=colors.grey)
section_header = ParagraphStyle("section_header", parent=styles["Normal"],
                                fontName="Times-Bold", fontSize=13, alignment=TA_CENTER)


def _header_block(branch_name: str):
    logo = Image(LOGO_PATH, width=28 * mm, height=28 * mm) if os.path.exists(LOGO_PATH) else Spacer(1, 1)
    badge = Image(KTM_BADGE_PATH, width=28 * mm, height=20 * mm) if os.path.exists(KTM_BADGE_PATH) else Spacer(1, 1)
    center = [
        Paragraph("S.K AUTOMOBILES", brand_style),
        Spacer(1, 6),
        Paragraph(branch_name.upper(), branch_style),
    ]
    tbl = Table([[logo, center, badge]], colWidths=[35 * mm, 110 * mm, 35 * mm])
    tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, 0), "LEFT"),
        ("ALIGN", (2, 0), (2, 0), "RIGHT"),
    ]))
    return tbl


def _kv(label: str, value: str, note: str = None):
    """One label/value pair styled like the PDF (bold label, normal value)."""
    txt = f"<b>{label}</b> {value or '-'}"
    p = [Paragraph(txt, normal)]
    if note:
        p.append(Paragraph(note, small_grey))
    return p


def build_quotation_pdf(quotation: Quotation, branch_name: str, branch_address: str,
                        branch_contact: str = None) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=15 * mm, bottomMargin=28 * mm,
                            leftMargin=15 * mm, rightMargin=15 * mm)
    story = []

    def draw_footer(canvas, doc_):
        """Draws the footer directly onto the page canvas so it always sits
        at a fixed position at the bottom of every page, regardless of how
        much content is above it."""
        canvas.saveState()
        page_width = A4[0]
        y = 20 * mm
        canvas.setStrokeColor(NAVY)
        canvas.setLineWidth(1)
        canvas.line(15 * mm, y + 14, page_width - 15 * mm, y + 14)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.setFillColor(colors.black)
        canvas.drawCentredString(page_width / 2, y + 4, f"S.K AUTOMOBILES - {branch_name.upper()}")
        canvas.setFont("Helvetica", 8.5)
        canvas.drawCentredString(page_width / 2, y - 6, f"Address: {branch_address}")
        if branch_contact and canvas.getPageNumber() == 3:
            canvas.drawCentredString(page_width / 2, y - 16, f"CONTACT NO.: {branch_contact}")
        canvas.restoreState()

    # ---------------- PAGE 1 ----------------
    story.append(_header_block(branch_name))
    story.append(Spacer(1, 4))
    story.append(Paragraph("OFFICIAL VEHICLE QUOTATION", title_style))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", color=colors.black, thickness=1))
    story.append(Spacer(1, 8))

    top_row = Table([[
        Paragraph(f"<b>Customer ID:</b> {quotation.customer_id}", label_bold),
        Paragraph(f"<b>Date:</b> {quotation.created_at.strftime('%d/%m/%Y')}", label_bold),
    ]], colWidths=[90 * mm, 90 * mm])
    story.append(top_row)
    story.append(Spacer(1, 8))

    story.append(Table([[
        _kv("CUSTOMER NAME :", quotation.customer_name.upper(), "(as per Aadhar)"),
    ]], colWidths=[180 * mm]))
    story.append(Spacer(1, 4))

    contact_row = Table([[
        _kv("CONTACT NO. :", quotation.contact_no, "(Linked to Aadhar)"),
        _kv("Email Id. :", quotation.email or "-", "(Active)"),
    ]], colWidths=[90 * mm, 90 * mm])
    story.append(contact_row)
    story.append(Spacer(1, 10))

    section = Table([[Paragraph("VEHICLE DETAILS", section_header)]], colWidths=[180 * mm])
    section.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), LIGHT_GREY),
                                 ("TOPPADDING", (0, 0), (-1, -1), 6),
                                 ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    story.append(section)
    story.append(Spacer(1, 8))

    model_row = Table([[
        Paragraph(f"<b>VEHICLE MODEL :</b> {quotation.model.name if quotation.model else '-'}", normal),
        Paragraph(f"<b>VEHICLE COLOR :</b> {quotation.color or '-'}", normal),
    ]], colWidths=[110 * mm, 70 * mm])
    story.append(model_row)
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"<b>ON ROAD PRICE :</b> Rs. {quotation.on_road_price:,.0f}", normal))
    story.append(Spacer(1, 8))

    reg_labels = {"REGULAR": "REGULAR NO.", "CHOICE": "CHOICE NO.", "BH_PASSING": "BH PASSING NO."}
    reg_lines = []
    for key, label in reg_labels.items():
        mark = "☑" if quotation.hspr_registration_type.value == key else "☐"
        reg_lines.append(Paragraph(f"{mark} {label}", normal))
    reg_table = Table([[Paragraph("<b>HSPR REGISTRATION TYPE :</b>", normal), reg_lines]],
                      colWidths=[60 * mm, 120 * mm])
    story.append(reg_table)
    story.append(Spacer(1, 10))

    inc_rows = []
    for inc in quotation.inclusions:
        status = "INCLUDED" if inc.included else "NOT INCLUDED"
        status_hex = "#2e9e4f" if inc.included else "#d92626"
        inc_rows.append([Paragraph(inc.description, normal),
                         Paragraph(f'<font color="{status_hex}"><b>{status}</b></font>', normal)])
    inc_table = Table(inc_rows, colWidths=[130 * mm, 50 * mm])
    inc_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.75, BORDER_ORANGE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(inc_table)

    # ---------------- PAGE 2 ----------------
    story.append(PageBreak())
    story.append(_header_block(branch_name))
    story.append(Spacer(1, 10))
    section2 = Table([[Paragraph("FINANCE / EMI SCHEME OPTIONS", section_header)]], colWidths=[180 * mm])
    section2.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), LIGHT_GREY),
                                  ("TOPPADDING", (0, 0), (-1, -1), 6),
                                  ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    story.append(section2)
    story.append(Spacer(1, 10))
    story.append(Paragraph(f"<b>BANK NAME :</b> {quotation.finance_bank_name or '-'}", normal))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"<b>FINANCER NAME :</b> {quotation.finance_financer_name or '-'}", normal))
    story.append(Spacer(1, 10))

    emi_header = ["TENURE (Months)", "DOWN PAYMENT", "MONTHLY EMI", "ROI %"]
    emi_data = [emi_header]
    for row in quotation.emi_options:
        emi_data.append([
            f"{row.tenure_months} Months",
            f"{row.down_payment:,.0f}" if row.down_payment else "",
            f"{row.monthly_emi:,.0f}" if row.monthly_emi else "",
            f"{row.roi_percent}" if row.roi_percent else "",
        ])
    emi_table = Table(emi_data, colWidths=[45 * mm, 45 * mm, 45 * mm, 45 * mm])
    emi_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#fbe4c4")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.75, BORDER_ORANGE),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(emi_table)
    story.append(Spacer(1, 14))

    docs = quotation.documents
    mid = (len(docs) + 1) // 2
    left_docs, right_docs = docs[:mid], docs[mid:]
    doc_rows = []
    for i in range(max(len(left_docs), len(right_docs))):
        l = f"☐ {left_docs[i].document_name}" if i < len(left_docs) else ""
        r = f"☐ {right_docs[i].document_name}" if i < len(right_docs) else ""
        doc_rows.append([Paragraph(l, normal), Paragraph(r, normal)])
    doc_box = Table(doc_rows, colWidths=[90 * mm, 90 * mm])
    doc_wrapper = Table([[Paragraph("<b>DOCUMENTS REQUIRED</b>", ParagraphStyle(
        "docs_head", parent=label_bold, textColor=ORANGE, fontSize=11))],
        [doc_box]], colWidths=[180 * mm])
    doc_wrapper.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_GREY),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(doc_wrapper)

    # ---------------- PAGE 3 ----------------
    story.append(PageBreak())
    story.append(_header_block(branch_name))
    story.append(Spacer(1, 14))

    note_body = (
        "<b>1. Price Validity:</b> The prices listed in this quotation are valid for 15 days "
        "from the date of issuance.<br/><br/>"
        "<b>2. Prevailing Price Clause:</b> The final On-Road price applicable will be the price "
        "prevailing on the actual date of vehicle invoicing and delivery, as per KTM India "
        "guidelines and statutory updates.<br/><br/>"
        "<b>3. Statutory Fees:</b> RTO road tax, registration charges, and insurance premiums are "
        "subject to government policy updates or tariff revisions at the time of registration."
    )
    note_table = Table([[Paragraph("<b>IMPORTANT CUSTOMER NOTE REGARDING PRICE REVISION</b><br/><br/>" + note_body, normal)]],
                       colWidths=[180 * mm])
    note_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fbe0bd")),
        ("BOX", (0, 0), (-1, -1), 2, ORANGE),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(note_table)
    story.append(Spacer(1, 14))

    tnc_body = (
        '<b>TERMS &amp; CONDITIONS:</b><br/><br/>'
        '• Payment mode: Cheque / Demand Draft / NEFT / RTGS in favor of "S. K. AUTOMOBILES".<br/>'
        '• Deliveries are subject to stock availability and clearance of full payment and documentation.<br/>'
        '• As per MoRTH mandates, BIS-certified helmets are mandatory and included with every vehicle purchase.'
    )
    tnc_table = Table([[Paragraph(tnc_body, normal)]], colWidths=[180 * mm])
    tnc_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1, colors.grey),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(tnc_table)
    story.append(Spacer(1, 40))

    sig_table = Table([
        ["_________________________", "_________________________"],
        ["SIGNATURE", "SIGNATURE"],
        [quotation.sales_manager_name or "-", "CUSTOMER"],
        ["(S.K AUTOMOBILES - SALES MANAGER)", f"({quotation.customer_name.upper()})"],
    ], colWidths=[90 * mm, 90 * mm])
    sig_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    story.append(sig_table)

    doc.build(story, onFirstPage=draw_footer, onLaterPages=draw_footer)
    return buf.getvalue()


# """Generates the 3-page S.K Automobiles quotation PDF."""
# import io
# import os

# from reportlab.lib import colors
# from reportlab.lib.pagesizes import A4
# from reportlab.lib.units import mm
# from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
#                                 Paragraph, Spacer, Image, PageBreak,
#                                 HRFlowable)
# from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
# from reportlab.lib.enums import TA_CENTER, TA_LEFT

# from app.modules.quotations.models import Quotation

# STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static")
# LOGO_PATH = os.path.join(STATIC_DIR, "logo_placeholder.png")
# KTM_BADGE_PATH = os.path.join(STATIC_DIR, "ktm_placeholder.png")

# NAVY = colors.HexColor("#2b2560")
# ORANGE = colors.HexColor("#f5820c")
# GREEN = colors.HexColor("#2e9e4f")
# LIGHT_GREY = colors.HexColor("#e9e9e9")
# BORDER_ORANGE = colors.HexColor("#f0c48a")

# styles = getSampleStyleSheet()
# brand_style = ParagraphStyle("brand", parent=styles["Normal"], fontName="Times-Bold",
#                              fontSize=20, textColor=NAVY, alignment=TA_CENTER)
# branch_style = ParagraphStyle("branch", parent=styles["Normal"], fontName="Helvetica-Bold",
#                               fontSize=14, alignment=TA_CENTER)
# title_style = ParagraphStyle("title", parent=styles["Normal"], fontName="Helvetica-Bold",
#                              fontSize=13, textColor=ORANGE, alignment=TA_CENTER)
# label_bold = ParagraphStyle("label_bold", parent=styles["Normal"], fontName="Helvetica-Bold",
#                             fontSize=10)
# normal = ParagraphStyle("normal", parent=styles["Normal"], fontName="Helvetica", fontSize=10)
# small_grey = ParagraphStyle("small_grey", parent=styles["Normal"], fontName="Helvetica",
#                             fontSize=8, textColor=colors.grey)
# section_header = ParagraphStyle("section_header", parent=styles["Normal"],
#                                 fontName="Times-Bold", fontSize=13, alignment=TA_CENTER)
# footer_style = ParagraphStyle("footer", parent=styles["Normal"], fontName="Helvetica-Bold",
#                               fontSize=9, alignment=TA_CENTER)
# footer_addr_style = ParagraphStyle("footer_addr", parent=styles["Normal"], fontName="Helvetica",
#                                    fontSize=8.5, alignment=TA_CENTER)


# def _header_block(branch_name: str):
#     logo = Image(LOGO_PATH, width=28 * mm, height=28 * mm) if os.path.exists(LOGO_PATH) else Spacer(1, 1)
#     badge = Image(KTM_BADGE_PATH, width=28 * mm, height=20 * mm) if os.path.exists(KTM_BADGE_PATH) else Spacer(1, 1)
#     center = [
#         Paragraph("S.K AUTOMOBILES", brand_style),
#         Spacer(1, 6),
#         Paragraph(branch_name.upper(), branch_style),
#     ]
#     tbl = Table([[logo, center, badge]], colWidths=[35 * mm, 110 * mm, 35 * mm])
#     tbl.setStyle(TableStyle([
#         ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
#         ("ALIGN", (0, 0), (0, 0), "LEFT"),
#         ("ALIGN", (2, 0), (2, 0), "RIGHT"),
#     ]))
#     return tbl


# def _footer_block(branch_name: str, address: str, contact: str = None):
#     elems = [
#         HRFlowable(width="100%", color=NAVY, thickness=1),
#         Spacer(1, 4),
#         Paragraph(f"S.K AUTOMOBILES - {branch_name.upper()}", footer_style),
#         Paragraph(f"<b>Address:</b> {address}", footer_addr_style),
#     ]
#     if contact:
#         elems.append(Paragraph(f"<b>CONTACT NO.:</b> {contact}", footer_addr_style))
#     return elems


# def _kv(label: str, value: str, note: str = None):
#     """One label/value pair styled like the PDF (bold label, normal value)."""
#     txt = f"<b>{label}</b> {value or '-'}"
#     p = [Paragraph(txt, normal)]
#     if note:
#         p.append(Paragraph(note, small_grey))
#     return p


# def build_quotation_pdf(quotation: Quotation, branch_name: str, branch_address: str,
#                         branch_contact: str = None) -> bytes:
#     buf = io.BytesIO()
#     doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=15 * mm, bottomMargin=15 * mm,
#                             leftMargin=15 * mm, rightMargin=15 * mm)
#     story = []

#     # ---------------- PAGE 1 ----------------
#     story.append(_header_block(branch_name))
#     story.append(Spacer(1, 4))
#     story.append(Paragraph("OFFICIAL VEHICLE QUOTATION", title_style))
#     story.append(Spacer(1, 8))
#     story.append(HRFlowable(width="100%", color=colors.black, thickness=1))
#     story.append(Spacer(1, 8))

#     top_row = Table([[
#         Paragraph(f"<b>Customer ID:</b> {quotation.customer_id}", label_bold),
#         Paragraph(f"<b>Date:</b> {quotation.created_at.strftime('%d/%m/%Y')}", label_bold),
#     ]], colWidths=[90 * mm, 90 * mm])
#     story.append(top_row)
#     story.append(Spacer(1, 8))

#     story.append(Table([[
#         _kv("CUSTOMER NAME :", quotation.customer_name.upper(), "(as per Aadhar)"),
#     ]], colWidths=[180 * mm]))
#     story.append(Spacer(1, 4))

#     contact_row = Table([[
#         _kv("CONTACT NO. :", quotation.contact_no, "(Linked to Aadhar)"),
#         _kv("Email Id. :", quotation.email or "-", "(Active)"),
#     ]], colWidths=[90 * mm, 90 * mm])
#     story.append(contact_row)
#     story.append(Spacer(1, 10))

#     section = Table([[Paragraph("VEHICLE DETAILS", section_header)]], colWidths=[180 * mm])
#     section.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), LIGHT_GREY),
#                                  ("TOPPADDING", (0, 0), (-1, -1), 6),
#                                  ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
#     story.append(section)
#     story.append(Spacer(1, 8))

#     model_row = Table([[
#         Paragraph(f"<b>VEHICLE MODEL :</b> {quotation.model.name if quotation.model else '-'}", normal),
#         Paragraph(f"<b>VEHICLE COLOR :</b> {quotation.color or '-'}", normal),
#     ]], colWidths=[110 * mm, 70 * mm])
#     story.append(model_row)
#     story.append(Spacer(1, 4))
#     story.append(Paragraph(f"<b>ON ROAD PRICE :</b> Rs. {quotation.on_road_price:,.0f}", normal))
#     story.append(Spacer(1, 8))

#     reg_labels = {"REGULAR": "REGULAR NO.", "CHOICE": "CHOICE NO.", "BH_PASSING": "BH PASSING NO."}
#     reg_lines = []
#     for key, label in reg_labels.items():
#         mark = "☑" if quotation.hspr_registration_type.value == key else "☐"
#         reg_lines.append(Paragraph(f"{mark} {label}", normal))
#     reg_table = Table([[Paragraph("<b>HSPR REGISTRATION TYPE :</b>", normal), reg_lines]],
#                       colWidths=[60 * mm, 120 * mm])
#     story.append(reg_table)
#     story.append(Spacer(1, 10))

#     inc_rows = []
#     for inc in quotation.inclusions:
#         status = "INCLUDED" if inc.included else "NOT INCLUDED"
#         status_color = GREEN if inc.included else colors.red
#         inc_rows.append([Paragraph(inc.description, normal),
#                          Paragraph(f'<font color="{status_color.hexval() if hasattr(status_color, "hexval") else "#2e9e4f"}"><b>{status}</b></font>', normal)])
#     inc_table = Table(inc_rows, colWidths=[130 * mm, 50 * mm])
#     inc_table.setStyle(TableStyle([
#         ("GRID", (0, 0), (-1, -1), 0.75, BORDER_ORANGE),
#         ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
#         ("TOPPADDING", (0, 0), (-1, -1), 6),
#         ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
#     ]))
#     story.append(inc_table)
#     story.append(Spacer(1, 12))
#     story.extend(_footer_block(branch_name, branch_address))

#     # ---------------- PAGE 2 ----------------
#     story.append(PageBreak())
#     story.append(_header_block(branch_name))
#     story.append(Spacer(1, 10))
#     section2 = Table([[Paragraph("FINANCE / EMI SCHEME OPTIONS", section_header)]], colWidths=[180 * mm])
#     section2.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), LIGHT_GREY),
#                                   ("TOPPADDING", (0, 0), (-1, -1), 6),
#                                   ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
#     story.append(section2)
#     story.append(Spacer(1, 10))
#     story.append(Paragraph(f"<b>BANK NAME :</b> {quotation.finance_bank_name or '-'}", normal))
#     story.append(Spacer(1, 4))
#     story.append(Paragraph(f"<b>FINANCER NAME :</b> {quotation.finance_financer_name or '-'}", normal))
#     story.append(Spacer(1, 10))

#     emi_header = ["TENURE (Months)", "DOWN PAYMENT", "MONTHLY EMI", "ROI %"]
#     emi_data = [emi_header]
#     for row in quotation.emi_options:
#         emi_data.append([
#             f"{row.tenure_months} Months",
#             f"{row.down_payment:,.0f}" if row.down_payment else "",
#             f"{row.monthly_emi:,.0f}" if row.monthly_emi else "",
#             f"{row.roi_percent}" if row.roi_percent else "",
#         ])
#     emi_table = Table(emi_data, colWidths=[45 * mm, 45 * mm, 45 * mm, 45 * mm])
#     emi_table.setStyle(TableStyle([
#         ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#fbe4c4")),
#         ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
#         ("GRID", (0, 0), (-1, -1), 0.75, BORDER_ORANGE),
#         ("ALIGN", (0, 0), (-1, -1), "CENTER"),
#         ("TOPPADDING", (0, 0), (-1, -1), 6),
#         ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
#     ]))
#     story.append(emi_table)
#     story.append(Spacer(1, 14))

#     docs = quotation.documents
#     mid = (len(docs) + 1) // 2
#     left_docs, right_docs = docs[:mid], docs[mid:]
#     doc_rows = []
#     for i in range(max(len(left_docs), len(right_docs))):
#         l = f"☐ {left_docs[i].document_name}" if i < len(left_docs) else ""
#         r = f"☐ {right_docs[i].document_name}" if i < len(right_docs) else ""
#         doc_rows.append([Paragraph(l, normal), Paragraph(r, normal)])
#     doc_box = Table([[Paragraph("<b>DOCUMENTS REQUIRED</b>", label_bold)]] + doc_rows if False else doc_rows,
#                     colWidths=[90 * mm, 90 * mm])
#     doc_wrapper = Table([[Paragraph("<b>DOCUMENTS REQUIRED</b>", ParagraphStyle(
#         "docs_head", parent=label_bold, textColor=ORANGE, fontSize=11))],
#         [doc_box]], colWidths=[180 * mm])
#     doc_wrapper.setStyle(TableStyle([
#         ("BACKGROUND", (0, 0), (-1, -1), LIGHT_GREY),
#         ("TOPPADDING", (0, 0), (-1, -1), 6),
#         ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
#         ("LEFTPADDING", (0, 0), (-1, -1), 10),
#     ]))
#     story.append(doc_wrapper)
#     story.append(Spacer(1, 20))
#     story.extend(_footer_block(branch_name, branch_address))

#     # ---------------- PAGE 3 ----------------
#     story.append(PageBreak())
#     story.append(_header_block(branch_name))
#     story.append(Spacer(1, 14))

#     note_body = (
#         "<b>1. Price Validity:</b> The prices listed in this quotation are valid for 15 days "
#         "from the date of issuance.<br/><br/>"
#         "<b>2. Prevailing Price Clause:</b> The final On-Road price applicable will be the price "
#         "prevailing on the actual date of vehicle invoicing and delivery, as per KTM India "
#         "guidelines and statutory updates.<br/><br/>"
#         "<b>3. Statutory Fees:</b> RTO road tax, registration charges, and insurance premiums are "
#         "subject to government policy updates or tariff revisions at the time of registration."
#     )
#     note_table = Table([[Paragraph("<b>IMPORTANT CUSTOMER NOTE REGARDING PRICE REVISION</b><br/><br/>" + note_body, normal)]],
#                        colWidths=[180 * mm])
#     note_table.setStyle(TableStyle([
#         ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fbe0bd")),
#         ("BOX", (0, 0), (-1, -1), 2, ORANGE),
#         ("LEFTPADDING", (0, 0), (-1, -1), 10),
#         ("TOPPADDING", (0, 0), (-1, -1), 8),
#         ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
#     ]))
#     story.append(note_table)
#     story.append(Spacer(1, 14))

#     tnc_body = (
#         '<b>TERMS &amp; CONDITIONS:</b><br/><br/>'
#         '• Payment mode: Cheque / Demand Draft / NEFT / RTGS in favor of "S. K. AUTOMOBILES".<br/>'
#         '• Deliveries are subject to stock availability and clearance of full payment and documentation.<br/>'
#         '• As per MoRTH mandates, BIS-certified helmets are mandatory and included with every vehicle purchase.'
#     )
#     tnc_table = Table([[Paragraph(tnc_body, normal)]], colWidths=[180 * mm])
#     tnc_table.setStyle(TableStyle([
#         ("BOX", (0, 0), (-1, -1), 1, colors.grey),
#         ("LEFTPADDING", (0, 0), (-1, -1), 10),
#         ("TOPPADDING", (0, 0), (-1, -1), 8),
#         ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
#     ]))
#     story.append(tnc_table)
#     story.append(Spacer(1, 40))

#     sig_table = Table([
#         ["_________________________", "_________________________"],
#         ["SIGNATURE", "SIGNATURE"],
#         [quotation.sales_manager_name or "-", "CUSTOMER"],
#         ["(S.K AUTOMOBILES - SALES MANAGER)", f"({quotation.customer_name.upper()})"],
#     ], colWidths=[90 * mm, 90 * mm])
#     sig_table.setStyle(TableStyle([
#         ("ALIGN", (0, 0), (-1, -1), "CENTER"),
#         ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
#         ("FONTSIZE", (0, 0), (-1, -1), 9),
#     ]))
#     story.append(sig_table)
#     story.append(Spacer(1, 30))
#     story.extend(_footer_block(branch_name, branch_address, branch_contact))

#     doc.build(story)
#     return buf.getvalue()