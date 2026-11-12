"""CRE-wise reports.

Leads are not assigned to a CRE: a CRE covers 1-2 branches. So each CRE row mixes two things, shown separately:
  WORKLOAD  (from the CRE's branches): leads, follow-ups pending/overdue, test rides, bookings, lost, showroom visits
  ACTIVITY  (by the CRE personally):   calls logged, customers contacted, quotations created, review links sent
Two CREs sharing a branch therefore share that branch's workload but not each other's activity.
"""
from collections import defaultdict
from datetime import date, datetime, time, timedelta

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.modules.leads.models import (Disposition, EnquiryStage as S, Lead, LeadFollowup, LeadSource,
                                      OpportunityStatus, TestRide, TestRideStatus)
from app.modules.leads.stages import cancelled_booking_condition, delivered_condition, sold_condition
from app.modules.quotations.models import Quotation, QuotationStatus
from app.modules.users.models import AppUser, Branch, Role
from app.modules.whatsapp.models import WhatsappMessage


def _pct(a, b):
    return round(a * 100 / b, 1) if b else 0


def window(date_from, date_to):
    today = date.today()
    if not date_from:
        date_from = today.replace(day=1)
    if not date_to:
        date_to = today
    return datetime.combine(date_from, time.min), datetime.combine(date_to + timedelta(days=1), time.min), date_from, date_to


def cres(db: Session, only_id=None):
    q = db.query(AppUser).filter(AppUser.role == Role.CRE, AppUser.is_active.is_(True))
    if only_id:
        q = q.filter(AppUser.user_id == only_id)
    return q.order_by(AppUser.full_name).all()


def lead_query(db, branch_ids, start, end, f):
    """Leads of those branches enquired in the window, with the optional filters."""
    q = db.query(Lead).filter(Lead.branch_id.in_(branch_ids or [-1]), Lead.enquiry_at >= start, Lead.enquiry_at < end)
    if f.get("source"):
        q = q.filter(Lead.source == LeadSource(f["source"]))
    if f.get("opportunity_status_id"):
        q = q.filter(Lead.opportunity_status_id == f["opportunity_status_id"])
    if f.get("disposition_id"):
        q = q.filter(Lead.current_disposition_id == f["disposition_id"])
    return q


def _ids(q):
    return {r[0] for r in q.with_entities(Lead.lead_id).all()}


def scope_stats(db, branch_ids, start, end, f) -> dict:
    """Workload + funnel numbers for the leads of some branches."""
    base = lead_query(db, branch_ids, start, end, f)
    ids = _ids(base)
    now = datetime.now()
    out = {"total": len(ids)}
    if not ids:
        return {**{k: 0 for k in ("total", "contacted", "qualified", "tr_booked", "tr_completed", "tr_rescheduled", "quotations", "booked",
                                  "delivered", "pending", "due_today", "overdue", "showroom", "lost", "tr_scheduled")}}
    idl = list(ids)
    contacted = _ids(base.filter(Lead.first_contact_at.isnot(None)))
    tr = db.query(TestRide.lead_id, TestRide.status).filter(TestRide.lead_id.in_(idl)).all()
    tr_leads = {l for l, s in tr}
    tr_done = {l for l, s in tr if s == TestRideStatus.COMPLETED}
    quo = {r[0] for r in db.query(Quotation.lead_id).filter(Quotation.lead_id.in_(idl), Quotation.status != QuotationStatus.DRAFT).all()}
    booked = _ids(base.filter(sold_condition(db)))
    delivered = _ids(base.filter(delivered_condition(db)))
    interest = _ids(base.filter(or_(Lead.showroom_visit.in_(("YES", "PLANNED")), Lead.test_ride_interest.in_(("YES", "PLANNED")))))
    qualified = (contacted & (interest | tr_leads | quo)) | (contacted & booked)
    open_ = base.filter(Lead.enquiry_stage == S.OPEN, Lead.next_followup_at.isnot(None))
    eod = datetime.combine(date.today() + timedelta(days=1), time.min)
    overdue = open_.filter(Lead.next_followup_at < now).count()
    due_today = open_.filter(Lead.next_followup_at >= datetime.combine(date.today(), time.min), Lead.next_followup_at < eod).count()
    pending = open_.filter(Lead.next_followup_at >= now).count() + overdue
    lost = base.filter(Lead.enquiry_stage == S.CLOSED, ~sold_condition(db), ~cancelled_booking_condition(db)).count()
    showroom = base.filter(Lead.showroom_visit == "YES").count()
    out.update(contacted=len(contacted), qualified=len(qualified), tr_booked=len(tr_leads), tr_completed=len(tr_done),
               tr_scheduled=len(tr), tr_rescheduled=sum(1 for l, s in tr if s == TestRideStatus.RESCHEDULED),
               quotations=len(quo), booked=len(booked), delivered=len(delivered), pending=pending, due_today=due_today,
               overdue=overdue, showroom=showroom, lost=lost)
    return out


