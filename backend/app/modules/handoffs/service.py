"""Rules for the hand-offs. The router only calls these; every rule lives here."""
from datetime import date, timedelta

from fastapi import HTTPException

from app.core.database import now_ist
from app.modules.handoffs.models import (AtwApproval, InsuranceCase, InvoiceDetail, OwnerApproval,
                                         RtoCase)
from app.modules.leads.stages import change_stage
from app.modules.leads.lookup_names import lookup_key
from app.modules.leads.models import EnquiryStage, Lead
import re
from app.modules.notifications.models import NotificationType
from app.modules.notifications.service import create_notification
from app.modules.payments import service as pay_svc
from app.modules.users.models import AppUser, Role, UserBranch

POLICY_TYPES = {"MBO_ACKO": ("MBO Policy - ACKO", "ACKO"),
                "CUSTOMER_BAGIC": ("Customer Policy - BAGIC (Bajaj General)", "Bajaj General")}
NOMINEE_RELATIONS = ["Father", "Mother", "Spouse", "Son", "Daughter", "Brother", "Sister", "Other"]
REG_TYPES = {"REGULAR": "Regular No.", "CHOICE": "Choice No.", "BH_PASSING": "BH Passing No."}
RTO_STATUSES = {"PENDING": "Pending", "IN_PROCESS": "In process", "REGISTERED": "Registered"}
SPECIAL_ITEMS = {"PRICE": "Price", "CHOICE_NO": "Choice No. plate", "BH_PASSING_NO": "BH Passing No. plate",
                 "ACCESSORIES": "Accessories", "DELAYED_PAYMENT": "Delayed payment from customer",
                 "FULL_PAYMENT_ON_DELIVERY": "Full payment on delivery date",
                 "DELIVERY_DATE": "Final bike delivery date"}
ATW_LABELS = {"PENDING": "ATW Pending Owner Approval",
              "APPROVED": "ATW Approved – 10 Years Engine Warranty", "REJECTED": "ATW Rejected"}
BOOKING_DONE_KEY = lookup_key("BOOKING DONE")
REMINDER_DAYS = 5
WRITE_INSURANCE_ROLES = ("INSURANCE", "CRE", "ADMIN")
WRITE_RTO_ROLES = ("RTO", "ADMIN")


# ---------- who to notify ----------
def _ids(db, roles, branch_id=None):
    q = db.query(AppUser).filter(AppUser.role.in_(roles), AppUser.is_active.is_(True))
    if branch_id is not None and Role.CRE in roles and len(roles) == 1:
        q = q.join(UserBranch, UserBranch.user_id == AppUser.user_id).filter(UserBranch.branch_id == branch_id)
    return [u.user_id for u in q.all()]


def _notify(db, user_ids, type_, title, message, lead, actor_id):
    for uid in dict.fromkeys(user_ids):
        create_notification(db, user_id=uid, type_=type_, title=title, message=message,
                            reference_type="lead", reference_id=lead.lead_id, actor_user_id=actor_id)


def _who(lead: Lead) -> str:
    return f"{lead.customer.full_name} ({lead.enquiry_no})"


# ---------- insurance ----------
def is_booking_done(lead: Lead) -> bool:
    return bool(lead.opportunity and lookup_key(lead.opportunity.name) == BOOKING_DONE_KEY)


def ensure_insurance_case(db, lead: Lead, actor_id=None) -> InsuranceCase:
    """Called when a lead reaches BOOKING DONE: the insurance file starts straight away."""
    case = db.query(InsuranceCase).filter(InsuranceCase.lead_id == lead.lead_id).first()
    if case:
        return case
    case = InsuranceCase(lead_id=lead.lead_id, status="PENDING")
    db.add(case); db.flush()
    _notify(db, _ids(db, [Role.CRE], lead.branch_id), NotificationType.INSURANCE_STARTED,
            "New booking: insurance to be processed",
            f"{_who(lead)} is BOOKING DONE. Please start the insurance.", lead, actor_id)
    _notify(db, _ids(db, [Role.INSURANCE]), NotificationType.INSURANCE_STARTED,
            "New booking: insurance to be processed",
            f"{_who(lead)} is BOOKING DONE. Please start the insurance.", lead, actor_id)
    return case


