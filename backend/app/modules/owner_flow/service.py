"""Owner Portal workflow: Booking -> Initial Owner approval -> PBA payment + documents ->
Insurance -> Final Owner approval -> RTO -> Delivery Challan.  No department can skip a step:
each stage is only created by the one before it."""
from decimal import Decimal

from fastapi import HTTPException

from app.core.database import now_ist
from app.modules.documents import service as docs_svc
from app.modules.documents.models import CustomerDocument
from app.modules.handoffs import service as hs
from app.modules.handoffs.models import AtwApproval, InsuranceCase, InvoiceDetail, RtoCase
from app.modules.leads.models import EnquiryStage, Lead
from app.modules.notifications.models import NotificationType
from app.modules.owner_flow.models import OwnerStageApproval
from app.modules.payments import service as pay_svc
from app.modules.users.models import AppUser, Role

ZERO = Decimal("0")
STAGE_LABELS = {"INITIAL": "Initial Owner approval", "FINAL": "Final Owner approval"}


def get_stage(db, lead_id, stage) -> OwnerStageApproval | None:
    return (db.query(OwnerStageApproval)
            .filter(OwnerStageApproval.lead_id == lead_id, OwnerStageApproval.stage == stage).first())


# ---------- 1. booking -> initial approval ----------
def start_initial(db, lead: Lead, actor_id=None) -> OwnerStageApproval | None:
    """Called when the lead is BOOKING DONE. Returns the new row, or None if it already existed."""
    if get_stage(db, lead.lead_id, "INITIAL"):
        return None
    q = pay_svc.latest_quotation(db, lead.lead_id)
    row = OwnerStageApproval(lead_id=lead.lead_id, stage="INITIAL", status="PENDING",
                             quoted_price=q.on_road_price if q else None,
                             discounted_price=q.discounted_price if q else None)
    db.add(row); db.flush()
    hs._notify(db, hs._ids(db, [Role.OWNER]), NotificationType.APPROVAL_REQUESTED,
               "New booking: initial approval needed",
               f"{hs._who(lead)}: please approve the discounted price, customer processing and ATW.",
               lead, actor_id)
    return row


def decide_initial(db, lead: Lead, *, approve: bool, discounted_price, customer_processing, atw_allowed,
                   remark, user) -> OwnerStageApproval:
    row = get_stage(db, lead.lead_id, "INITIAL")
    if not row:
        raise HTTPException(404, "This booking has no initial approval request")
    if hs.get_case(db, InsuranceCase, lead.lead_id):
        raise HTTPException(400, "The file has already moved to Insurance, so the initial approval can't be changed")
    remark = (remark or "").strip() or None
    if approve:
        if discounted_price is None or Decimal(discounted_price) <= 0:
            raise HTTPException(400, "Enter the approved discounted price")
        if customer_processing is None:
            raise HTTPException(400, "Choose Customer Processing: YES or NO")
        if atw_allowed is None:
            raise HTTPException(400, "Choose ATW: YES or NO")
        row.discounted_price = Decimal(discounted_price)
        row.customer_processing, row.atw_allowed = bool(customer_processing), bool(atw_allowed)
        # keep the quotation's internal discounted price in step: the PBA reads it there
        q = pay_svc.latest_quotation(db, lead.lead_id)
        if q:
            q.discounted_price = row.discounted_price
    elif not remark:
        raise HTTPException(400, "Enter the reason for rejecting")
    row.status = "APPROVED" if approve else "REJECTED"
    row.decided_by_user_id, row.decided_at, row.remark = user.user_id, now_ist(), remark
    # ATW is recorded on its own record too, so the delivery receipt and ATW list stay correct
    if approve:
        _apply_atw(db, lead, row, user)
    db.flush()
    if approve:
        msg = (f"{hs._who(lead)}: approved at Rs. {row.discounted_price:,.2f} by {user.full_name}. "
               f"Customer processing: {'YES' if row.customer_processing else 'NO'}; ATW: {'YES' if row.atw_allowed else 'NO'}.")
    else:
        msg = f"{hs._who(lead)}: initial approval REJECTED by {user.full_name} — {remark}. Please inform the customer."
    hs._notify(db, [lead.assigned_user_id], NotificationType.APPROVAL_DECIDED,
               "Initial approval " + row.status.lower(), msg, lead, user.user_id)
    if approve:
        maybe_start_insurance(db, lead, user.user_id)
    return row