def activity(db, user_id, start, end) -> dict:
    fu = db.query(LeadFollowup).filter(LeadFollowup.user_id == user_id, LeadFollowup.created_at >= start, LeadFollowup.created_at < end).all()
    contacted = [x for x in fu if x.contacted]
    q = db.query(func.count(Quotation.quotation_id)).filter(Quotation.created_by_user_id == user_id,
                                                           Quotation.created_at >= start, Quotation.created_at < end)
    wa = db.query(WhatsappMessage.status).filter(WhatsappMessage.kind == "REVIEW", WhatsappMessage.created_by_user_id == user_id,
                                                WhatsappMessage.created_at >= start, WhatsappMessage.created_at < end).all()
    return {"calls": len(fu), "calls_connected": len(contacted), "customers_contacted": len({x.lead_id for x in contacted}),
            "quotations_created": q.scalar() or 0, "quotations_shared": q.filter(Quotation.status != QuotationStatus.DRAFT).scalar() or 0,
            "review_sent": len(wa), "review_failed": sum(1 for (s,) in wa if s == "FAILED")}


def report(db: Session, date_from, date_to, cre_id=None, branch_id=None, f=None, only_id=None):
    f = f or {}
    start, end, d1, d2 = window(date_from, date_to)
    allowed = cres(db, only_id)
    if cre_id:
        allowed = [c for c in allowed if c.user_id == cre_id]
    bnames = {b.branch_id: b.name for b in db.query(Branch).all()}
    rows = []
    union = set()
    for c in allowed:
        bids = [b for b in c.branch_ids if not branch_id or b == branch_id]
        union |= set(bids)
        st = scope_stats(db, bids, start, end, f)
        ac = activity(db, c.user_id, start, end)
        from app.modules.final_review.models import FinalReview
        fr_done = db.query(func.count(FinalReview.id)).filter(FinalReview.reviewed_by_user_id == c.user_id, FinalReview.status == "COMPLETED",
                                                              FinalReview.closed_at >= start, FinalReview.closed_at < end).scalar() or 0
        fr_pending = db.query(func.count(Lead.lead_id)).filter(Lead.branch_id.in_(bids or [-1]), Lead.enquiry_stage == S.DELIVERED).scalar() or 0
        ac.update(final_done=fr_done, final_pending=fr_pending)
        done = ac["calls_connected"]
        rows.append({"cre_id": c.user_id, "name": c.full_name, "branches": [bnames.get(b, "?") for b in bids], **st, **ac,
                     "conversion_pct": _pct(st["booked"], st["total"]),
                     "followup_completion_pct": _pct(done, done + st["pending"]),
                     "tr_completion_pct": _pct(st["tr_completed"], st["tr_scheduled"])})
    total = scope_stats(db, list(union), start, end, f)
    base = lead_query(db, list(union), start, end, f)
    # opportunity status + disposition distribution (leads in scope)
    opp = [{"name": n or "Not set", "count": c} for n, c in
           base.outerjoin(OpportunityStatus, OpportunityStatus.id == Lead.opportunity_status_id)
           .with_entities(OpportunityStatus.name, func.count(Lead.lead_id)).group_by(OpportunityStatus.name).all()]
    opp.sort(key=lambda x: -x["count"])
    disp = [{"name": n or "Not set", "count": c} for n, c in
            base.outerjoin(Disposition, Disposition.id == Lead.current_disposition_id)
            .with_entities(Disposition.name, func.count(Lead.lead_id)).group_by(Disposition.name).all()]
    disp.sort(key=lambda x: -x["count"])
    funnel = [{"label": l, "count": total[k]} for l, k in
              (("Total assigned leads", "total"), ("Contacted", "contacted"), ("Qualified", "qualified"), ("Test ride booked", "tr_booked"),
               ("Test ride completed", "tr_completed"), ("Quotation shared", "quotations"), ("Booking done", "booked"), ("Bike delivered", "delivered"))]
    cre_ids = [c.user_id for c in allowed]
    # follow-up trend (calls logged per day) by these CREs
    trend = defaultdict(int)
    for (ts,) in db.query(LeadFollowup.created_at).filter(LeadFollowup.user_id.in_(cre_ids or [-1]), LeadFollowup.created_at >= start, LeadFollowup.created_at < end).all():
        trend[ts.date().isoformat()] += 1
    return {"from": d1, "to": d2, "rows": rows, "total": total, "funnel": funnel, "opportunity": opp, "disposition": disp,
            "trend": [{"date": k, "count": v} for k, v in sorted(trend.items())],
            "review": review_report(db, cre_ids, start, end),
            "options": {"cres": [{"id": c.user_id, "name": c.full_name} for c in cres(db, only_id)],
                        "branches": [{"id": k, "name": v} for k, v in bnames.items()],
                        "opportunity": [{"id": o.id, "name": o.name} for o in db.query(OpportunityStatus).order_by(OpportunityStatus.name).all()],
                        "dispositions": [{"id": o.id, "name": o.name} for o in db.query(Disposition).order_by(Disposition.name).all()]}}


