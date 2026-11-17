"""Owner KPI view: sales-funnel conversion and deal-workflow speed.

Funnel = the enquiries RECEIVED in the chosen window, followed through the journey (a cohort), so every
percentage answers "of the customers who enquired, how many got to this step". Counts are done in SQL with
EXISTS sub-queries (indexed on lead_id), so this stays fast with lakhs of leads.

Speed = for each hand-over in the deal workflow, how long it took (events that FINISHED inside the window),
plus the deals that have been waiting the longest right now.
"""
from datetime import datetime, timedelta
from statistics import median

from sqlalchemy import and_, exists, func
from sqlalchemy.orm import Session

from app.core.database import now_ist
from app.modules.handoffs.models import InsuranceCase
from app.modules.leads.models import Lead, StageHistory, TestRide
from app.modules.owner.service import _dt, window
from app.modules.owner_flow.models import OwnerStageApproval
from app.modules.payments.models import Booking
from app.modules.quotations.models import Quotation
from app.modules.users.models import Branch

FUNNEL = [("enquiry", "Enquiries"), ("followup", "Followed up"), ("testride", "Test ride done"),
          ("quotation", "Quotation given"), ("booking", "Booked"), ("approved", "Owner approved"), ("delivered", "Delivered")]


def _conds(db: Session):
    """EXISTS conditions per funnel step (each correlated to Lead)."""
    L = Lead.lead_id
    return {
        "enquiry": None,
        "followup": Lead.first_contact_at.isnot(None),
        "testride": exists().where(and_(TestRide.lead_id == L, TestRide.completed.is_(True))),
        "quotation": exists().where(Quotation.lead_id == L),
        "booking": exists().where(Booking.lead_id == L),
        "approved": exists().where(and_(OwnerStageApproval.lead_id == L, OwnerStageApproval.stage == "INITIAL",
                                        OwnerStageApproval.status == "APPROVED")),
        "delivered": exists().where(and_(StageHistory.lead_id == L, StageHistory.to_stage == "DELIVERED")),
    }


def funnel(db: Session, start, end, branch_id=None):
    base = [Lead.enquiry_at >= _dt(start), Lead.enquiry_at < _dt(end)]
    if branch_id:
        base.append(Lead.branch_id == branch_id)
    conds = _conds(db)
    total, by_branch = {}, {}
    for key, _ in FUNNEL:
        f = list(base) + ([conds[key]] if conds[key] is not None else [])
        total[key] = db.query(func.count(Lead.lead_id)).filter(*f).scalar() or 0
        for bid, n in db.query(Lead.branch_id, func.count(Lead.lead_id)).filter(*f).group_by(Lead.branch_id).all():
            by_branch.setdefault(bid, {})[key] = n
    n0 = total["enquiry"]
    steps, prev = [], n0
    for key, label in FUNNEL:
        n = total[key]
        steps.append({"key": key, "label": label, "count": n,
                      "pct_of_enquiries": round(100 * n / n0, 1) if n0 else None,
                      "pct_of_previous": round(100 * n / prev, 1) if prev else None})
        prev = n
    names = {b.branch_id: b.name for b in db.query(Branch).all()}
    rows = []
    for bid, vals in by_branch.items():
        e = vals.get("enquiry", 0)
        rows.append({"branch_id": bid, "branch": names.get(bid, "No branch"), "enquiry": e,
                     **{k: vals.get(k, 0) for k, _ in FUNNEL[1:]},
                     "booking_pct": round(100 * vals.get("booking", 0) / e, 1) if e else None,
                     "delivered_pct": round(100 * vals.get("delivered", 0) / e, 1) if e else None})
    rows.sort(key=lambda r: -r["enquiry"])
    return {"steps": steps, "branches": rows}


def _hours(a, b):
    return (b - a).total_seconds() / 3600 if a and b and b >= a else None


def _stat(label, pairs, hint):
    hrs = [h for h in (_hours(a, b) for a, b in pairs) if h is not None]
    return {"label": label, "hint": hint, "count": len(hrs),
            "avg_hours": round(sum(hrs) / len(hrs), 1) if hrs else None,
            "median_hours": round(median(hrs), 1) if hrs else None,
            "max_hours": round(max(hrs), 1) if hrs else None}