def _apply_atw(db, lead, row, user):
    q = pay_svc.latest_quotation(db, lead.lead_id)
    if not q or q.engine_warranty_years != 10:
        return                                   # nothing to decide for a 5-year quotation
    atw = hs.get_case(db, AtwApproval, lead.lead_id)
    if not atw:
        atw = AtwApproval(lead_id=lead.lead_id, requested_by_user_id=lead.assigned_user_id or user.user_id,
                          model_name=q.model.name if q.model else None)
        db.add(atw)
    atw.status = "APPROVED" if row.atw_allowed else "REJECTED"
    atw.decided_by_user_id, atw.decided_at = user.user_id, now_ist()
    atw.decision_note = "Decided with the initial approval"


def resubmit(db, lead: Lead, stage: str, user) -> OwnerStageApproval:
    row = get_stage(db, lead.lead_id, stage)
    if not row or row.status != "REJECTED":
        raise HTTPException(400, "Only a rejected request can be sent to the Owner again")
    if stage == "FINAL":
        ins = hs.get_case(db, InsuranceCase, lead.lead_id)
        if not ins or ins.status != "COMPLETED":
            raise HTTPException(400, "The insurance policy is not uploaded")
    row.status, row.round_no, row.requested_at = "PENDING", (row.round_no or 1) + 1, now_ist()
    row.decided_by_user_id = row.decided_at = row.remark = None
    if stage == "INITIAL":
        q = pay_svc.latest_quotation(db, lead.lead_id)
        row.quoted_price = q.on_road_price if q else row.quoted_price
    db.flush()
    hs._notify(db, hs._ids(db, [Role.OWNER]), NotificationType.APPROVAL_REQUESTED,
               f"{STAGE_LABELS[stage]} requested again",
               f"{hs._who(lead)}: sent again by {user.full_name}.", lead, user.user_id)
    return row


# ---------- 2. PBA: payment + documents -> Insurance ----------
def payment_state(db, lead: Lead) -> dict:
    """DP (finance deals) or full payment (cash deals) — the money the customer himself must pay."""
    s = pay_svc.summary(db, lead)
    q = pay_svc.latest_quotation(db, lead.lead_id)
    cost, paid, out = s["total_vehicle_cost"], s["total_paid"], s["outstanding"]
    own = sum((p["amount"] for p in s["payments"] if p["mode"] != "FINANCE"), ZERO)
    finance_in = sum((p["amount"] for p in s["payments"] if p["mode"] == "FINANCE"), ZERO)
    is_emi = bool(q and (q.payment_type or "CASH") == "EMI")
    need = q.down_payment if (is_emi and q and q.down_payment) else cost
    ok = bool(paid > 0 and ((out is not None and out <= 0) or (need is not None and own >= need)))
    kind = "DOWN_PAYMENT" if (is_emi and q and q.down_payment) else "FULL_PAYMENT"
    return {"ok": ok, "kind": kind, "required": need, "paid_by_customer": own, "finance_received": finance_in,
            "total_cost": cost, "total_paid": paid, "outstanding": out, "payment_status": s["payment_status"],
            "finance_bank": s["finance"]["finance_bank_name"], "is_emi": is_emi}


def documents_state(db, lead: Lead) -> dict:
    have = {d.doc_type: d for d in db.query(CustomerDocument).filter(CustomerDocument.lead_id == lead.lead_id)
            .order_by(CustomerDocument.uploaded_at.asc()).all()}
    items, missing = [], []
    for d in docs_svc.DOC_TYPES:
        if not d["required"]:
            continue
        got = docs_svc.doc_satisfied(d, have)
        if d.get("either_with") and d["value"] != d["either_with"] and not got:
            pass
        items.append({"label": d["label"], "uploaded": got})
        if not got:
            missing.append(d["label"])
    # "either of" pairs show twice; keep one missing message per pair
    missing = list(dict.fromkeys(missing))
    return {"ok": not missing, "missing": missing, "items": items}