def get_case(db, model, lead_id):
    return db.query(model).filter(model.lead_id == lead_id).first()


def check_nominee(c: InsuranceCase) -> list[str]:
    miss = []
    if not (c.nominee_name or "").strip(): miss.append("nominee name")
    if not c.nominee_age: miss.append("nominee age")
    if not c.nominee_relation: miss.append("nominee relation")
    elif c.nominee_relation == "Other" and not (c.nominee_relation_other or "").strip():
        miss.append("nominee relation (specify)")
    return miss


def complete_insurance(db, lead: Lead, c: InsuranceCase, *, policy_no, start, expiry, premium, saved, user):
    if c.status == "COMPLETED":
        raise HTTPException(400, "The insurance is already completed")
    if c.policy_type not in POLICY_TYPES:
        raise HTTPException(400, "Select the insurance policy type first")
    miss = check_nominee(c)
    if miss:
        raise HTTPException(400, "Enter the nominee details first: " + ", ".join(miss))
    from app.modules.insurance.service import missing_documents
    gap = missing_documents(db, lead, c)
    if gap:
        raise HTTPException(400, "Upload the required documents first: " + ", ".join(gap))
    policy_no = (policy_no or "").strip()
    if not policy_no:
        raise HTTPException(400, "Policy number is required")
    if expiry <= start:
        raise HTTPException(400, "The policy expiry date must be after the start date")
    if premium is not None and premium < 0:
        raise HTTPException(400, "Premium cannot be negative")
    dup = db.query(InsuranceCase).filter(InsuranceCase.policy_no.ilike(policy_no),
                                         InsuranceCase.id != c.id).first()
    if dup:
        raise HTTPException(400, "This policy number is already used on another booking")
    c.policy_no, c.policy_start, c.policy_expiry, c.premium = policy_no, start, expiry, premium
    c.pdf_original_name, c.pdf_stored_path, c.pdf_size_bytes = (saved["original_name"], saved["stored_path"],
                                                                saved["size_bytes"])
    c.status, c.completed_at, c.completed_by_user_id = "COMPLETED", now_ist(), user.user_id
    c.updated_by_user_id = user.user_id
    # the file now moves to the RTO
    if not get_case(db, RtoCase, lead.lead_id):
        db.add(RtoCase(lead_id=lead.lead_id, status="PENDING",
                       registration_type=_quoted_reg_type(db, lead)))
    company = POLICY_TYPES[c.policy_type][1]
    msg = (f"{_who(lead)}: {company} policy {policy_no} is ready (valid till {expiry:%d-%m-%Y}). "
           "The insurance PDF is on the lead page.")
    _notify(db, [lead.assigned_user_id], NotificationType.INSURANCE_DONE, "Insurance policy uploaded",
            msg, lead, user.user_id)
    db.flush()
    sync_stage(db, lead, user.user_id)
    _notify(db, _ids(db, [Role.RTO]), NotificationType.INSURANCE_DONE,
            "Insurance done: RTO to start", msg, lead, user.user_id)


def _quoted_reg_type(db, lead):
    q = pay_svc.latest_quotation(db, lead.lead_id)
    return q.hspr_registration_type.value if q and q.hspr_registration_type else None


