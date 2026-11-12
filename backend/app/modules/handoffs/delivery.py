"""Delivery: blockers, Owner exception, receipt generation, customer acknowledgement."""
import json
import os
import secrets
import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException

from app.core.config import settings
from app.modules.whatsapp.links import get_link
from app.core.database import now_ist
from app.modules.documents import service as docs
from app.modules.documents.models import CustomerDocument
from app.modules.handoffs import service as hs
from app.modules.handoffs.delivery_pdf import build_delivery_pdf
from app.modules.handoffs.models import (AtwApproval, DeliveryRecord, InsuranceCase, InvoiceDetail,
                                         OwnerApproval, RtoCase)
from app.modules.leads.models import EnquiryStage
from app.modules.leads.stages import change_stage
from app.modules.notifications.models import NotificationType
from app.modules.payments import service as pay_svc
from app.modules.users.models import Role

ZERO = Decimal("0")


def _rec(db, lead_id):
    return db.query(DeliveryRecord).filter(DeliveryRecord.lead_id == lead_id).first()


def blockers(db, lead) -> dict:
    """{'hard': [...], 'soft': [...]}.  hard = work that must be done first (cannot be overridden);
    soft = Owner approval / full payment (the Owner may allow delivery anyway, with a reason)."""
    hard, soft = [], []
    if not hs.get_case(db, InvoiceDetail, lead.lead_id):
        hard.append("Invoice details (chassis / engine no.) are not entered")
    ins = hs.get_case(db, InsuranceCase, lead.lead_id)
    if not ins or ins.status != "COMPLETED":
        hard.append("Insurance is not completed")
    rto = hs.get_case(db, RtoCase, lead.lead_id)
    if not rto or rto.status != "REGISTERED":
        hard.append("RTO registration is not completed")
    appr = hs.get_case(db, OwnerApproval, lead.lead_id)
    if not appr or appr.status != "APPROVED":
        soft.append("Owner approval is pending" if appr and appr.status == "PENDING"
                    else "Owner approval has not been given")
    s = pay_svc.summary(db, lead)
    if s["outstanding"] is None or s["outstanding"] > 0:
        soft.append("Payment is not complete" + (f" (outstanding Rs. {s['outstanding']:,.2f})" if s["outstanding"] else ""))
    return {"hard": hard, "soft": soft}


def state(db, lead) -> dict:
    rec = _rec(db, lead.lead_id)
    b = blockers(db, lead)
    delivered = lead.enquiry_stage in (EnquiryStage.DELIVERED,) or bool(rec and rec.generated_at)
    overridden = bool(rec and rec.override_at)
    return {
        "delivered": delivered, "receipt_no": rec.receipt_no if rec else None,
        "delivery_date": rec.delivery_date.isoformat() if rec and rec.delivery_date else None,
        "generated_at": rec.generated_at if rec else None,
        "generated_by": rec.generated_by.full_name if rec and rec.generated_by else None,
        "blockers_hard": [] if delivered else b["hard"], "blockers_soft": [] if delivered else b["soft"],
        "override": None if not overridden else {"reason": rec.override_reason, "by": rec.override_by.full_name if rec.override_by else None,
                                                  "at": rec.override_at, "pending_then": (rec.override_blockers or "").split(" | ")},
        "can_generate": (not delivered) and not b["hard"] and (not b["soft"] or overridden),
        "can_override": (not delivered) and not b["hard"] and bool(b["soft"]) and not overridden,
        "has_link": bool(rec and rec.ack_token), "agreed_at": rec.agreed_at if rec else None,
        "has_accepted_pdf": bool(rec and rec.accepted_doc_id),
    }


def override(db, lead, reason, user) -> DeliveryRecord:
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise HTTPException(400, "Enter the reason for allowing the delivery")
    b = blockers(db, lead)
    if b["hard"]:
        raise HTTPException(400, "These must be completed first: " + "; ".join(b["hard"]))
    if not b["soft"]:
        raise HTTPException(400, "Nothing is pending, so no exception is needed")
    rec = _rec(db, lead.lead_id)
    if rec and rec.generated_at:
        raise HTTPException(400, "The bike is already delivered")
    if not rec:
        rec = DeliveryRecord(lead_id=lead.lead_id)
        db.add(rec)
    rec.override_reason, rec.override_by_user_id, rec.override_at = reason, user.user_id, now_ist()
    rec.override_blockers = " | ".join(b["soft"])
    db.flush()
    hs._notify(db, [lead.assigned_user_id], NotificationType.DELIVERY_OVERRIDE, "Delivery allowed by the Owner",
               f"{hs._who(lead)}: the Owner allowed delivery although: {rec.override_blockers}. Reason: {reason}", lead, user.user_id)
    return rec