def maybe_start_insurance(db, lead: Lead, actor_id=None) -> InsuranceCase | None:
    """Create the Insurance file ONLY when: initial approval done (customer processing YES),
    DP / full payment received and every required customer document uploaded."""
    if hs.get_case(db, InsuranceCase, lead.lead_id):
        return None
    ini = get_stage(db, lead.lead_id, "INITIAL")
    if not ini or ini.status != "APPROVED" or not ini.customer_processing:
        return None
    if not payment_state(db, lead)["ok"] or not documents_state(db, lead)["ok"]:
        return None
    case = InsuranceCase(lead_id=lead.lead_id, status="PENDING")
    db.add(case); db.flush()
    msg = f"{hs._who(lead)}: payment and documents are complete. Please process the insurance."
    hs._notify(db, hs._ids(db, [Role.CRE], lead.branch_id) + hs._ids(db, [Role.INSURANCE]),
               NotificationType.INSURANCE_STARTED, "Insurance to be processed", msg, lead, actor_id)
    hs._notify(db, [lead.assigned_user_id], NotificationType.INSURANCE_STARTED, "Moved to Insurance",
               f"{hs._who(lead)}: payment and documents complete — the file has moved to Insurance.", lead, actor_id)
    return case


# ---------- 3. Insurance -> final approval ----------
def request_final(db, lead: Lead, actor_id=None) -> OwnerStageApproval:
    """Called when the policy PDF is uploaded."""
    row = get_stage(db, lead.lead_id, "FINAL")
    if row:
        if row.status == "REJECTED":
            row.status, row.round_no, row.requested_at = "PENDING", (row.round_no or 1) + 1, now_ist()
            row.decided_by_user_id = row.decided_at = row.remark = None
        return row
    row = OwnerStageApproval(lead_id=lead.lead_id, stage="FINAL", status="PENDING")
    db.add(row); db.flush()
    hs._notify(db, hs._ids(db, [Role.OWNER]), NotificationType.APPROVAL_REQUESTED, "Final approval needed",
               f"{hs._who(lead)}: insurance policy uploaded. Please review and give the final approval.",
               lead, actor_id)
    return row


def decide_final(db, lead: Lead, *, approve: bool, remark, user) -> OwnerStageApproval:
    row = get_stage(db, lead.lead_id, "FINAL")
    if not row:
        raise HTTPException(404, "This file has not reached the final approval")
    if row.status != "PENDING":
        raise HTTPException(400, "The final approval has already been decided")
    remark = (remark or "").strip() or None
    if not approve and not remark:
        raise HTTPException(400, "Enter the reason for rejecting")
    row.status = "APPROVED" if approve else "REJECTED"
    row.decided_by_user_id, row.decided_at, row.remark = user.user_id, now_ist(), remark
    if approve:
        if not hs.get_case(db, RtoCase, lead.lead_id):
            db.add(RtoCase(lead_id=lead.lead_id, status="PENDING", registration_type=hs._quoted_reg_type(db, lead)))
        db.flush()
        msg = f"{hs._who(lead)}: final approval given by {user.full_name}. The file is now with the RTO."
        hs._notify(db, hs._ids(db, [Role.RTO]), NotificationType.INSURANCE_DONE, "Approved: RTO to start", msg, lead, user.user_id)
        hs._notify(db, [lead.assigned_user_id], NotificationType.APPROVAL_DECIDED,
                   "Final approval given — Delivery Challan enabled",
                   msg + " The Delivery Challan is now enabled.", lead, user.user_id)
        hs.sync_stage(db, lead, user.user_id)
    else:
        hs._notify(db, [lead.assigned_user_id], NotificationType.APPROVAL_DECIDED, "Final approval rejected",
                   f"{hs._who(lead)}: final approval REJECTED by {user.full_name} — {remark}. Please inform the customer.",
                   lead, user.user_id)
    db.flush()
    return row


# ---------- views ----------
def _person(u): return u.full_name if u else None


def stage_view(row) -> dict | None:
    if not row:
        return None
    return {"stage": row.stage, "status": row.status, "round": row.round_no, "requested_at": row.requested_at,
            "quoted_price": row.quoted_price, "discounted_price": row.discounted_price,
            "customer_processing": row.customer_processing, "atw_allowed": row.atw_allowed,
            "decided_by": _person(row.decided_by), "decided_at": row.decided_at, "remark": row.remark}