# ---------- RTO ----------
def update_rto(db, lead: Lead, rto: RtoCase, data: dict, user):
    if "registration_type" in data and data["registration_type"] not in (None, *REG_TYPES):
        raise HTTPException(400, "Unknown registration type")
    if "status" in data and data["status"] not in RTO_STATUSES:
        raise HTTPException(400, "Unknown RTO status")
    before_no, before_dd = rto.registration_no, rto.delivery_date
    for k in ("status", "registration_type", "registration_no", "registration_date", "delivery_date"):
        if k in data:
            v = data[k]
            setattr(rto, k, (v.strip() or None) if isinstance(v, str) else v)
    if rto.status == "REGISTERED" and not rto.registration_no:
        raise HTTPException(400, "Enter the registration number to mark it Registered")
    if rto.registration_no and not rto.registration_date:
        rto.registration_date = date.today()
    rto.updated_by_user_id = user.user_id
    db.flush()
    sync_stage(db, lead, user.user_id)
    if rto.registration_no != before_no or rto.delivery_date != before_dd:
        bits = []
        if rto.registration_no: bits.append(f"registration no. {rto.registration_no}")
        if rto.delivery_date: bits.append(f"delivery date {rto.delivery_date:%d-%m-%Y}")
        _notify(db, [lead.assigned_user_id], NotificationType.RTO_UPDATE, "RTO update",
                f"{_who(lead)}: " + ", ".join(bits) + ".", lead, user.user_id)


# ---------- owner approval ----------
def request_approval(db, lead: Lead, items: list[str], note, delivery_date, user) -> OwnerApproval:
    booking = pay_svc.get_booking(db, lead.lead_id)
    if not booking or not booking.payments:
        raise HTTPException(400, "Record the booking payment before asking for approval")
    items = [i for i in dict.fromkeys(items or [])]
    bad = [i for i in items if i not in SPECIAL_ITEMS]
    if bad:
        raise HTTPException(400, "Unknown approval item: " + ", ".join(bad))
    if not delivery_date:
        raise HTTPException(400, "Enter the final bike delivery date")
    if delivery_date < date.today():
        raise HTTPException(400, "The delivery date cannot be in the past")
    appr = get_case(db, OwnerApproval, lead.lead_id)
    if appr and appr.status == "PENDING":
        raise HTTPException(400, "An approval request is already waiting for the Owner")
    if appr and appr.status == "APPROVED":
        raise HTTPException(400, "This deal is already approved")
    if not appr:
        appr = OwnerApproval(lead_id=lead.lead_id); db.add(appr)
    appr.status, appr.special_items, appr.note = "PENDING", ",".join(items) or None, (note or "").strip() or None
    appr.delivery_date, appr.requested_by_user_id, appr.requested_at = delivery_date, user.user_id, now_ist()
    appr.decided_by_user_id = appr.decided_at = appr.decision_note = None
    db.flush()
    _notify(db, _ids(db, [Role.OWNER]), NotificationType.APPROVAL_REQUESTED, "Approval needed",
            f"{_who(lead)}: approval requested by {user.full_name}.", lead, user.user_id)
    return appr


def decide(db, lead: Lead, row, approve: bool, note, user, type_, label: str):
    if row.status != "PENDING":
        raise HTTPException(400, "This request has already been decided")
    note = (note or "").strip() or None
    if not approve and not note:
        raise HTTPException(400, "Enter the reason for rejecting")
    row.status = "APPROVED" if approve else "REJECTED"
    row.decided_by_user_id, row.decided_at, row.decision_note = user.user_id, now_ist(), note
    _notify(db, [row.requested_by_user_id, lead.assigned_user_id], type_, f"{label} {row.status.lower()}",
            f"{_who(lead)}: {label} {row.status.lower()} by the Owner" + (f" — {note}" if note else "."),
            lead, user.user_id)


