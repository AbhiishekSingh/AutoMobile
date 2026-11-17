"""GM consolidated numbers (on top of the Owner dashboard): PBA vs CRE, SLA compliance, booking-to-delivery funnel,
bottlenecks and the customer-wise status list. Cohort = leads enquired in the date range (after the chosen filters)."""
from datetime import date, datetime, time, timedelta

from sqlalchemy import func

from app.modules.cre_reports import service as cre_svc
from app.modules.handoffs.models import InsuranceCase, RtoCase
from app.modules.leads import sla
from app.modules.leads.models import BikeModel, EnquiryStage as S, Lead, LeadFollowup, LeadSource, TestRide, TestRideStatus
from app.modules.leads.stages import cancelled_booking_condition, delivered_condition, invoiced_condition, sold_condition
from app.modules.owner import service as owner_svc
from app.modules.payments.models import Booking
from app.modules.quotations.models import Quotation, QuotationStatus
from app.modules.users.models import AppUser, Branch, Role

ACTIVE = owner_svc.ACTIVE


def _pct(a, b):
    return round(a * 100 / b, 1) if b else 0


def cohort(db, start, end, branch_id=None, pba_id=None, model_id=None, source=None):
    q = db.query(Lead).filter(Lead.enquiry_at >= start, Lead.enquiry_at < end)
    if branch_id: q = q.filter(Lead.branch_id == branch_id)
    if pba_id: q = q.filter(Lead.assigned_user_id == pba_id)
    if model_id: q = q.filter(Lead.model_id == model_id)
    if source: q = q.filter(Lead.source == LeadSource(source))
    return q


def _ids(q):
    return {r[0] for r in q.with_entities(Lead.lead_id).all()}


