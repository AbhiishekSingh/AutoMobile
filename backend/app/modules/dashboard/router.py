"""dashboard/router.py — Chart data endpoints for the PBA dashboard."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import period_range
from app.core.deps import get_current_user, get_db, require_roles
from app.modules.leads.models import (BikeModel, EnquiryStage, Lead,
                                      LeadSource, LostReason, SLAFlag)
from app.modules.quotations.models import Quotation, QuotationStatus
from app.modules.users.models import AppUser, Role
from app.modules.leads.service import scope

router = APIRouter(tags=["dashboard"])

READ_ROLES = ("PBA", "SALES_MANAGER", "GM", "OWNER", "ADMIN")


@router.get("/dashboard/charts", dependencies=[Depends(require_roles(*READ_ROLES))])
def charts(
    period: str = Query("today", enum=["today", "week", "month", "year"]),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns data for:
      1. target_tracker   — grouped bar chart (model-wise target vs achieved)
      2. total_sales      — donut chart (achieved / to_be_achieved / cancelled)
      3. sla_compliance    — donut chart (GREEN / YELLOW / RED follow-up SLA)
      4. lead_source       — donut chart (CSV import vs WALKIN)
      5. lost_reasons      — horizontal bar (top reasons for CLOSED leads)
      6. quotation_funnel  — bar chart (DRAFT/SHARED/ACCEPTED/EXPIRED/REJECTED)

    All six are filtered by `period` ("today" | "week" | "month" | "year"),
    applied to Lead.enquiry_at for lead-based charts and Quotation.created_at
    for the quotation funnel — see `period_range()` in app/core/database.py
    for the exact calendar boundaries used.
    """
    period_start, period_end = period_range(period)

    # ── 1. Target Tracker (model-wise) ──────────────────────────────────────
    # "Achieved" = BOOKED or INVOICED stage
    # "Target"   = all leads for that model in the period — acts as target pool
    achieved_stages = [EnquiryStage.BOOKED, EnquiryStage.INVOICED]

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
    base_q = scope(base_q, user).group_by(BikeModel.name)

    # Total leads per model (target)
    target_rows = {name: cnt for name, cnt in base_q.all()}

    # Achieved leads per model
    achieved_q = (
        db.query(BikeModel.name, func.count(Lead.lead_id))
        .join(Lead, Lead.model_id == BikeModel.id, isouter=True)
        .filter(Lead.enquiry_stage.in_(achieved_stages))
        .filter(Lead.enquiry_at >= period_start, Lead.enquiry_at < period_end)
    )
    achieved_rows = {
        name: cnt
        for name, cnt in scope(achieved_q, user).group_by(BikeModel.name).all()
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

    # ── 2. Total Sales of Vehicles ───────────────────────────────────────────
    # Achieved  = BOOKED + INVOICED
    # To Be     = OPEN + QUOTED
    # Cancelled = CLOSED
    stage_map = {
        EnquiryStage.BOOKED:   "achieved",
        EnquiryStage.INVOICED: "achieved",
        EnquiryStage.OPEN:     "to_be_achieved",
        EnquiryStage.QUOTED:   "to_be_achieved",
        EnquiryStage.CLOSED:   "cancelled",
    }

    stage_counts = dict(
        scope(db.query(Lead.enquiry_stage, func.count(Lead.lead_id)), user)
        .filter(Lead.enquiry_at >= period_start, Lead.enquiry_at < period_end)
        .group_by(Lead.enquiry_stage)
        .all()
    )

    totals = {"achieved": 0, "to_be_achieved": 0, "cancelled": 0}
    for stage, bucket in stage_map.items():
        totals[bucket] += stage_counts.get(stage, 0)

    # ── 3. SLA Compliance (follow-up responsiveness) ────────────────────────
    # GREEN  = contacted <= 3h, YELLOW = pending 3-24h, RED = overdue > 24h
    sla_counts = dict(
        scope(db.query(Lead.sla_flag, func.count(Lead.lead_id)), user)
        .filter(Lead.enquiry_at >= period_start, Lead.enquiry_at < period_end)
        .group_by(Lead.sla_flag)
        .all()
    )
    sla_compliance = {
        "green": sla_counts.get(SLAFlag.GREEN, 0),
        "yellow": sla_counts.get(SLAFlag.YELLOW, 0),
        "red": sla_counts.get(SLAFlag.RED, 0),
    }

    # ── 4. Lead Source Split (CSV import vs Walk-in) ─────────────────────────
    source_counts = dict(
        scope(db.query(Lead.source, func.count(Lead.lead_id)), user)
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
        scope(lost_q, user)
        .group_by(LostReason.name)
        .order_by(func.count(Lead.lead_id).desc())
        .limit(8)
        .all()
    )
    lost_reasons = [{"reason": name, "count": cnt} for name, cnt in lost_rows]

    # ── 6. Quotation Funnel (DRAFT → SHARED → ACCEPTED / EXPIRED / REJECTED) ─
    quot_q = (
        db.query(Quotation.status, func.count(Quotation.quotation_id))
        .filter(Quotation.created_at >= period_start, Quotation.created_at < period_end)
    )
    if user.role == Role.PBA and user.branch_id:
        quot_q = quot_q.filter(Quotation.branch_id == user.branch_id)
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