# ---------- ATW ----------
def request_atw(db, lead: Lead, user) -> AtwApproval:
    q = pay_svc.latest_quotation(db, lead.lead_id)
    if not q or q.engine_warranty_years != 10:
        raise HTTPException(400, "The quotation does not include the 10-year engine warranty")
    row = get_case(db, AtwApproval, lead.lead_id)
    if row and row.status in ("PENDING", "APPROVED"):
        raise HTTPException(400, "ATW is already " + ("approved" if row.status == "APPROVED" else "waiting for the Owner"))
    if not row:
        row = AtwApproval(lead_id=lead.lead_id); db.add(row)
    row.status, row.model_name = "PENDING", (q.model.name if q.model else None)
    inv = get_case(db, InvoiceDetail, lead.lead_id)
    row.chassis_no = inv.chassis_no if inv else None
    row.requested_by_user_id, row.requested_at = user.user_id, now_ist()
    row.decided_by_user_id = row.decided_at = row.decision_note = None
    db.flush()
    _notify(db, _ids(db, [Role.OWNER]), NotificationType.ATW_REQUESTED, "ATW approval needed",
            f"{_who(lead)}: 10-year engine warranty (ATW) requested by {user.full_name}.", lead, user.user_id)
    return row


# ---------- stage follows the milestones ----------
def sync_stage(db, lead: Lead, actor_id=None) -> None:
    """Move the lead forward as far as its milestones allow, one allowed step at a time:
    Booked -> Insurance Done (policy uploaded) -> RTO Done (registered) -> Invoiced (invoice saved).
    The client has not fixed the order of invoice / insurance / RTO, so each milestone is
    recorded whenever it happens and the stage simply catches up in the stage engine's order.
    To change the order, edit ALLOWED_NEXT in leads/stages.py and the list below."""
    ins, rto = get_case(db, InsuranceCase, lead.lead_id), get_case(db, RtoCase, lead.lead_id)
    inv = get_case(db, InvoiceDetail, lead.lead_id)
    done = {EnquiryStage.INSURANCE_DONE: bool(ins and ins.status == "COMPLETED"),
            EnquiryStage.RTO_DONE: bool(rto and rto.status == "REGISTERED"),
            EnquiryStage.INVOICED: bool(inv)}
    order = [EnquiryStage.BOOKED, EnquiryStage.INSURANCE_DONE, EnquiryStage.RTO_DONE, EnquiryStage.INVOICED]
    cur = lead.enquiry_stage
    if cur not in order:          # Open, Delivered or Closed: not moved by a milestone
        return
    while order.index(cur) + 1 < len(order) and done[order[order.index(cur) + 1]]:
        cur = order[order.index(cur) + 1]
        change_stage(db, lead, cur, actor_user_id=actor_id, reason="Milestone completed")


# ---------- invoice details ----------
_VIN = re.compile(r"^[A-Z0-9]{10,20}$")