def performance(db, date_from, date_to, branch_id=None, pba_id=None, cre_id=None, model_id=None, source=None):
    start, end, d1, d2 = cre_svc.window(date_from, date_to)
    base = cohort(db, start, end, branch_id, pba_id, model_id, source)
    leads = base.all()
    ids = {l.lead_id for l in leads}
    now = datetime.now()
    booked, invoiced, delivered = (_ids(base.filter(c)) for c in (sold_condition(db), invoiced_condition(db), delivered_condition(db)))
    cancelled = _ids(base.filter(cancelled_booking_condition(db)))
    ins = {i.lead_id: i.status for i in db.query(InsuranceCase).filter(InsuranceCase.lead_id.in_(ids or [-1])).all()}
    rto = {r.lead_id: r.status for r in db.query(RtoCase).filter(RtoCase.lead_id.in_(ids or [-1])).all()}
    tr = db.query(TestRide.lead_id, TestRide.status).filter(TestRide.lead_id.in_(ids or [-1])).all()
    quo = {r[0] for r in db.query(Quotation.lead_id).filter(Quotation.lead_id.in_(ids or [-1]), Quotation.status != QuotationStatus.DRAFT).all()}
    users = {u.user_id: u for u in db.query(AppUser).all()}
    bnames = {b.branch_id: b.name for b in db.query(Branch).all()}
    calls = {}
    for uid, in db.query(LeadFollowup.user_id).filter(LeadFollowup.lead_id.in_(ids or [-1]), LeadFollowup.created_at >= start, LeadFollowup.created_at < end).all():
        calls[uid] = calls.get(uid, 0) + 1

    # ---- PBA-wise ----
    rows = {}
    def row(uid):
        u = users.get(uid)
        return rows.setdefault(uid, {"user_id": uid, "name": u.full_name if u else "Unassigned", "branch": bnames.get(u.branch_id) if u else None,
                                     "leads": 0, "contacted": 0, "sla_green": 0, "sla_red": 0, "sla_wait": 0, "overdue_followups": 0,
                                     "calls": calls.get(uid, 0), "test_rides": 0, "test_rides_done": 0, "quotations": 0, "booked": 0,
                                     "invoiced": 0, "delivered": 0, "cancelled": 0, "ins_pending": 0, "rto_pending": 0})
    for l in leads:
        r = row(l.assigned_user_id)
        r["leads"] += 1
        r["contacted"] += 1 if l.first_contact_at else 0
        st = sla.sla_state(l.enquiry_at, l.first_contact_at, now)
        if st == sla.COMPLETED: r["sla_green"] += 1
        elif st in (sla.LATE, sla.OVERDUE): r["sla_red"] += 1
        else: r["sla_wait"] += 1
        if l.enquiry_stage == S.OPEN and l.next_followup_at and l.next_followup_at < now: r["overdue_followups"] += 1
        if l.lead_id in quo: r["quotations"] += 1
        if l.lead_id in booked: r["booked"] += 1
        if l.lead_id in invoiced: r["invoiced"] += 1
        if l.lead_id in delivered: r["delivered"] += 1
        if l.lead_id in cancelled: r["cancelled"] += 1
        if l.lead_id in booked and l.enquiry_stage in ACTIVE:
            r["ins_pending"] += 0 if ins.get(l.lead_id) == "COMPLETED" else 1
            r["rto_pending"] += 0 if rto.get(l.lead_id) == "REGISTERED" else 1
    owner = {l.lead_id: l.assigned_user_id for l in leads}
    for lid, s in tr:
        r = row(owner[lid]); r["test_rides"] += 1; r["test_rides_done"] += 1 if s == TestRideStatus.COMPLETED else 0
    pba_rows = sorted(rows.values(), key=lambda r: (-r["booked"], r["name"]))
    for r in pba_rows:
        r["conversion_pct"] = _pct(r["booked"], r["leads"])
        r["sla_pct"] = _pct(r["sla_green"], r["leads"])
        r["contacted_pct"] = _pct(r["contacted"], r["leads"])

    # ---- CRE-wise (existing CRE report) + PBA vs CRE ----
    cre = cre_svc.report(db, d1, d2, cre_id=cre_id, branch_id=branch_id, f={"source": source} if source else {})
    ct = cre["total"]
    pt = lambda k: sum(r[k] for r in pba_rows)
    versus = [
        {"team": "PBA team", "leads": pt("leads"), "contacted": pt("contacted"), "calls": pt("calls"), "test_rides": pt("test_rides"),
         "quotations": pt("quotations"), "booked": pt("booked"), "delivered": pt("delivered")},
        {"team": "CRE team", "leads": ct["total"], "contacted": ct["contacted"], "calls": sum(r["calls"] for r in cre["rows"]),
         "test_rides": ct["tr_booked"], "quotations": ct["quotations"], "booked": ct["booked"], "delivered": ct["delivered"]}]
    for v in versus:
        v["conversion_pct"] = _pct(v["booked"], v["leads"])

    # ---- funnel + SLA ----
    funnel = [{"label": "Leads", "count": len(ids)}, {"label": "Contacted", "count": sum(1 for l in leads if l.first_contact_at)},
              {"label": "Quotation shared", "count": len(quo)}, {"label": "Test ride", "count": len({l for l, _ in tr})},
              {"label": "Booked", "count": len(booked)},
              {"label": "Insurance done", "count": sum(1 for i in booked if ins.get(i) == "COMPLETED")},
              {"label": "RTO registered", "count": sum(1 for i in booked if rto.get(i) == "REGISTERED")},
              {"label": "Invoiced", "count": len(invoiced)}, {"label": "Delivered", "count": len(delivered)}]
    slat = {"green": sum(r["sla_green"] for r in pba_rows), "red": sum(r["sla_red"] for r in pba_rows), "waiting": sum(r["sla_wait"] for r in pba_rows)}
    slat["compliance_pct"] = _pct(slat["green"], len(ids))

    # ---- bottlenecks right now (department-wise) ----
    snap = owner_svc.sales_snapshot(db, branch_id)
    if pba_id: snap = [r for r in snap if r["lead"].assigned_user_id == pba_id]
    if model_id: snap = [r for r in snap if r["lead"].model_id == model_id]
    act = [r for r in snap if r["stage"] in ACTIVE]
    wide = db.query(Lead)
    if branch_id: wide = wide.filter(Lead.branch_id == branch_id)
    if pba_id: wide = wide.filter(Lead.assigned_user_id == pba_id)
    bott = [
        {"key": "UNASSIGNED", "label": "Leads not assigned to a PBA", "count": wide.filter(Lead.assigned_user_id.is_(None), Lead.enquiry_stage == S.OPEN).count(), "dept": "Sales"},
        {"key": "SLA_RED", "label": "Leads not contacted in time (open)", "count": sum(1 for l in wide.filter(Lead.enquiry_stage == S.OPEN, Lead.first_contact_at.is_(None)).all()
                                                                       if sla.sla_state(l.enquiry_at, None, now) in (sla.PENDING, sla.OVERDUE)), "dept": "PBA"},
        {"key": "OVERDUE_FU", "label": "Overdue follow-ups", "count": wide.filter(Lead.enquiry_stage == S.OPEN, Lead.next_followup_at < now).count(), "dept": "PBA / CRE"},
        {"key": "PAYMENT", "label": "Payment pending", "count": sum(1 for r in snap if r["pay_status"] != "PAID" and (r["outstanding"] or 0) > 0), "dept": "Accounts"},
        {"key": "INSURANCE", "label": "Insurance pending", "count": sum(1 for r in act if r["insurance"] != "COMPLETED"), "dept": "Insurance"},
        {"key": "RTO", "label": "RTO pending", "count": sum(1 for r in act if r["rto"] != "REGISTERED"), "dept": "RTO"},
        {"key": "INVOICE", "label": "Invoice pending", "count": sum(1 for r in act if r["stage"] != S.INVOICED), "dept": "PBA"},
        {"key": "DELIVERY", "label": "Pending customer deliveries", "count": len(act), "dept": "Showroom"},
        {"key": "FINAL_REVIEW", "label": "Final reviews pending", "count": wide.filter(Lead.enquiry_stage == S.DELIVERED).count(), "dept": "CRE"}]
    return {"from": d1, "to": d2, "pba": pba_rows, "cre": cre["rows"], "versus": versus, "funnel": funnel, "sla": slat, "bottlenecks": bott,
            "model_options": [{"id": m.id, "name": m.name} for m in db.query(BikeModel).order_by(BikeModel.name).all()],
            "pba_options": [{"id": u.user_id, "name": u.full_name} for u in users.values() if u.role == Role.PBA and u.is_active],
            "cre_options": [{"id": u.user_id, "name": u.full_name} for u in users.values() if u.role == Role.CRE and u.is_active]}


