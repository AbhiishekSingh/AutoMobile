"""Owner dashboard numbers: PBA-wise, branch-wise, pending work, collections, stock.

Period numbers (leads, bookings, invoiced, delivered, collection, test rides, cancellations) are events inside the
chosen window. "Snapshot" numbers (outstanding, insurance / RTO / invoice / delivery pending, booked stock) are
how things stand right now, whatever the window.
"""
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.accounts import service as acct_svc
from app.modules.handoffs.models import InsuranceCase, RtoCase
from app.modules.leads.models import BikeModel, EnquiryStage as S, Lead, StageHistory, TestRide, TestRideStatus
from app.modules.leads.stages import CANCELLABLE_STAGES, sold_condition
from app.modules.payments.models import Booking, Payment
from app.modules.payments.service import _cost, latest_quotation, money, payment_status
from app.modules.stock import service as stock_svc
from app.modules.stock.models import StockItem, StockMovement
from app.modules.targets.models import SalesTarget
from app.modules.users.models import AppUser, Branch, Role

PERIODS = ("day", "week", "month", "quarter", "year")
ACTIVE = (S.BOOKED, S.INSURANCE_DONE, S.RTO_DONE, S.INVOICED)     # booked, not yet delivered


# ---------- windows ----------
def _shift_months(d: date, n: int) -> date:
    m = d.year * 12 + d.month - 1 + n
    return date(m // 12, m % 12 + 1, 1)


def window(period: str, anchor: date):
    """(start date, end date exclusive, label)."""
    if period == "day":
        s, e = anchor, anchor + timedelta(days=1); lab = anchor.strftime("%d %b %Y")
    elif period == "week":
        s = anchor - timedelta(days=anchor.weekday()); e = s + timedelta(days=7)
        lab = f"{s.strftime('%d %b')} – {(e - timedelta(days=1)).strftime('%d %b %Y')}"
    elif period == "month":
        s = date(anchor.year, anchor.month, 1); e = _shift_months(s, 1); lab = s.strftime("%B %Y")
    elif period == "quarter":
        s = date(anchor.year, 3 * ((anchor.month - 1) // 3) + 1, 1); e = _shift_months(s, 3)
        lab = f"Q{(s.month - 1) // 3 + 1} {s.year} ({s.strftime('%b')}–{_shift_months(s, 2).strftime('%b')})"
    else:
        s = date(anchor.year, 1, 1); e = date(anchor.year + 1, 1, 1); lab = str(anchor.year)
    return s, e, lab


def previous_anchor(period: str, anchor: date) -> date:
    if period == "day": return anchor - timedelta(days=1)
    if period == "week": return anchor - timedelta(days=7)
    if period == "month": return _shift_months(date(anchor.year, anchor.month, 1), -1)
    if period == "quarter": return _shift_months(window("quarter", anchor)[0], -3)
    return date(anchor.year - 1, 1, 1)


def _dt(d: date) -> datetime:
    return datetime.combine(d, datetime.min.time())


def growth(cur, prev):
    if prev in (0, None):
        return None if not cur else 100
    return round((cur - prev) * 100 / prev)


# ---------- snapshot of booked customers ----------
def sales_snapshot(db: Session, branch_id=None):
    """One dict per customer with a (non-cancelled) booking: stage, money, insurance, RTO."""
    q = (db.query(Lead, Booking).join(Booking, Booking.lead_id == Lead.lead_id).filter(sold_condition(db)))
    if branch_id:
        q = q.filter(Lead.branch_id == branch_id)
    ins = {i.lead_id: i.status for i in db.query(InsuranceCase).all()}
    rto = {r.lead_id: r.status for r in db.query(RtoCase).all()}
    paid = dict(db.query(Payment.booking_id, func.coalesce(func.sum(Payment.amount), 0)).group_by(Payment.booking_id).all())
    out = []
    for lead, bk in q.all():
        cost = _cost(bk, None) if bk.quotation else None
        if cost is None:
            ql = latest_quotation(db, lead.lead_id)
            cost = money(ql.on_road_price) if ql else None
        p = money(paid.get(bk.booking_id, 0))
        out.append({"lead": lead, "booking": bk, "stage": lead.enquiry_stage, "cost": cost, "paid": p,
                    "outstanding": (cost - p) if cost is not None else Decimal(0),
                    "pay_status": payment_status(cost, p),
                    "insurance": ins.get(lead.lead_id, "PENDING"), "rto": rto.get(lead.lead_id, "PENDING")})
    return out


def _zero():
    return defaultdict(int)


def period_counts(db: Session, start: date, end: date, branch_id=None):
    """Event counts in [start, end): returns {'pba': {uid: counts}, 'branch': {bid: counts}, 'models': {...}}."""
    s, e = _dt(start), _dt(end)
    lead_info = {r[0]: (r[1], r[2], r[3]) for r in db.query(Lead.lead_id, Lead.assigned_user_id, Lead.branch_id, Lead.model_id).all()}
    pba, br = defaultdict(_zero), defaultdict(_zero)
    models = defaultdict(_zero)

    def add(lead_id, key, n=1, amount=None):
        info = lead_info.get(lead_id)
        if not info:
            return
        uid, bid, mid = info
        if branch_id and bid != branch_id:
            return
        pba[uid][key] += n; br[bid][key] += n
        if amount is not None:
            pba[uid][key + "_amt"] += float(amount); br[bid][key + "_amt"] += float(amount)
        return mid

    for (lid,) in db.query(Lead.lead_id).filter(Lead.enquiry_at >= s, Lead.enquiry_at < e).all():
        add(lid, "leads")
    for lid, in db.query(Booking.lead_id).join(Lead, Lead.lead_id == Booking.lead_id) \
            .filter(Booking.created_at >= s, Booking.created_at < e, sold_condition(db)).all():
        m = add(lid, "bookings")
        if m: models[m]["bookings"] += 1
    for to_stage, key in ((S.INVOICED.value, "invoiced"), (S.DELIVERED.value, "delivered")):
        for lid, in db.query(StageHistory.lead_id).filter(StageHistory.to_stage == to_stage,
                                                          StageHistory.changed_at >= s, StageHistory.changed_at < e).distinct().all():
            m = add(lid, key)
            if m: models[m][key] += 1
    for lid, amt in db.query(Payment.lead_id, Payment.amount).filter(Payment.payment_date >= start, Payment.payment_date < end).all():
        add(lid, "collection", 0, amt)
    for lid, status, sched in db.query(TestRide.lead_id, TestRide.status, TestRide.scheduled_at).filter(
            TestRide.scheduled_at >= s, TestRide.scheduled_at < e).all():
        add(lid, "test_rides")
        if status == TestRideStatus.COMPLETED: add(lid, "test_rides_done")
    booked_leads = {r[0] for r in db.query(Booking.lead_id).all()}
    paid_by_lead = dict(db.query(Payment.lead_id, func.sum(Payment.amount)).group_by(Payment.lead_id).all())
    for lid, in db.query(StageHistory.lead_id).filter(
            StageHistory.to_stage == S.CLOSED.value, StageHistory.from_stage.in_([x.value for x in CANCELLABLE_STAGES]),
            StageHistory.changed_at >= s, StageHistory.changed_at < e).distinct().all():
        if lid in booked_leads:
            add(lid, "cancelled", 1, paid_by_lead.get(lid) or 0)
    return {"pba": pba, "branch": br, "models": models}


def targets_by(db: Session, start: date, end: date):
    """Monthly targets inside the window: ({pba id: qty}, {branch id: qty}); None for day/week windows."""
    rows = db.query(SalesTarget.user_id, SalesTarget.qty).filter(SalesTarget.month >= date(start.year, start.month, 1), SalesTarget.month < end).all()
    bu = {u.user_id: u.branch_id for u in db.query(AppUser).filter(AppUser.role == Role.PBA).all()}
    pba, br = defaultdict(int), defaultdict(int)
    for uid, q in rows:
        pba[uid] += q; br[bu.get(uid)] += q
    return pba, br


# ---------- the dashboard ----------
def dashboard(db: Session, period: str, anchor: date, branch_id=None):
    start, end, label = window(period, anchor)
    pa = previous_anchor(period, anchor)
    pstart, pend, plabel = window(period, pa)
    cur, prev = period_counts(db, start, end, branch_id), period_counts(db, pstart, pend, branch_id)
    snap = sales_snapshot(db, branch_id)
    use_targets = period in ("month", "quarter", "year")
    tp, tb = targets_by(db, start, end) if use_targets else ({}, {})

    users = {u.user_id: u for u in db.query(AppUser).filter(AppUser.role == Role.PBA).all()}
    branches = {b.branch_id: b for b in db.query(Branch).filter(Branch.is_active == True).all()}  # noqa: E712
    stock_b = {b["id"]: b for b in stock_svc.summary(db, None)["branches"]}

    # snapshot per PBA / branch
    def snap_roll(key):
        d = defaultdict(lambda: defaultdict(float))
        for r in snap:
            k = r["lead"].assigned_user_id if key == "pba" else r["lead"].branch_id
            x = d[k]
            x["outstanding"] += float(r["outstanding"] or 0)
            x["booked_value"] += float(r["cost"] or 0)
            if r["pay_status"] == "PAID": x["paid_n"] += 1
            elif r["pay_status"] == "PARTIALLY_PAID": x["partial_n"] += 1
            else: x["pending_n"] += 1
            x["ins_done"] += 1 if r["insurance"] == "COMPLETED" else 0
            x["rto_done"] += 1 if r["rto"] == "REGISTERED" else 0
            if r["stage"] in ACTIVE:
                x["booked_stock"] += 1
                x["ins_pending"] += 0 if r["insurance"] == "COMPLETED" else 1
                x["rto_pending"] += 0 if r["rto"] == "REGISTERED" else 1
                x["delivery_pending"] += 1
                x["invoice_pending"] += 0 if r["stage"] == S.INVOICED else 1
        return d
    sp, sb = snap_roll("pba"), snap_roll("branch")

    def pct(a, b): return round(a * 100 / b) if b else None

    pba_rows = []
    pba_ids = set(cur["pba"]) | set(sp) | {u for u, x in users.items() if not branch_id or x.branch_id == branch_id}
    for uid in pba_ids:
        u = users.get(uid)
        if branch_id and u is not None and u.branch_id != branch_id:
            continue
        c, p, s = cur["pba"].get(uid, _zero()), prev["pba"].get(uid, _zero()), sp.get(uid, {})
        tgt = tp.get(uid, 0) if use_targets else None
        pba_rows.append({
            "user_id": uid, "name": u.full_name if u else "Unassigned", "branch": branches[u.branch_id].name if u and u.branch_id in branches else None,
            "leads": c["leads"], "bookings": c["bookings"], "bookings_prev": p["bookings"], "bookings_growth": growth(c["bookings"], p["bookings"]),
            "target": tgt, "achievement_pct": pct(c["bookings"], tgt) if tgt else None,
            "invoiced": c["invoiced"], "delivered": c["delivered"],
            "booking_amount": round(c["collection_amt"]), "outstanding": round(s.get("outstanding", 0)),
            "pay_paid": int(s.get("paid_n", 0)), "pay_partial": int(s.get("partial_n", 0)), "pay_pending": int(s.get("pending_n", 0)),
            "ins_done": int(s.get("ins_done", 0)), "ins_pending": int(s.get("ins_pending", 0)),
            "rto_done": int(s.get("rto_done", 0)), "rto_pending": int(s.get("rto_pending", 0)),
            "test_rides": c["test_rides"], "test_rides_done": c["test_rides_done"], "cancelled": c["cancelled"],
            "conversion_pct": pct(c["bookings"], c["leads"])})
    pba_rows = [r for r in pba_rows if r["name"] != "Unassigned" or r["leads"] or r["bookings"]]
    pba_rows.sort(key=lambda r: (-r["bookings"], r["name"]))

    branch_rows = []
    for bid, b in branches.items():
        if branch_id and bid != branch_id:
            continue
        c, p, s = cur["branch"].get(bid, _zero()), prev["branch"].get(bid, _zero()), sb.get(bid, {})
        st = stock_b.get(bid, {})
        tgt = tb.get(bid, 0) if use_targets else None
        branch_rows.append({
            "branch_id": bid, "name": b.name, "code": b.dealer_code, "leads": c["leads"], "bookings": c["bookings"],
            "bookings_prev": p["bookings"], "bookings_growth": growth(c["bookings"], p["bookings"]),
            "invoiced": c["invoiced"], "delivered": c["delivered"], "target": tgt, "achievement_pct": pct(c["bookings"], tgt) if tgt else None,
            "stock_vehicles": st.get("VEHICLE", 0), "stock_helmets": st.get("HELMET", 0), "stock_covers": st.get("PARKING_COVER", 0),
            "booked_stock": int(s.get("booked_stock", 0)), "ins_pending": int(s.get("ins_pending", 0)), "rto_pending": int(s.get("rto_pending", 0)),
            "invoice_pending": int(s.get("invoice_pending", 0)), "delivery_pending": int(s.get("delivery_pending", 0)),
            "booking_amount": round(c["collection_amt"]), "booked_value": round(s.get("booked_value", 0)),
            "outstanding": round(s.get("outstanding", 0)), "pay_paid": int(s.get("paid_n", 0)),
            "pay_partial": int(s.get("partial_n", 0)), "pay_pending": int(s.get("pending_n", 0)),
            "cancelled": c["cancelled"], "cancelled_amount": round(c["cancelled_amt"]),
            "test_rides": c["test_rides"], "conversion_pct": pct(c["bookings"], c["leads"])})
    branch_rows.sort(key=lambda r: -r["bookings"])

    def tot(k, d): return sum(v[k] for v in d["branch"].values())
    head = []
    for key, label in (("leads", "Leads"), ("bookings", "Bookings"), ("invoiced", "Invoiced"), ("delivered", "Delivered"),
                       ("cancelled", "Cancelled bookings")):
        c, p = tot(key, cur), tot(key, prev)
        head.append({"key": key, "label": label, "current": c, "previous": p, "growth": growth(c, p)})
    cc, pc = round(tot("collection_amt", cur)), round(tot("collection_amt", prev))
    head.append({"key": "collection", "label": "Collection (Rs)", "current": cc, "previous": pc, "growth": growth(cc, pc), "money": True})
    tt = sum(tb.values()) if use_targets else None
    models = {m.id: m.name for m in db.query(BikeModel).all()}
    model_rows = sorted(({"model": models.get(mid, "Unknown"), "bookings": v["bookings"], "invoiced": v["invoiced"], "delivered": v["delivered"]}
                         for mid, v in cur["models"].items()), key=lambda r: -r["bookings"])
    pend = {k: sum(r[k] for r in branch_rows) for k in ("ins_pending", "rto_pending", "invoice_pending", "delivery_pending")}
    acct = {"collection": cc, "collection_prev": pc, "collection_growth": growth(cc, pc),
            "booked_value": sum(r["booked_value"] for r in branch_rows), "outstanding": sum(r["outstanding"] for r in branch_rows),
            "paid": sum(r["pay_paid"] for r in branch_rows), "partial": sum(r["pay_partial"] for r in branch_rows),
            "pending": sum(r["pay_pending"] for r in branch_rows),
            "cancelled": sum(r["cancelled"] for r in branch_rows), "cancelled_amount": sum(r["cancelled_amount"] for r in branch_rows),
            **acct_svc.all_totals(db, branch_id)}
    return {"period": period, "label": label, "previous_label": plabel, "start": start, "end": end - timedelta(days=1),
            "anchor": anchor, "branch_id": branch_id, "branch_name": branches[branch_id].name if branch_id in branches else None,
            "headline": head, "target_total": tt, "pending": pend, "accounting": acct, "pba": pba_rows,
            "branches": branch_rows, "models": model_rows, "stock": stock_report(db, start, end, branch_id),
            "branch_options": [{"id": b.branch_id, "name": b.name} for b in branches.values()],
            "notes": []}


# ---------- pending customers ----------
KINDS = {"PAYMENT": "Payment pending", "INSURANCE": "Insurance pending", "RTO": "RTO pending",
         "INVOICE": "Invoice pending", "DELIVERY": "Delivery pending", "CANCELLED": "Cancelled bookings"}


def pending_list(db: Session, kind: str, branch_id=None):
    names = {u.user_id: u.full_name for u in db.query(AppUser).all()}
    bnames = {b.branch_id: b.name for b in db.query(Branch).all()}
    rows = []
    if kind == "CANCELLED":
        q = db.query(Lead, Booking).join(Booking, Booking.lead_id == Lead.lead_id).filter(~sold_condition(db), Lead.enquiry_stage == S.CLOSED)
        if branch_id: q = q.filter(Lead.branch_id == branch_id)
        paid = dict(db.query(Payment.booking_id, func.sum(Payment.amount)).group_by(Payment.booking_id).all())
        for l, bk in q.all():
            rows.append(_row(l, names, bnames, f"Cancelled · Rs {round(float(paid.get(bk.booking_id) or 0)):,} received"))
        return rows
    for r in sales_snapshot(db, branch_id):
        l, active = r["lead"], r["stage"] in ACTIVE
        if kind == "PAYMENT" and r["pay_status"] != "PAID" and (r["outstanding"] or 0) > 0:
            d = f"Outstanding Rs {round(float(r['outstanding'])):,}"
        elif kind == "INSURANCE" and active and r["insurance"] != "COMPLETED":
            d = "Insurance " + r["insurance"].replace("_", " ").lower()
        elif kind == "RTO" and active and r["rto"] != "REGISTERED":
            d = "RTO " + r["rto"].replace("_", " ").lower()
        elif kind == "INVOICE" and active and r["stage"] != S.INVOICED:
            d = "Not invoiced yet"
        elif kind == "DELIVERY" and active:
            d = "Invoiced, awaiting delivery" if r["stage"] == S.INVOICED else "Booked, awaiting delivery"
        else:
            continue
        rows.append(_row(l, names, bnames, d, r["booking"].created_at))
    return rows


def _row(l, names, bnames, detail, since=None):
    return {"lead_id": l.lead_id, "enquiry_no": l.enquiry_no, "customer": l.customer.full_name, "phone": l.customer.phone,
            "branch": bnames.get(l.branch_id), "pba": names.get(l.assigned_user_id), "stage": l.enquiry_stage.value,
            "detail": detail, "since": since}


# ---------- stock report ----------
def stock_report(db: Session, start: date, end: date, branch_id=None):
    """Closing stock now + what moved in the window, per item."""
    s, e = _dt(start), _dt(end)
    items = {i.id: i for i in db.query(StockItem).filter(StockItem.is_active == True).all()}  # noqa: E712
    bal, _, _ = stock_svc.balances(db)
    mv = defaultdict(lambda: defaultdict(int))
    for m in db.query(StockMovement).filter(StockMovement.created_at >= s, StockMovement.created_at < e).all():
        if branch_id and branch_id not in (m.from_branch_id, m.to_branch_id) and m.move_type != "RECEIVE":
            continue
        x = mv[m.item_id]
        if m.move_type in ("RECEIVE", "RECEIPT"): x["received"] += m.qty
        elif m.move_type == "ALLOCATE": x["allocated"] += m.qty
        elif m.move_type == "TRANSFER": x["transferred"] += m.qty
        elif m.move_type == "ISSUE": x["issued"] += m.qty
        elif m.move_type == "COUNT": x["count_diff"] += m.qty
    rows = []
    for iid, it in sorted(items.items(), key=lambda kv: (kv[1].kind, kv[1].name)):
        b = bal.get(iid, {})
        closing = b.get(branch_id, 0) if branch_id else sum(b.values())
        x = mv.get(iid, {})
        rows.append({**stock_svc.item_dict(it), "closing": closing, "warehouse": 0 if branch_id else b.get(None, 0),
                     "received": x.get("received", 0), "allocated": x.get("allocated", 0), "transferred": x.get("transferred", 0),
                     "issued": x.get("issued", 0), "count_diff": x.get("count_diff", 0)})
    kinds = {}
    for r in rows:
        k = kinds.setdefault(r["kind"], {"closing": 0, "received": 0, "issued": 0})
        k["closing"] += r["closing"]; k["received"] += r["received"]; k["issued"] += r["issued"]
    return {"items": rows, "kinds": kinds, "out_of_stock": [r["label"] for r in rows if r["closing"] <= 0]}