def speed(db: Session, start, end, branch_id=None):
    s, e = _dt(start), _dt(end)
    OSA = OwnerStageApproval
    def branch(q):
        return q.join(Lead, Lead.lead_id == OSA.lead_id).filter(Lead.branch_id == branch_id) if branch_id else q

    # 1. Booking -> Initial Owner decision (decision made inside the window)
    q = db.query(Booking.created_at, OSA.decided_at).join(OSA, and_(OSA.lead_id == Booking.lead_id, OSA.stage == "INITIAL")) \
        .filter(OSA.status.in_(["APPROVED", "REJECTED"]), OSA.decided_at >= s, OSA.decided_at < e)
    if branch_id:
        q = q.filter(Booking.branch_id == branch_id)
    p1 = q.all()
    # 1b. Owner's own response time, request -> decision (initial + final)
    q = db.query(OSA.requested_at, OSA.decided_at).filter(OSA.status.in_(["APPROVED", "REJECTED"]), OSA.decided_at >= s, OSA.decided_at < e)
    p1b = branch(q).all()
    # 2. Initial approval -> Insurance completed
    q = db.query(OSA.decided_at, InsuranceCase.completed_at).join(InsuranceCase, InsuranceCase.lead_id == OSA.lead_id) \
        .filter(OSA.stage == "INITIAL", OSA.status == "APPROVED", InsuranceCase.completed_at >= s, InsuranceCase.completed_at < e)
    p2 = branch(q).all()
    # 3. Insurance completed -> Final Owner decision
    q = db.query(InsuranceCase.completed_at, OSA.decided_at).join(OSA, and_(OSA.lead_id == InsuranceCase.lead_id, OSA.stage == "FINAL")) \
        .filter(OSA.status.in_(["APPROVED", "REJECTED"]), OSA.decided_at >= s, OSA.decided_at < e)
    if branch_id:
        q = q.join(Lead, Lead.lead_id == OSA.lead_id).filter(Lead.branch_id == branch_id)
    p3 = q.all()

    # 4-6. stage hops from the stage history (RTO done, Invoiced, Delivered) + 7. Booking -> Delivered
    def hist(stage):
        q = db.query(StageHistory.lead_id, func.min(StageHistory.changed_at)).filter(StageHistory.to_stage == stage)
        if branch_id:
            q = q.join(Lead, Lead.lead_id == StageHistory.lead_id).filter(Lead.branch_id == branch_id)
        return dict(q.group_by(StageHistory.lead_id).having(and_(func.min(StageHistory.changed_at) >= s, func.min(StageHistory.changed_at) < e)).all())
    def at(stage, lead_ids):
        if not lead_ids:
            return {}
        return dict(db.query(StageHistory.lead_id, func.min(StageHistory.changed_at))
                    .filter(StageHistory.to_stage == stage, StageHistory.lead_id.in_(lead_ids)).group_by(StageHistory.lead_id).all())
    rto_done, invoiced, delivered = hist("RTO_DONE"), hist("INVOICED"), hist("DELIVERED")
    final_ok = {r.lead_id: r.decided_at for r in db.query(OSA.lead_id, OSA.decided_at)
                .filter(OSA.stage == "FINAL", OSA.status == "APPROVED", OSA.lead_id.in_(list(rto_done) or [0])).all()}
    p4 = [(final_ok.get(l), t) for l, t in rto_done.items()]
    inv_prev = at("RTO_DONE", list(invoiced))
    p5 = [(inv_prev.get(l), t) for l, t in invoiced.items()]
    del_prev = at("INVOICED", list(delivered))
    p6 = [(del_prev.get(l), t) for l, t in delivered.items()]
    bk = dict(db.query(Booking.lead_id, Booking.created_at).filter(Booking.lead_id.in_(list(delivered) or [0])).all())
    p7 = [(bk.get(l), t) for l, t in delivered.items()]

    stats = [
        _stat("Booking → Initial Owner decision", p1, "Booking made until the Owner approves or rejects"),
        _stat("Owner response time (initial + final)", p1b, "From the request reaching the Owner to the decision"),
        _stat("Initial approval → Insurance done", p2, "Payment, documents and the insurance team's work"),
        _stat("Insurance done → Final Owner decision", p3, "Waiting for the final approval"),
        _stat("Final approval → RTO done", p4, "Registration time"),
        _stat("RTO done → Invoiced", p5, "Invoice entry"),
        _stat("Invoiced → Delivered", p6, "Handover to the customer"),
        _stat("Booking → Delivered (whole deal)", p7, "End to end"),
    ]
    return stats


def waiting_now(db: Session, branch_id=None, limit=12):
    """The deals that have been waiting longest right now, with who holds them."""
    now = now_ist()
    out = []
    def add(rows, step, dept):
        for lead, since in rows:
            out.append({"lead_id": lead.lead_id, "enquiry_no": lead.enquiry_no, "customer": lead.customer.full_name,
                        "step": step, "department": dept, "since": since,
                        "waiting_hours": round(_hours(since, now) or 0, 1)})
    def lq(q):
        return q.filter(Lead.branch_id == branch_id) if branch_id else q
    OSA = OwnerStageApproval
    for stage, label in (("INITIAL", "Initial Owner approval"), ("FINAL", "Final Owner approval")):
        add(lq(db.query(Lead, OSA.requested_at).join(OSA, OSA.lead_id == Lead.lead_id)
               .filter(OSA.stage == stage, OSA.status == "PENDING")).order_by(OSA.requested_at.asc()).limit(limit).all(), label, "Owner")
    add(lq(db.query(Lead, InsuranceCase.created_at).join(InsuranceCase, InsuranceCase.lead_id == Lead.lead_id)
           .filter(InsuranceCase.status != "COMPLETED")).order_by(InsuranceCase.created_at.asc()).limit(limit).all(), "Insurance", "Insurance")
    from app.modules.handoffs.models import RtoCase
    add(lq(db.query(Lead, RtoCase.created_at).join(RtoCase, RtoCase.lead_id == Lead.lead_id)
           .filter(RtoCase.status != "REGISTERED")).order_by(RtoCase.created_at.asc()).limit(limit).all(), "RTO registration", "RTO")
    out.sort(key=lambda r: -r["waiting_hours"])
    return out[:limit]


def kpi(db: Session, period: str, anchor, branch_id=None):
    start, end, label = window(period, anchor)
    return {"period": period, "label": label, "start": start, "end": end - timedelta(days=1),
            "branch_options": [{"id": b.branch_id, "name": b.name} for b in db.query(Branch).order_by(Branch.name).all()],
            "funnel": funnel(db, start, end, branch_id), "speed": speed(db, start, end, branch_id),
            "waiting": waiting_now(db, branch_id)}