def customers(db, branch_id=None, pba_id=None, model_id=None, source=None, booking_status="ACTIVE", insurance_status=None,
              rto_status=None, delivery_status=None, date_from=None, date_to=None):
    """Customer-wise booking status: every booked customer with payment, insurance, RTO and delivery state."""
    names = {u.user_id: u.full_name for u in db.query(AppUser).all()}
    bnames = {b.branch_id: b.name for b in db.query(Branch).all()}
    models = {m.id: m.name for m in db.query(BikeModel).all()}
    out = []
    if booking_status == "CANCELLED":
        for r in owner_svc.pending_list(db, "CANCELLED", branch_id):
            out.append({**r, "booking_status": "Cancelled", "payment": "-", "insurance": "-", "rto": "-", "delivery": "-", "model": None, "source": None})
        return out
    for r in owner_svc.sales_snapshot(db, branch_id):
        l = r["lead"]
        if pba_id and l.assigned_user_id != pba_id: continue
        if model_id and l.model_id != model_id: continue
        if source and l.source.value != source: continue
        bd = r["booking"].created_at
        if date_from and bd.date() < date_from: continue
        if date_to and bd.date() > date_to: continue
        dstat = "DELIVERED" if r["stage"] in (S.DELIVERED, S.CLOSED) else "PENDING"
        if insurance_status and r["insurance"] != insurance_status: continue
        if rto_status and r["rto"] != rto_status: continue
        if delivery_status and dstat != delivery_status: continue
        out.append({"lead_id": l.lead_id, "enquiry_no": l.enquiry_no, "customer": l.customer.full_name, "phone": l.customer.phone,
                    "branch": bnames.get(l.branch_id), "pba": names.get(l.assigned_user_id), "model": models.get(l.model_id),
                    "source": l.source.value, "stage": l.enquiry_stage.value, "booking_status": "Booked", "booked_on": bd,
                    "payment": r["pay_status"], "outstanding": round(float(r["outstanding"] or 0)), "insurance": r["insurance"],
                    "rto": r["rto"], "delivery": dstat})
    return out