def save_invoice(db, lead: Lead, d: dict, saved, user) -> InvoiceDetail:
    """d: invoice_no, invoice_date, chassis_no, engine_no, registration_type, hypothecation,
    nominee_name, nominee_relation, insurance_addon, delivery_date.  saved: uploaded file info or None."""
    booking = pay_svc.get_booking(db, lead.lead_id)
    if not booking or not booking.payments:
        raise HTTPException(400, "Record the booking payment before adding the invoice")
    if lead.enquiry_stage in (EnquiryStage.DELIVERED, EnquiryStage.CLOSED):
        raise HTTPException(400, "The invoice can't be changed after delivery or closing")
    row = get_case(db, InvoiceDetail, lead.lead_id)
    chassis = (d.get("chassis_no") or "").strip().upper().replace(" ", "")
    engine = (d.get("engine_no") or "").strip().upper().replace(" ", "")
    if not chassis or not engine:
        raise HTTPException(400, "Chassis number and engine number are mandatory")
    if not _VIN.match(chassis):
        raise HTTPException(400, "The chassis number must be 10-20 letters/digits")
    if not re.match(r"^[A-Z0-9*\-/]{5,25}$", engine):
        raise HTTPException(400, "The engine number looks wrong (5-25 letters/digits)")
    for col, val, label in ((InvoiceDetail.chassis_no, chassis, "chassis"), (InvoiceDetail.engine_no, engine, "engine")):
        q = db.query(InvoiceDetail).filter(col == val)
        if row:
            q = q.filter(InvoiceDetail.id != row.id)
        if q.first():
            raise HTTPException(400, f"This {label} number is already on another customer's invoice")
    if not row and not saved:
        raise HTTPException(400, "Upload the invoice copy")
    if d.get("registration_type") not in (None, "", *REG_TYPES):
        raise HTTPException(400, "Unknown registration type")
    if d.get("invoice_date") and d["invoice_date"] > date.today():
        raise HTTPException(400, "The invoice date cannot be in the future")
    if d.get("delivery_date") and d["delivery_date"] < date.today() and not (row and row.delivery_date == d["delivery_date"]):
        raise HTTPException(400, "The delivery date cannot be in the past")
    if d.get("nominee_relation") not in (None, "", *NOMINEE_RELATIONS):
        raise HTTPException(400, "Unknown nominee relation")

    first = row is None
    if first:
        row = InvoiceDetail(lead_id=lead.lead_id, chassis_no=chassis, engine_no=engine,
                            created_by_user_id=user.user_id)
        db.add(row)
    row.chassis_no, row.engine_no = chassis, engine
    for k in ("invoice_no", "registration_type", "hypothecation", "nominee_name", "nominee_relation", "insurance_addon"):
        v = d.get(k)
        setattr(row, k, (v.strip() or None) if isinstance(v, str) else v)
    row.invoice_date, row.delivery_date = d.get("invoice_date"), d.get("delivery_date")
    if saved:
        row.file_original_name, row.file_stored_path = saved["original_name"], saved["stored_path"]
        row.file_content_type, row.file_size_bytes = saved["content_type"], saved["size_bytes"]
    db.flush()
    _push_invoice_details(db, lead, row)
    sync_stage(db, lead, user.user_id)
    return row


def _push_invoice_details(db, lead: Lead, inv: InvoiceDetail) -> None:
    """Carry the invoice details to the other desks so nobody types them twice."""
    atw = get_case(db, AtwApproval, lead.lead_id)
    if atw:
        atw.chassis_no = inv.chassis_no                      # ATW is tied to the chassis number
    ins = get_case(db, InsuranceCase, lead.lead_id)
    if ins and ins.status != "COMPLETED":                    # prefill only what is still empty
        if inv.hypothecation and not ins.hypothecation:
            ins.hypothecation = inv.hypothecation
        if inv.nominee_name and not ins.nominee_name:
            ins.nominee_name = inv.nominee_name
            if inv.nominee_relation and not ins.nominee_relation:
                ins.nominee_relation = inv.nominee_relation
    rto = get_case(db, RtoCase, lead.lead_id)
    if rto:
        if inv.registration_type:
            rto.registration_type = inv.registration_type
        if inv.delivery_date and not rto.delivery_date:
            rto.delivery_date = inv.delivery_date


# ---------- the panel shown on the lead page ----------
def _d(v): return v.isoformat() if v else None