def workflow_status(db, lead: Lead) -> dict:
    """One current status for the lead + the status of every stage (real time: derived on read)."""
    ini, fin = get_stage(db, lead.lead_id, "INITIAL"), get_stage(db, lead.lead_id, "FINAL")
    ins, rto = hs.get_case(db, InsuranceCase, lead.lead_id), hs.get_case(db, RtoCase, lead.lead_id)
    pay, doc = payment_state(db, lead), documents_state(db, lead)
    if lead.enquiry_stage == EnquiryStage.DELIVERED:
        cur = "DELIVERED"
    elif rto:
        cur = "RTO_REGISTERED" if rto.status == "REGISTERED" else "AT_RTO"
    elif fin:
        cur = {"PENDING": "AWAITING_FINAL_APPROVAL", "REJECTED": "FINAL_REJECTED"}.get(fin.status, "AT_RTO")
    elif ins:
        cur = "AT_INSURANCE"
    elif not ini:
        cur = "NO_BOOKING"
    elif ini.status == "PENDING":
        cur = "AWAITING_INITIAL_APPROVAL"
    elif ini.status == "REJECTED":
        cur = "INITIAL_REJECTED"
    elif not ini.customer_processing:
        cur = "CUSTOMER_PROCESSING_NO"
    else:
        cur = "AWAITING_PBA"
    stages = {
        "initial": ini.status if ini else None,
        "payment": "DONE" if pay["ok"] else "PENDING",
        "documents": "DONE" if doc["ok"] else "PENDING",
        "insurance": ("COMPLETED" if ins and ins.status == "COMPLETED" else ins.status) if ins else None,
        "final": fin.status if fin else None,
        "rto": rto.status if rto else None,
        "challan": "ENABLED" if (fin and fin.status == "APPROVED") else "LOCKED",
    }
    return {"current": cur, "label": CURRENT_LABELS[cur], "stages": stages}


CURRENT_LABELS = {
    "NO_BOOKING": "Not booked", "AWAITING_INITIAL_APPROVAL": "Waiting for Owner (initial approval)",
    "INITIAL_REJECTED": "Initial approval rejected", "CUSTOMER_PROCESSING_NO": "Owner: customer processing NO",
    "AWAITING_PBA": "With PBA: payment / documents", "AT_INSURANCE": "With Insurance",
    "AWAITING_FINAL_APPROVAL": "Waiting for Owner (final approval)", "FINAL_REJECTED": "Final approval rejected",
    "AT_RTO": "With RTO", "RTO_REGISTERED": "RTO registered - ready for delivery", "DELIVERED": "Delivered"}


def detail(db, lead: Lead) -> dict:
    """Everything the Owner checks before the final approval (also shown to PBA and GM)."""
    ini, fin = get_stage(db, lead.lead_id, "INITIAL"), get_stage(db, lead.lead_id, "FINAL")
    ins, rto = hs.get_case(db, InsuranceCase, lead.lead_id), hs.get_case(db, RtoCase, lead.lead_id)
    atw = hs.get_case(db, AtwApproval, lead.lead_id)
    q = pay_svc.latest_quotation(db, lead.lead_id)
    s = pay_svc.summary(db, lead)
    return {
        "lead_id": lead.lead_id, "enquiry_no": lead.enquiry_no, "customer_name": lead.customer.full_name,
        "mobile": lead.customer.phone, "branch": lead.branch.name if lead.branch else None,
        "pba": (lambda u: u.full_name if u else None)(db.get(AppUser, lead.assigned_user_id) if lead.assigned_user_id else None),
        "model": lead.model.name if lead.model else None, "color": lead.color,
        "bike_price": q.on_road_price if q else None,
        "discounted_price": ini.discounted_price if ini and ini.status == "APPROVED" else (q.discounted_price if q else None),
        "payment": payment_state(db, lead), "payments": s["payments"],
        "documents": documents_state(db, lead),
        "insurance": None if not ins else {"status": ins.status, "policy_no": ins.policy_no, "company": hs.POLICY_TYPES.get(ins.policy_type, (None, None))[1],
                                           "policy_expiry": ins.policy_expiry, "has_pdf": bool(ins.pdf_stored_path)},
        "atw": {"quoted": bool(q and q.engine_warranty_years == 10), "status": atw.status if atw else None},
        "rto": None if not rto else {"status": rto.status, "registration_no": rto.registration_no},
        "initial": stage_view(ini), "final": stage_view(fin),
        "workflow": workflow_status(db, lead),
    }