def review_report(db, cre_ids, start, end):
    q = db.query(WhatsappMessage).filter(WhatsappMessage.kind == "REVIEW", WhatsappMessage.created_at >= start, WhatsappMessage.created_at < end,
                                         WhatsappMessage.created_by_user_id.in_(cre_ids or [-1]))
    msgs = q.all()
    names = {u.user_id: u.full_name for u in db.query(AppUser).filter(AppUser.user_id.in_(cre_ids or [-1])).all()}
    bn = {b.branch_id: b.name for b in db.query(Branch).all()}
    by_cre, by_branch, by_day = defaultdict(int), defaultdict(int), defaultdict(int)
    for m in msgs:
        by_cre[names.get(m.created_by_user_id, "?")] += 1
        by_branch[bn.get(m.branch_id, "—")] += 1
        by_day[m.created_at.date().isoformat()] += 1
    mk = lambda d: [{"name": k, "count": v} for k, v in sorted(d.items(), key=lambda x: (-x[1], x[0]))]
    return {"total": len(msgs), "delivered": sum(1 for m in msgs if m.status in ("DELIVERED", "READ")), "failed": sum(1 for m in msgs if m.status == "FAILED"),
            "by_cre": mk(by_cre), "by_branch": mk(by_branch), "by_day": [{"date": k, "count": v} for k, v in sorted(by_day.items())]}


KINDS = {"overdue": "Overdue follow-ups", "pending": "Pending follow-ups", "due_today": "Today's follow-ups", "tr_scheduled": "Test rides scheduled",
         "tr_completed": "Test rides completed", "showroom": "Showroom visits", "lost": "Lost leads", "booked": "Bookings", "all": "All leads"}


def lead_list(db, kind, branch_ids, start, end, f, limit=500):
    base = lead_query(db, branch_ids, start, end, f)
    now = datetime.now()
    if kind in ("overdue", "pending", "due_today"):
        base = base.filter(Lead.enquiry_stage == S.OPEN, Lead.next_followup_at.isnot(None))
        if kind == "overdue": base = base.filter(Lead.next_followup_at < now)
        else:
            d0 = datetime.combine(date.today(), time.min)
            base = base.filter(Lead.next_followup_at >= d0, Lead.next_followup_at < d0 + timedelta(days=1))
    elif kind in ("tr_scheduled", "tr_completed"):
        sub = db.query(TestRide.lead_id)
        if kind == "tr_completed": sub = sub.filter(TestRide.status == TestRideStatus.COMPLETED)
        base = base.filter(Lead.lead_id.in_(sub))
    elif kind == "showroom": base = base.filter(Lead.showroom_visit == "YES")
    elif kind == "lost": base = base.filter(Lead.enquiry_stage == S.CLOSED, ~sold_condition(db), ~cancelled_booking_condition(db))
    elif kind == "booked": base = base.filter(sold_condition(db))
    names = {u.user_id: u.full_name for u in db.query(AppUser).all()}
    bn = {b.branch_id: b.name for b in db.query(Branch).all()}
    return [{"lead_id": l.lead_id, "enquiry_no": l.enquiry_no, "customer": l.customer.full_name, "mobile": l.customer.phone,
             "branch": bn.get(l.branch_id), "pba": names.get(l.assigned_user_id), "stage": l.enquiry_stage.value,
             "opportunity": l.opportunity.name if l.opportunity else None, "disposition": l.current_disposition.name if l.current_disposition else None,
             "next_followup_at": l.next_followup_at, "enquiry_at": l.enquiry_at}
            for l in base.order_by(Lead.next_followup_at.asc().nullslast(), Lead.lead_id.desc()).limit(limit).all()]