def panel(db, lead: Lead) -> dict:
    ins, rto = get_case(db, InsuranceCase, lead.lead_id), get_case(db, RtoCase, lead.lead_id)
    appr, atw = get_case(db, OwnerApproval, lead.lead_id), get_case(db, AtwApproval, lead.lead_id)
    q = pay_svc.latest_quotation(db, lead.lead_id)
    booking = pay_svc.get_booking(db, lead.lead_id)
    inv = get_case(db, InvoiceDetail, lead.lead_id)
    return {
        "booking_no": booking.booking_no if booking else None,
        "insurance": None if not ins else {
            "status": ins.status, "policy_type": ins.policy_type,
            "policy_type_label": POLICY_TYPES.get(ins.policy_type, (None,))[0],
            "company": POLICY_TYPES.get(ins.policy_type, (None, None))[1],
            "nominee_name": ins.nominee_name, "nominee_age": ins.nominee_age,
            "nominee_relation": ins.nominee_relation, "nominee_relation_other": ins.nominee_relation_other,
            "hypothecation": ins.hypothecation, "policy_no": ins.policy_no,
            "policy_start": _d(ins.policy_start), "policy_expiry": _d(ins.policy_expiry),
            "premium": ins.premium, "has_pdf": bool(ins.pdf_stored_path),
            "completed_at": ins.completed_at,
            "completed_by": ins.completed_by.full_name if ins.completed_by else None,
            "nominee_missing": check_nominee(ins)},
        "rto": None if not rto else {
            "status": rto.status, "status_label": RTO_STATUSES.get(rto.status),
            "registration_type": rto.registration_type,
            "registration_type_label": REG_TYPES.get(rto.registration_type),
            "registration_no": rto.registration_no, "registration_date": _d(rto.registration_date),
            "delivery_date": _d(rto.delivery_date)},
        "invoice": None if not inv else {
            "invoice_no": inv.invoice_no, "invoice_date": _d(inv.invoice_date), "chassis_no": inv.chassis_no,
            "engine_no": inv.engine_no, "registration_type": inv.registration_type,
            "hypothecation": inv.hypothecation, "nominee_name": inv.nominee_name,
            "nominee_relation": inv.nominee_relation, "insurance_addon": inv.insurance_addon,
            "delivery_date": _d(inv.delivery_date), "file_name": inv.file_original_name,
            "has_file": bool(inv.file_stored_path), "saved_at": inv.updated_at},
        "approval": None if not appr else {
            "status": appr.status, "items": [i for i in (appr.special_items or "").split(",") if i],
            "note": appr.note, "delivery_date": _d(appr.delivery_date),
            "requested_by": appr.requested_by.full_name if appr.requested_by else None,
            "requested_at": appr.requested_at,
            "decided_by": appr.decided_by.full_name if appr.decided_by else None,
            "decided_at": appr.decided_at, "decision_note": appr.decision_note},
        "atw": {"eligible": bool(q and q.engine_warranty_years == 10),
                "status": atw.status if atw else None,
                "label": ATW_LABELS.get(atw.status) if atw else None,
                "model_name": atw.model_name if atw else None, "chassis_no": atw.chassis_no if atw else None,
                "decided_at": atw.decided_at if atw else None,
                "decided_by": atw.decided_by.full_name if atw and atw.decided_by else None,
                "decision_note": atw.decision_note if atw else None},
        "options": {"policy_types": [{"value": k, "label": v[0]} for k, v in POLICY_TYPES.items()],
                    "nominee_relations": NOMINEE_RELATIONS,
                    "reg_types": [{"value": k, "label": v} for k, v in REG_TYPES.items()],
                    "rto_statuses": [{"value": k, "label": v} for k, v in RTO_STATUSES.items()],
                    "special_items": [{"value": k, "label": v} for k, v in SPECIAL_ITEMS.items()]},
    }


# ---------- 5-day delivery pop-up ----------
def delivery_reminders(db, leads_query) -> list[dict]:
    """Approved deals whose delivery date is within the next 5 days (today included)."""
    today = date.today()
    rows = (leads_query.join(OwnerApproval, OwnerApproval.lead_id == Lead.lead_id)
            .filter(OwnerApproval.status == "APPROVED",
                    OwnerApproval.delivery_date >= today,
                    OwnerApproval.delivery_date <= today + timedelta(days=REMINDER_DAYS),
                    Lead.enquiry_stage.notin_([EnquiryStage.DELIVERED, EnquiryStage.CLOSED]))
            .add_columns(OwnerApproval.delivery_date).order_by(OwnerApproval.delivery_date).all())
    return [{"lead_id": l.lead_id, "enquiry_no": l.enquiry_no, "customer_name": l.customer.full_name,
             "delivery_date": dd.isoformat(), "days_left": (dd - today).days} for l, dd in rows]