# ---------- customer journey (one picture for every department) ----------
def journey(db, lead: Lead, money: bool = True) -> dict:
    """Lead source -> enquiry -> follow-up -> test ride -> quotation -> booking -> approvals -> insurance ->
    RTO -> invoice -> delivery.  Each step: status DONE / CURRENT / WAITING / REJECTED and who holds it."""
    from app.modules.leads.models import LeadFollowup, LeadModelInterest, TestRide
    from sqlalchemy import func
    ini, fin = get_stage(db, lead.lead_id, "INITIAL"), get_stage(db, lead.lead_id, "FINAL")
    ins, rto = hs.get_case(db, InsuranceCase, lead.lead_id), hs.get_case(db, RtoCase, lead.lead_id)
    inv = hs.get_case(db, InvoiceDetail, lead.lead_id)
    q = pay_svc.latest_quotation(db, lead.lead_id)
    booking = pay_svc.get_booking(db, lead.lead_id)
    n_fu = db.query(func.count(LeadFollowup.id)).filter(LeadFollowup.lead_id == lead.lead_id).scalar() or 0
    n_tr = db.query(func.count(TestRide.id)).filter(TestRide.lead_id == lead.lead_id,
                                                   TestRide.completed.is_(True)).scalar() or 0
    delivered = lead.enquiry_stage == EnquiryStage.DELIVERED
    pay, doc = payment_state(db, lead), documents_state(db, lead)
    src = "LeadSquare" if str(getattr(lead.source, "value", lead.source)) == "CSV" else "Walk-in"
    steps = [
        ("enquiry", "Enquiry", "CRE / PBA", "DONE", f"{src} · {lead.enquiry_at:%d %b %Y}" if lead.enquiry_at else src),
        ("followup", "Follow-ups", "PBA / CRE", "DONE" if n_fu else "CURRENT", f"{n_fu} call(s)" if n_fu else "No call yet"),
        ("testride", "Test ride", "PBA", "DONE" if n_tr else "WAITING", f"{n_tr} completed" if n_tr else "Not done"),
        ("quotation", "Quotation", "PBA", "DONE" if q else "WAITING", q.quotation_no if q else "Not created"),
        ("booking", "Booking", "PBA", "DONE" if booking else "WAITING", booking.booking_no if booking else "Not booked"),
    ]
    def st(row):
        return {"APPROVED": "DONE", "PENDING": "CURRENT", "REJECTED": "REJECTED"}.get(row.status, "WAITING") if row else "WAITING"
    steps.append(("initial", "Initial Owner approval", "Owner", st(ini),
                  (f"₹ {ini.discounted_price:,.0f}" if ini and ini.status == "APPROVED" and ini.discounted_price else
                   (ini.remark if ini and ini.status == "REJECTED" else ("Waiting for Owner" if ini else "—")))))
    pd_ok = pay["ok"] and doc["ok"]
    steps.append(("paydocs", "Payment & documents", "PBA",
                  "DONE" if pd_ok else ("CURRENT" if ini and ini.status == "APPROVED" and ini.customer_processing else "WAITING"),
                  "Complete" if pd_ok else ("Payment pending" if not pay["ok"] else "Missing: " + ", ".join(doc["missing"][:2]))))
    steps.append(("insurance", "Insurance", "Insurance",
                  "DONE" if ins and ins.status == "COMPLETED" else ("CURRENT" if ins else "WAITING"),
                  (ins.policy_no or "In progress") if ins else "Starts after payment + documents"))
    steps.append(("final", "Final Owner approval", "Owner", st(fin),
                  fin.remark if fin and fin.status == "REJECTED" else ("Waiting for Owner" if fin and fin.status == "PENDING" else "—")))
    steps.append(("rto", "RTO", "RTO", "DONE" if rto and rto.status == "REGISTERED" else ("CURRENT" if rto else "WAITING"),
                  (rto.registration_no or hs.RTO_STATUSES.get(rto.status, "")) if rto else "After final approval"))
    steps.append(("invoice", "Invoice", "PBA", "DONE" if inv else ("CURRENT" if booking else "WAITING"),
                  inv.invoice_no or "Saved" if inv else "Not entered"))
    steps.append(("delivery", "Delivery", "PBA", "DONE" if delivered else ("CURRENT" if fin and fin.status == "APPROVED" else "WAITING"),
                  "Delivered" if delivered else ("Challan enabled" if fin and fin.status == "APPROVED" else "Locked")))
    # the single "who has it now" line: first step that is not done
    holder = next(((lbl, who, s_) for k, lbl, who, s_, _ in steps if s_ in ("CURRENT", "REJECTED")), None)
    if delivered:   # same-day delivery: the bike is out but the RTO registration may still be running
        holder = ("RTO registration (bike already delivered)", "RTO", "CURRENT") if rto and rto.status != "REGISTERED" else None
    summary = {"stage": getattr(lead.enquiry_stage, "value", lead.enquiry_stage), "quotation_no": q.quotation_no if q else None,
               "booking_no": booking.booking_no if booking else None,
               "other_models": [r.model.name for r in db.query(LeadModelInterest).filter(LeadModelInterest.lead_id == lead.lead_id)
                                 .order_by(LeadModelInterest.id.asc()).all()[1:] if r.model]}
    if money:   # prices / payments are not shown to RTO and Insurance
        price = ini.discounted_price if ini and ini.status == "APPROVED" and ini.discounted_price else (q.on_road_price if q else None)
        summary.update({"on_road_price": float(price) if price is not None else None,
                        "total_paid": float(pay["total_paid"] or 0), "outstanding": float(pay["outstanding"]) if pay["outstanding"] is not None else None})
    return {"lead_id": lead.lead_id, "enquiry_no": lead.enquiry_no, "customer_name": lead.customer.full_name,
            "summary": summary,
            "mobile": lead.customer.phone, "city": lead.customer.city, "source": src,
            "branch": lead.branch.name if lead.branch else None,
            "model": lead.model.name if lead.model else None, "color": lead.color,
            "now": None if not holder else {"step": holder[0], "department": holder[1],
                                                        "rejected": holder[2] == "REJECTED"},
            "steps": [{"key": k, "label": l, "dept": w, "status": s_, "detail": d} for k, l, w, s_, d in steps]}