def delivery_data(db, lead, rec) -> dict:
    s = pay_svc.summary(db, lead)
    inv = hs.get_case(db, InvoiceDetail, lead.lead_id)
    ins, rto = hs.get_case(db, InsuranceCase, lead.lead_id), hs.get_case(db, RtoCase, lead.lead_id)
    atw = hs.get_case(db, AtwApproval, lead.lead_id)
    q = pay_svc.latest_quotation(db, lead.lead_id)
    pays = s["payments"]
    first = pays[0]["amount"] if pays else ZERO
    rest = sum((p["amount"] for p in pays[1:]), ZERO)
    fin = sum((p["amount"] for p in pays if p["mode"] == "FINANCE"), ZERO)
    have = {d.doc_type for d in db.query(CustomerDocument).filter(CustomerDocument.lead_id == lead.lead_id).all()}
    req = [d for d in docs.DOC_TYPES if d["required"]]
    got = [d["label"] for d in req if d["value"] in have or d.get("either_with") in have]
    warranty = q.engine_warranty_years if q and q.engine_warranty_years else None
    w_text = "-" if not warranty else (f"{warranty} years" + (f" (ATW: {hs.ATW_LABELS[atw.status]})" if warranty == 10 and atw else ""))
    branch = lead.branch
    cust = lead.customer
    return {
        "receipt_no": rec.receipt_no, "delivery_date": rec.delivery_date, "branch_name": branch.name if branch else "",
        "branch_address": ", ".join(x for x in (getattr(branch, "address", None), getattr(branch, "contact_no", None)) if x),
        "customer_name": cust.full_name, "mobile": cust.phone, "enquiry_no": lead.enquiry_no, "booking_no": s["booking_no"],
        "model": lead.model.name if lead.model else None, "color": lead.color, "sku_code": lead.sku_code,
        "chassis_no": inv.chassis_no, "engine_no": inv.engine_no, "invoice_no": inv.invoice_no, "invoice_date": inv.invoice_date,
        "registration_no": rto.registration_no if rto else None,
        "plate_type": hs.REG_TYPES.get((rto.registration_type if rto else None) or inv.registration_type),
        "acc_helmet": bool(q and q.acc_helmet), "acc_parking_cover": bool(q and q.acc_parking_cover),
        "rsa_one_year": bool(q and q.rsa_one_year), "warranty_text": w_text,
        "insurance_text": (f'{hs.POLICY_TYPES[ins.policy_type][1]} policy {ins.policy_no}, valid {ins.policy_start:%d-%m-%Y} to {ins.policy_expiry:%d-%m-%Y}'
                           if ins and ins.status == "COMPLETED" else "-"),
        "documents_text": (f"{len(got)} of {len(req)} required KYC documents on file" + (f" ({', '.join(got)})" if got else "")),
        "payments": pays, "total_cost": s["total_vehicle_cost"], "booking_paid": first, "subsequent_paid": rest,
        "finance_paid": fin, "total_paid": s["total_paid"], "outstanding": s["outstanding"],
        "insurance_premium": ins.premium if ins and ins.status == "COMPLETED" else None,
        "exception_note": (f"Delivered with the Owner's approval of an exception: {rec.override_blockers}." if rec.override_at else None),
        "review_url": get_link(db, lead.branch_id, "GOOGLE_REVIEW_URL"),
    }


def make_pdf(db, lead, rec) -> bytes:
    ack = {"agreed_at": rec.agreed_at, "ip": rec.agreed_ip} if rec.agreed_at else None
    return build_delivery_pdf(delivery_data(db, lead, rec), ack)


def generate(db, lead, user) -> DeliveryRecord:
    """The bike is handed over: needs everything done (or the Owner's exception). Sets the
    delivery date to today, creates the receipt number and moves the lead to DELIVERED."""
    st = state(db, lead)
    if st["delivered"]:
        raise HTTPException(400, "The bike is already marked delivered")
    if st["blockers_hard"]:
        raise HTTPException(400, "Complete these first: " + "; ".join(st["blockers_hard"]))
    if st["blockers_soft"] and not st["override"]:
        raise HTTPException(400, "The delivery receipt can't be generated: " + "; ".join(st["blockers_soft"]) +
                            ". The Owner can allow an exception.")
    rec = _rec(db, lead.lead_id) or DeliveryRecord(lead_id=lead.lead_id)
    db.add(rec)
    booking = pay_svc.get_booking(db, lead.lead_id)
    rec.receipt_no = f"DR-{booking.booking_no}"
    rec.delivery_date, rec.generated_at, rec.generated_by_user_id = now_ist().date(), now_ist(), user.user_id
    db.flush()
    hs.sync_stage(db, lead, user.user_id)                      # make sure it has reached INVOICED
    change_stage(db, lead, EnquiryStage.DELIVERED, actor_user_id=user.user_id, reason="Delivery receipt generated")
    return rec


def link_token(db, lead) -> DeliveryRecord:
    rec = _rec(db, lead.lead_id)
    if not rec or not rec.generated_at:
        raise HTTPException(400, "Generate the delivery receipt first")
    if not rec.ack_token:
        rec.ack_token = secrets.token_urlsafe(32)
    return rec


def accept(db, lead, rec, ip, user_agent) -> None:
    """The customer pressed I AGREE: record it once, store the accepted PDF on the customer's profile."""
    if rec.agreed_at:
        return
    rec.agreed_at, rec.agreed_ip, rec.agreed_user_agent = now_ist(), ip, (user_agent or "")[:300]
    pdf = make_pdf(db, lead, rec)
    rel = os.path.join("customers", str(lead.customer_id), f"{uuid.uuid4().hex}.pdf")
    full = os.path.join(docs.upload_root(), rel)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "wb") as f:
        f.write(pdf)
    d = CustomerDocument(lead_id=lead.lead_id, customer_id=lead.customer_id, doc_type="OTHER",
                         note="Delivery receipt - accepted by customer", original_name=f"{rec.receipt_no}-accepted.pdf",
                         stored_path=rel, content_type="application/pdf", size_bytes=len(pdf))
    db.add(d); db.flush()
    rec.accepted_doc_id = d.id
    hs._notify(db, [lead.assigned_user_id] + hs._ids(db, [Role.OWNER, Role.GM]), NotificationType.DELIVERY_ACK,
               "Customer acknowledged delivery", f"{hs._who(lead)} pressed I AGREE on the delivery receipt.", lead, None)
