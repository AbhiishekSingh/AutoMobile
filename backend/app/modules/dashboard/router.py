"""dashboard/router.py — Chart data endpoints for the PBA dashboard."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import period_range
from app.core.deps import get_current_user, get_db, require_roles
from app.modules.leads.models import (BikeModel, EnquiryStage, Lead,
                                      LeadSource, LostReason, SLAFlag)
from app.modules.quotations.models import Quotation, QuotationStatus
from app.modules.targets import service as tgt
from app.modules.users.models import AppUser, Role
from app.modules.leads.service import scope
from app.modules.leads.sla import sla_conditions
from app.modules.leads.stages import cancelled_booking_condition, sold_condition
from app.modules.users.access import MANAGER_ROLES, SALES_ROLES, dashboard_branch

router = APIRouter(tags=["dashboard"])

READ_ROLES = SALES_ROLES + MANAGER_ROLES


@router.get("/dashboard/charts", dependencies=[Depends(require_roles(*READ_ROLES))])
def charts(
    period: str = Query("today", enum=["today", "week", "month", "year"]),
    branch_id: int | None = None,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns data for:
      1. target_tracker   — grouped bar chart (model-wise target vs achieved)
      2. total_sales      — donut chart (achieved / to_be_achieved / cancelled)
      3. sla_compliance    — donut chart (GREEN on time / YELLOW pending / RED late or overdue)
      4. lead_source       — donut chart (CSV import vs WALKIN)
      5. lost_reasons      — horizontal bar (top reasons for CLOSED leads)
      6. quotation_funnel  — bar chart (DRAFT/SHARED/ACCEPTED/EXPIRED/REJECTED)

    All six are filtered by `period` ("today" | "week" | "month" | "year"),
    applied to Lead.enquiry_at for lead-based charts and Quotation.created_at
    for the quotation funnel — see `period_range()` in app/core/database.py
    for the exact calendar boundaries used.
    """
    period_start, period_end = period_range(period)
    # CRE: one branch at a time (defaults to their first) — same rule as /pba/dashboard
    branch_id = dashboard_branch(user, branch_id)

    # ── 1. Target Tracker (model-wise) ──────────────────────────────────────
    # "Achieved" = BOOKED or INVOICED stage
    # "Target"   = all leads for that model in the period — acts as target pool
    # (achieved = booked or later, incl. delivered-then-closed: sold_condition)

    # NOTE: join Lead to BikeModel FIRST, then apply scope()/filters — see
    # the comment on the Lost Reasons query below for why ordering matters
    # here (this pattern silently mis-scopes for PBA users if the join comes
    # after scope()'s branch filter).
    base_q = (
        db.query(BikeModel.name, func.count(Lead.lead_id))
        .join(Lead, Lead.model_id == BikeModel.id, isouter=True)
        .filter((Lead.lead_id.is_(None)) |
                ((Lead.enquiry_at >= period_start) & (Lead.enquiry_at < period_end)))
    )
    base_q = scope(base_q, user, branch_id).group_by(BikeModel.name)

    # Total leads per model (target)
    target_rows = {name: cnt for name, cnt in base_q.all()}

    # Achieved leads per model
    achieved_q = (
        db.query(BikeModel.name, func.count(Lead.lead_id))
        .join(Lead, Lead.model_id == BikeModel.id, isouter=True)
        .filter(sold_condition(db))
        .filter(Lead.enquiry_at >= period_start, Lead.enquiry_at < period_end)
    )
    achieved_rows = {
        name: cnt
        for name, cnt in scope(achieved_q, user, branch_id).group_by(BikeModel.name).all()
    }

    # Only include models that have at least one lead in the period
    target_tracker = []
    for model_name, target in target_rows.items():
        if target == 0:
            continue
        achieved = achieved_rows.get(model_name, 0)
        pct = round((achieved / target) * 100) if target else 0
        target_tracker.append({
            "model": model_name,
            "target": target,
            "achieved": achieved,
            "achievement_pct": pct,
        })

    # Sort by target desc for a nicer chart
    target_tracker.sort(key=lambda x: x["target"], reverse=True)

    # Real targets (set by Owner/GM) replace the stand-in when they exist for a month/year view
    real = tgt.period_targets(db, user, branch_id, period, period_start, period_end)
    if real:
        got = tgt.booked_by_model(db, user, branch_id, period_start, period_end)
        target_tracker = []
        for name in sorted(set(real) | set(got)):
            t, a = real.get(name, 0), got.get(name, 0)
            target_tracker.append({"model": name, "target": t, "achieved": a,
                                   "achievement_pct": round(a * 100 / t) if t else 0})
        target_tracker.sort(key=lambda x: x["target"], reverse=True)

    # ── 2. Total Sales of Vehicles ───────────────────────────────────────────
    # Achieved  = booked or any later stage (incl. delivered-then-closed)
    # To Be     = still OPEN
    # Cancelled = a booking that was cancelled (closed after booking, not
    #             delivered). Closed enquiries that never booked are lost
    #             leads (see "Lost Reasons" below) — not cancelled sales.
    def sales_count(condition):
        return (scope(db.query(func.count(Lead.lead_id)), user, branch_id)
                .filter(Lead.enquiry_at >= period_start, Lead.enquiry_at < period_end)
                .filter(condition).scalar() or 0)

    totals = {"achieved": sales_count(sold_condition(db)),
              "to_be_achieved": sales_count(Lead.enquiry_stage == EnquiryStage.OPEN),
              "cancelled": sales_count(cancelled_booking_condition(db))}

    # ── 3. SLA Compliance (follow-up responsiveness) ────────────────────────
    # GREEN  = contacted <= 3h, YELLOW = pending 3-24h, RED = overdue > 24h
    # Worked out from the clock (leads/sla.py): green = contacted within 3h;
    # yellow = not contacted yet (still in time, or 3-24h); red = contacted
    # late OR not contacted after 24h.
    sla_cond = sla_conditions()

    def sla_count(key):
        return (scope(db.query(func.count(Lead.lead_id)), user, branch_id)
                .filter(Lead.enquiry_at >= period_start, Lead.enquiry_at < period_end)
                .filter(sla_cond[key]).scalar() or 0)

    sla_compliance = {"green": sla_count("GREEN"), "yellow": sla_count("YELLOW"),
                      "red": sla_count("RED")}

    # ── 4. Lead Source Split (CSV import vs Walk-in) ─────────────────────────
    source_counts = dict(
        scope(db.query(Lead.source, func.count(Lead.lead_id)), user, branch_id)
        .filter(Lead.enquiry_at >= period_start, Lead.enquiry_at < period_end)
        .group_by(Lead.source)
        .all()
    )
    lead_source = {
        "csv": source_counts.get(LeadSource.CSV, 0),
        "walkin": source_counts.get(LeadSource.WALKIN, 0),
    }

    # ── 5. Lost Reasons (why CLOSED leads were lost) ─────────────────────────
    # NOTE: join Lead to LostReason FIRST, then apply scope()/filters.
    # scope() adds a `Lead.branch_id == ...` filter for PBA users — if that
    # filter is applied before Lead is joined, Lead.lead_id (already
    # referenced in the SELECT via func.count) gets implicitly pulled into
    # the query as a second, unjoined table, producing an ambiguous/duplicate
    # FROM entry once .join(Lead, ...) runs afterward. This only manifests
    # when scope() actually adds a filter, i.e. only for PBA — never for
    # admin/owner, where scope() is a no-op. Joining first avoids it entirely.
    lost_q = (
        db.query(LostReason.name, func.count(Lead.lead_id))
        .join(Lead, Lead.lost_reason_id == LostReason.id)
        .filter(Lead.enquiry_stage == EnquiryStage.CLOSED)
        .filter(Lead.enquiry_at >= period_start, Lead.enquiry_at < period_end)
    )
    lost_rows = (
        scope(lost_q, user, branch_id)
        .group_by(LostReason.name)
        .order_by(func.count(Lead.lead_id).desc())
        .limit(8)
        .all()
    )
    lost_reasons = [{"reason": name, "count": cnt} for name, cnt in lost_rows]

    # ── 6. Quotation Funnel (DRAFT → SHARED → ACCEPTED / EXPIRED / REJECTED) ─
    # Counted on the quotation's LEAD, so it follows the same visibility rule
    # as everything else (PBA: their leads; CRE: the chosen branch).
    quot_q = (
        db.query(Quotation.status, func.count(Quotation.quotation_id))
        .join(Lead, Quotation.lead_id == Lead.lead_id)
        .filter(Quotation.created_at >= period_start, Quotation.created_at < period_end)
    )
    quot_q = scope(quot_q, user, branch_id)
    quot_counts = dict(quot_q.group_by(Quotation.status).all())
    quotation_funnel = [
        {"status": s.value, "count": quot_counts.get(s, 0)}
        for s in QuotationStatus
    ]

    return {
        "target_tracker": target_tracker,
        "total_sales": totals,
        "sla_compliance": sla_compliance,
        "lead_source": lead_source,
        "lost_reasons": lost_reasons,
        "quotation_funnel": quotation_funnel,
    }