def approval_cards(db, stage: str, status: str, page: int, size: int) -> dict:
    """Owner's queue: one row per approval (initial or final) with what is needed to decide. Paginated."""
    base = db.query(OwnerStageApproval, Lead).join(Lead, Lead.lead_id == OwnerStageApproval.lead_id)
    if stage in ("INITIAL", "FINAL"):
        base = base.filter(OwnerStageApproval.stage == stage)
    counts = {k: base.filter(OwnerStageApproval.status == k).count() for k in ("PENDING", "APPROVED", "REJECTED")}
    q = base.filter(OwnerStageApproval.status == status) if status in counts else base
    total = q.count()
    order = OwnerStageApproval.requested_at.asc() if status == "PENDING" else OwnerStageApproval.decided_at.desc().nullslast()
    rows = q.order_by(order).offset((page - 1) * size).limit(size).all()
    out = []
    for ap, lead in rows:
        qt = pay_svc.latest_quotation(db, lead.lead_id)
        card = {"lead_id": lead.lead_id, "enquiry_no": lead.enquiry_no, "customer_name": lead.customer.full_name,
                "mobile": lead.customer.phone, "city": lead.customer.city,
                "branch": lead.branch.name if lead.branch else None,
                "pba": (lambda u: u.full_name if u else None)(db.get(AppUser, lead.assigned_user_id) if lead.assigned_user_id else None),
                "model": lead.model.name if lead.model else None, "color": lead.color,
                "on_road_price": qt.on_road_price if qt else None, "discounted_price": ap.discounted_price,
                "payment_type": (qt.payment_type if qt else None), "down_payment": qt.down_payment if qt else None,
                "finance_bank": qt.finance_bank_name if qt else None,
                "atw_quoted": bool(qt and qt.engine_warranty_years == 10), "since": ap.requested_at,
                "round": ap.round_no, "stage": ap.stage, "status": ap.status, "decided_at": ap.decided_at,
                "decided_by": ap.decided_by.full_name if ap.decided_by else None, "remark": ap.remark,
                "customer_processing": ap.customer_processing, "atw_allowed": ap.atw_allowed}
        out.append(card)
    return {"total": total, "page": page, "page_size": size, "counts": counts, "rows": out}
