from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db, now_ist, period_range
from app.core.deps import get_current_user, require_roles
from app.modules.leads.models import (BikeModel, Customer, Disposition,
                                      EnquiryMode, Lead, LeadFollowup, LeadType,
                                      LeadSource, LostReason, OpportunityStatus,
                                      SLAFlag, StageHistory, TestRide, TestRideStatus,
                                      EnquiryStage, LeadModelInterest)
from app.modules.handoffs.service import ensure_insurance_case, is_booking_done
from app.modules.leads.callbacks import (CHOICES, missing_call_details, needs_call_details,
                                         update_callback_reminder)
from app.modules.leads.schemas import (CustomerListResponse, CustomerLookup,
                                       FollowupCreate,
                                       FollowupListResponse, LeadCreate,
                                       LeadDetail, LeadListResponse, LeadUpdate, ModelInterestIn,
                                       Lookups, PBADashboard, TestRideAction,
                                       TestRideCreate)
from app.modules.audit.service import record_changes
from app.modules.leads.lookup_names import lookup_key
from app.modules.leads.sla import ageing_days, lead_sla
from app.modules.leads.stages import (change_stage, delivered_condition,
                                      invoiced_condition, open_booking_condition,
                                      sold_condition, stage_label)
from app.modules.leads.test_rides import create_test_ride, update_test_ride
from app.modules.leads.service import (bucket_filter, check_followup_date,
                                       dropdown_options, find_customer_by_phone,
                                       is_allowed, mask_phone, normalize_phone, scope)
from app.modules.notifications.models import NotificationType
from app.modules.notifications.service import create_notification
from app.modules.quotations.models import Quotation, QuotationStatus
from app.modules.users.access import (MANAGER_ROLES, SALES_ROLES,
                                      check_branch_access, dashboard_branch,
                                      get_visible_lead, is_cre)
from app.modules.users.models import AppUser, Branch, Role
from app.modules.whatsapp import service as wa

router = APIRouter(tags=["pba"])
READ_ROLES = SALES_ROLES + MANAGER_ROLES      # PBA, CRE, Owner, GM, Admin
# Screens with a branch filter take `?branch_id=` — CRE picks one of their
# branches; leaving it out shows all the branches they can see.

# Enquiry-mode tiles shown first on the Leads screen (after "Total Leads").
# Add more names here to pin them too, e.g. ["Walk-in", "Digital"].
TILE_PIN_FIRST = ["Walk-in"]


@router.get("/lookups", response_model=Lookups,
            dependencies=[Depends(require_roles(*READ_ROLES))])
def lookups(db: Session = Depends(get_db)):
    q = lambda M: db.query(M).order_by(M.id).all()  # noqa: E731
    # Opportunity status + disposition: only the values in their fixed lists
    # (leads/service.py), in list order. Old/imported values stay in the DB
    # for history but are never offered here.
    return Lookups(enquiry_modes=q(EnquiryMode),
                   opportunity_statuses=dropdown_options(db, OpportunityStatus),
                   dispositions=dropdown_options(db, Disposition),
                   lost_reasons=q(LostReason), models=q(BikeModel))


def _require_listed(db: Session, Model, value_id: int | None, label: str) -> None:
    """Reject a value that isn't in the dropdown's fixed list — so the rule
    holds even if someone calls the API directly, not just via the UI."""
    if value_id is None:
        return
    row = db.get(Model, value_id)
    if not row or not row.is_active or not is_allowed(Model, row.name):
        raise HTTPException(400, f"Please choose a {label} from the list")


@router.get("/leads/tiles", dependencies=[Depends(require_roles(*READ_ROLES))])
def tiles(branch_id: int | None = None, user: AppUser = Depends(get_current_user),
          db: Session = Depends(get_db)):
    base = scope(db.query(Lead.mode_id, func.count(Lead.lead_id)), user,
                 branch_id).group_by(Lead.mode_id)
    counts = {mid: c for mid, c in base.all()}
    modes = db.query(EnquiryMode).order_by(EnquiryMode.id).all()
    # Tiles pinned to the front, in this order, right after "Total Leads".
    # Every other mode follows in its normal (id) order. Matching uses
    # lookup_key, so "Walk-In" / "Walk-in" / "WALK IN" all count.
    pinned = [lookup_key(n) for n in TILE_PIN_FIRST]
    modes.sort(key=lambda m: pinned.index(lookup_key(m.name))
               if lookup_key(m.name) in pinned else len(pinned))
    out = [{"key": "total", "label": "Total Leads", "count": sum(counts.values())}]
    for m in modes:
        out.append({"key": m.name, "label": m.name, "count": counts.get(m.id, 0)})
    return out


@router.get("/leads/pipeline", dependencies=[Depends(require_roles(*READ_ROLES))])
def pipeline(branch_id: int | None = None, user: AppUser = Depends(get_current_user),
             db: Session = Depends(get_db)):
    buckets = [("all", "All Leads"), ("completed", "Completed"), ("pending", "Pending"),
               ("overdue", "Overdue"), ("calllater", "Call Later"), ("testride", "Test Ride"),
               ("casual", "Casual Enquiry"), ("future", "Future Lead"),
               ("service", "Service / Spare Part"), ("unassigned", "Unassigned"), ("closed", "Closed")]
    out = []
    for key, label in buckets:
        q = bucket_filter(scope(db.query(func.count(Lead.lead_id)), user, branch_id), key, db)
        out.append({"key": key, "label": label, "count": q.scalar() or 0})
    return out


@router.get("/leads", response_model=LeadListResponse,
            dependencies=[Depends(require_roles(*READ_ROLES))])
def list_leads(user: AppUser = Depends(get_current_user), db: Session = Depends(get_db),
               mode: str | None = None, bucket: str = "all", search: str | None = None,
               page: int = 1, page_size: int = 10, branch_id: int | None = None,
               whole_branch: bool = False):
    q = scope(db.query(Lead).join(Customer), user, branch_id, whole_branch)
    if mode and mode != "total":
        m = db.query(EnquiryMode).filter(EnquiryMode.name == mode).first()
        q = q.filter(Lead.mode_id == (m.id if m else -1))
    q = bucket_filter(q, bucket, db)
    if search:
        like = f"%{search}%"
        q = q.filter((Customer.full_name.ilike(like)) | (Customer.phone.ilike(like)) |
                     (Lead.enquiry_no.ilike(like)))
    total = q.count()
    rows = q.order_by(Lead.enquiry_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    pba_names = {u.user_id: u.full_name for u in db.query(AppUser).filter(AppUser.user_id.in_({l.assigned_user_id for l in rows if l.assigned_user_id} or {-1})).all()}
    return LeadListResponse(total=total, page=page, page_size=page_size, rows=[dict(
        lead_id=l.lead_id, enquiry_no=l.enquiry_no, enquiry_at=l.enquiry_at,
        enquiry_mode=l.mode.name if l.mode else None, customer_name=l.customer.full_name,
        contact_masked=mask_phone(l.customer.phone), model_name=l.model.name if l.model else None,
        opportunity_status=l.opportunity.name if l.opportunity else None,
        disposition=l.current_disposition.name if l.current_disposition else None,
        sla_flag=lead_sla(l)[1], sla_state=lead_sla(l)[0],
        assigned_pba=pba_names.get(l.assigned_user_id),
        is_mine=(l.assigned_user_id in (None, user.user_id))) for l in rows])


@router.get("/leads/{lead_id}", response_model=LeadDetail,
            dependencies=[Depends(require_roles(*READ_ROLES))])
def lead_detail(lead_id: int, user: AppUser = Depends(get_current_user),
                db: Session = Depends(get_db)):
    # only a lead this user may see (PBA: own/unassigned in branch, CRE: their branches)
    l = get_visible_lead(db, user, lead_id)
    branch = db.get(Branch, l.branch_id) if l.branch_id else None
    sp = db.get(AppUser, l.assigned_user_id) if l.assigned_user_id else None
    within3 = None
    if l.first_contact_at and l.enquiry_at:
        within3 = (l.first_contact_at - l.enquiry_at) <= timedelta(hours=3)
    view_only = bool(user.via_branch and l.assigned_user_id not in (None, user.user_id))
    return LeadDetail(
        view_only=view_only, branch_id=l.branch_id, assigned_user_id=l.assigned_user_id,
        lead_id=l.lead_id, customer_id=l.customer_id,
        enquiry_no=l.enquiry_no, enquiry_date=l.enquiry_at,
        enquiry_time=l.enquiry_at.strftime("%H:%M") if l.enquiry_at else None,
        dealer_code=l.dealer_code, branch_code=l.branch_code,
        branch_name=branch.name if branch else None,
        salesperson_name=sp.full_name if sp else None, salesperson_email=l.salesperson_email,
        first_contact_at=l.first_contact_at, within_3hrs=within3,
        followup_enquiry_mode=l.mode.name if l.mode else None,
        customer_name=l.customer.full_name, mobile=(mask_phone(l.customer.phone) if view_only else l.customer.phone), pincode=l.customer.pincode,
        model_name=l.model.name if l.model else None, color=l.color, sku_code=l.sku_code,
        enquiry_stage=l.enquiry_stage.value if l.enquiry_stage else None,
        opportunity_status=l.opportunity.name if l.opportunity else None,
        disposition=l.current_disposition.name if l.current_disposition else None,
        lost_reason=l.lost_reason.name if l.lost_reason else None,
        next_followup_at=l.next_followup_at, ageing_days=ageing_days(l),
        mode_id=l.mode_id, model_id=l.model_id,
        opportunity_status_id=l.opportunity_status_id,
        disposition_id=l.current_disposition_id, lost_reason_id=l.lost_reason_id,
        followups=[dict(id=f.id, created_at=f.created_at, remark=f.remark,
                        disposition=f.disposition.name if f.disposition else None,
                        opportunity_status=f.opportunity.name if f.opportunity else None,
                        next_followup_at=f.next_followup_at,
                        by=f.user.full_name if f.user else None) for f in l.followups],
        test_rides=[dict(id=t.id, model_name=t.model.name if t.model else None, color=t.color,
                         status=t.status.value, scheduled_at=t.scheduled_at, slot=t.slot,
                         preferred_location=t.preferred_location, completed=t.completed)
                    for t in l.test_rides],
        # earlier versions of the customer's details, newest first
        previous_details=list(l.customer.previous_details),
        showroom_visit=l.showroom_visit, test_ride_interest=l.test_ride_interest,
        models=_interest_rows(db, l))


@router.get("/leads/{lead_id}/stage-history",
            dependencies=[Depends(require_roles(*READ_ROLES))])
def stage_history(lead_id: int, user: AppUser = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    """Every real stage change of this lead, newest first. Visible to whoever
    may see the lead (PBA, CRE, GM, Owner, Admin)."""
    get_visible_lead(db, user, lead_id)          # 404 if this user can't see the lead
    rows = (db.query(StageHistory).filter(StageHistory.lead_id == lead_id)
            .order_by(StageHistory.changed_at.desc(), StageHistory.id.desc()).all())
    return [dict(id=r.id,
                 from_stage=stage_label(r.from_stage) if r.from_stage else None,
                 to_stage=stage_label(r.to_stage),
                 changed_by=r.changed_by.full_name if r.changed_by else "System",
                 reason=r.reason, changed_at=r.changed_at) for r in rows]


@router.post("/leads", status_code=201, dependencies=[Depends(require_roles(*SALES_ROLES))])
def create_lead(body: LeadCreate, user: AppUser = Depends(get_current_user),
                db: Session = Depends(get_db)):
    """Add a walk-in lead.

    PBA: the lead goes to the PBA's own branch and is assigned to them.
    CRE: picks the branch (one of theirs) and, optionally, the PBA in that
         branch to assign it to — or leaves it unassigned in that branch.
    """
    if is_cre(user):
        if not body.branch_id:
            raise HTTPException(400, "Please choose the branch for this lead")
        check_branch_access(user, body.branch_id)
        branch = db.get(Branch, body.branch_id)
        if not branch:
            raise HTTPException(400, "Unknown branch")
        assignee = None
        if body.assigned_user_id:
            assignee = db.get(AppUser, body.assigned_user_id)
            if (not assignee or not assignee.is_active or assignee.role != Role.PBA
                    or assignee.branch_id != branch.branch_id):
                raise HTTPException(400, "Please choose an active PBA from this branch")
    else:
        branch, assignee = user.branch, user

    phone = normalize_phone(body.phone)
    if len(phone) < 10:
        raise HTTPException(400, "Please enter a valid 10-digit mobile number")

    # ---- returning customer: take over their latest enquiry, don't create a new one ----
    cust = find_customer_by_phone(db, phone)
    if cust:
        latest = (db.query(Lead).filter(Lead.customer_id == cust.customer_id)
                  .order_by(Lead.enquiry_at.desc(), Lead.lead_id.desc()).first())
        if latest:
            return _take_over_lead(db, latest, branch, assignee, actor=user)
        # (a customer with no lead at all is rare — falls through and gets a new enquiry)
    else:
        cust = Customer(phone=phone, full_name=body.full_name, alt_phone=body.alt_phone,
                        city=body.city, pincode=body.pincode)
        db.add(cust); db.flush()
    seq = (db.query(func.count(Lead.lead_id)).scalar() or 0) + 1
    lead = Lead(enquiry_no=f"ENQ{100000 + seq}", customer_id=cust.customer_id,
                branch_id=branch.branch_id if branch else None,
                assigned_user_id=assignee.user_id if assignee else None,
                mode_id=body.mode_id,
                model_id=(body.models[0].model_id if body.models else body.model_id),
                color=(body.models[0].color if body.models else body.color), lead_type=LeadType(body.lead_type),
                source=LeadSource(body.source), enquiry_at=now_ist(),
                # a walk-in is attended in person, so the first contact is now
                # (otherwise it would turn Overdue after 24h with nobody to call)
                first_contact_at=now_ist() if body.source == "WALKIN" else None,
                salesperson_email=assignee.email if assignee else None,
                # the branch's showroom code (the branch table's code column)
                branch_code=branch.dealer_code if branch else None)
    db.add(lead); db.flush()
    _save_model_interests(db, lead, body.models or
                          ([ModelInterestIn(model_id=body.model_id, color=body.color)] if body.model_id else []))
    # A PBA adding their own lead isn't notified (create_notification skips
    # self-notifying); a CRE assigning it to a PBA does notify that PBA.
    if assignee:
        create_notification(
            db, user_id=assignee.user_id, type_=NotificationType.LEAD_ASSIGNED,
            title="New lead assigned to you",
            message=f"Walk-in lead {lead.enquiry_no} ({cust.full_name}) "
                    f"has been assigned to you by {user.full_name}.",
            reference_type="lead", reference_id=lead.lead_id, actor_user_id=user.user_id)
    db.commit(); db.refresh(lead)
    if assignee:    # automatic welcome message to the customer (once per lead)
        wa.auto_send(db, "WELCOME", lead, user=user); db.commit()
    return {"lead_id": lead.lead_id, "enquiry_no": lead.enquiry_no, "existing": False}


def _save_model_interests(db: Session, lead: Lead, items: list) -> None:
    """Replace the lead's list of enquired models; the first one is the lead's main model."""
    seen, clean = set(), []
    for it in items:
        if not db.get(BikeModel, it.model_id):
            raise HTTPException(400, "Unknown bike model")
        key = (it.model_id, (it.color or "").strip().lower())
        if key in seen:
            continue
        seen.add(key); clean.append(it)
    if len(clean) > 6:
        raise HTTPException(400, "At most 6 models can be added to one enquiry")
    db.query(LeadModelInterest).filter(LeadModelInterest.lead_id == lead.lead_id).delete()
    for it in clean:
        db.add(LeadModelInterest(lead_id=lead.lead_id, model_id=it.model_id,
                                 color=(it.color or "").strip() or None))
    if clean:
        lead.model_id, lead.color = clean[0].model_id, (clean[0].color or "").strip() or None


def _interest_rows(db: Session, lead: Lead) -> list[dict]:
    rows = (db.query(LeadModelInterest).filter(LeadModelInterest.lead_id == lead.lead_id)
            .order_by(LeadModelInterest.id).all())
    if rows:
        return [dict(model_id=r.model_id, model_name=r.model.name if r.model else None, color=r.color)
                for r in rows]
    if lead.model_id:      # older leads: just the one model kept on the lead itself
        return [dict(model_id=lead.model_id, model_name=lead.model.name if lead.model else None,
                     color=lead.color)]
    return []


@router.put("/leads/{lead_id}/models", dependencies=[Depends(require_roles(*SALES_ROLES))])
def set_lead_models(lead_id: int, body: list[ModelInterestIn],
                    user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """Replace the list of models this customer is interested in (first = main model)."""
    lead = get_visible_lead(db, user, lead_id)
    if not body:
        raise HTTPException(400, "Add at least one model")
    before = {"model_id": lead.model_id, "color": lead.color}
    _save_model_interests(db, lead, body)
    record_changes(db, entity_type="lead", entity_id=lead.lead_id, before=before, after=lead,
                   fields=("model_id", "color"), changed_by_user_id=user.user_id)
    db.commit()
    return {"models": _interest_rows(db, lead)}


TAKEOVER_FIELDS = ("assigned_user_id", "branch_id", "branch_code", "salesperson_email",
                   "enquiry_stage")


def _take_over_lead(db: Session, lead: Lead, branch: Branch | None, assignee: AppUser | None,
                    actor: AppUser) -> dict:
    """A returning customer walked in: the SAME enquiry moves to the PBA who
    attended them (any PBA, any branch) instead of a new enquiry being made.

      - assigned to the attending PBA (CRE: the PBA they picked, or unassigned
        in the chosen branch); the lead moves to that branch so its PBAs/CRE see it
      - a CLOSED enquiry is reopened (back to OPEN)
      - customer details are NOT changed; the PBA only updates the follow-up
      - logged in the Activity Log; the previous PBA is not notified
    """
    before = {f: getattr(lead, f) for f in TAKEOVER_FIELDS}
    lead.assigned_user_id = assignee.user_id if assignee else None
    lead.salesperson_email = assignee.email if assignee else None
    if branch:
        lead.branch_id = branch.branch_id
        lead.branch_code = branch.dealer_code
    if lead.enquiry_stage == EnquiryStage.CLOSED:
        change_stage(db, lead, EnquiryStage.OPEN, actor_user_id=actor.user_id,
                     reason="Returning customer walked in")
    record_changes(db, entity_type="lead", entity_id=lead.lead_id, before=before, after=lead,
                   fields=TAKEOVER_FIELDS, changed_by_user_id=actor.user_id)
    # A CRE handing the lead to a PBA notifies that PBA (a PBA taking it
    # themselves isn't notified — create_notification skips self-notifying).
    if assignee and before["assigned_user_id"] != assignee.user_id:
        create_notification(
            db, user_id=assignee.user_id, type_=NotificationType.LEAD_ASSIGNED,
            title="Returning customer assigned to you",
            message=f"{lead.customer.full_name} walked in again — enquiry {lead.enquiry_no} "
                    f"has been assigned to you by {actor.full_name}.",
            reference_type="lead", reference_id=lead.lead_id, actor_user_id=actor.user_id)
    db.commit()
    return {"lead_id": lead.lead_id, "enquiry_no": lead.enquiry_no, "existing": True}


EDIT_ROLES = READ_ROLES
CUSTOMER_FIELDS = ("full_name", "phone", "pincode", "city", "alt_phone")
LEAD_FIELDS = ("enquiry_at", "first_contact_at", "dealer_code", "branch_code", "salesperson_email",
               "mode_id", "model_id", "color", "sku_code", "opportunity_status_id",
               "lost_reason_id", "next_followup_at")


@router.patch("/leads/{lead_id}", dependencies=[Depends(require_roles(*EDIT_ROLES))])
def update_lead(lead_id: int, body: LeadUpdate, user: AppUser = Depends(get_current_user),
                db: Session = Depends(get_db)):
    lead = get_visible_lead(db, user, lead_id)
    data = body.model_dump(exclude_unset=True)   # only the keys actually sent

    # Snapshot "before" values up front, for every field this endpoint can
    # touch, so we can diff old-vs-new after applying the edits below and
    # log exactly what changed (see audit/service.py). Capturing this before
    # any setattr() runs is what makes "old_value" actually the old value.
    cust = lead.customer
    cust_before = {f: getattr(cust, f, None) for f in CUSTOMER_FIELDS} if cust else {}
    lead_before = {f: getattr(lead, f, None) for f in LEAD_FIELDS}
    lead_before["current_disposition_id"] = lead.current_disposition_id
    lead_before["enquiry_stage"] = lead.enquiry_stage
    lead_before["assigned_user_id"] = lead.assigned_user_id

    # customer fields
    for f in CUSTOMER_FIELDS:
        if f in data and cust is not None:
            setattr(cust, f, data[f])

    # Opportunity status must come from the fixed list — but only when it
    # actually changes, so a lead imported with an old value (e.g. "Open")
    # can still have its other fields saved.
    if ("opportunity_status_id" in data
            and data["opportunity_status_id"] != lead.opportunity_status_id):
        _require_listed(db, OpportunityStatus, data["opportunity_status_id"],
                        "Opportunity Status")

    # Next Follow-up Date: only from now up to 15 days ahead — checked only
    # when it changes, so an older lead's existing date doesn't block saving
    # its other status fields.
    if data.get("next_followup_at") is not None:
        new_fu = data["next_followup_at"]
        cur_fu = lead.next_followup_at
        if new_fu.tzinfo is not None or cur_fu is None or \
                new_fu.replace(second=0, microsecond=0) != cur_fu.replace(second=0, microsecond=0):
            try:
                data["next_followup_at"] = check_followup_date(new_fu)
            except ValueError as e:
                raise HTTPException(400, str(e))

    # simple lead fields
    for f in LEAD_FIELDS:
        if f in data:
            setattr(lead, f, data[f])

    # fields that need mapping / casting
    if "disposition_id" in data:
        # Only validate when it actually changes: a lead imported with an old
        # disposition (e.g. "Call Later") can still have its other status
        # fields saved without being forced to pick a new disposition.
        if data["disposition_id"] != lead.current_disposition_id:
            _require_listed(db, Disposition, data["disposition_id"], "Follow-up Disposition")
        lead.current_disposition_id = data["disposition_id"]
    if "enquiry_stage" in data and data["enquiry_stage"]:
        # Only OPEN <-> CLOSED can be done by hand. Booked and later stages
        # belong to the system (leads/stages.py); a same-value re-save is a no-op.
        change_stage(db, lead, data["enquiry_stage"], actor_user_id=user.user_id,
                     manual=True)

    # ---- reassignment (kept separate: it's the one field that must trigger a
    # notification, so we need the before/after values, not just a blind setattr) ----
    if "assigned_user_id" in data:
        if user.role.value in SALES_ROLES:
            # A PBA/CRE can update a lead's details, but re-assigning a lead
            # to someone else (or themselves) is a management action.
            raise HTTPException(403, "Only Owner/GM/Admin can reassign a lead")
        new_assignee_id = data["assigned_user_id"]
        if new_assignee_id is not None:
            target = db.get(AppUser, new_assignee_id)
            if not target or not target.is_active or target.role != Role.PBA:
                raise HTTPException(400, "Assigned user must be an active PBA")
        previous_assignee_id = lead.assigned_user_id
        lead.assigned_user_id = new_assignee_id
        if new_assignee_id is not None and new_assignee_id != previous_assignee_id:
            create_notification(
                db, user_id=new_assignee_id, type_=NotificationType.LEAD_ASSIGNED,
                title="New lead assigned to you",
                message=f"Lead {lead.enquiry_no} ({cust.full_name if cust else 'Unknown'}) "
                        f"has been assigned to you.",
                reference_type="lead", reference_id=lead.lead_id, actor_user_id=user.user_id,
            )
        # new_assignee_id == previous_assignee_id (re-saving the same person) and
        # new_assignee_id is None (unassigning) both intentionally skip notifying.

    # Log every field that actually changed. Comparing against the snapshot
    # taken above (not against `data`) means a value sent-but-unchanged (e.g.
    # re-saving the same phone number) correctly produces no audit row.
    if cust is not None:
        record_changes(db, entity_type="customer", entity_id=cust.customer_id,
                       before=cust_before, after=cust, fields=CUSTOMER_FIELDS,
                       changed_by_user_id=user.user_id)
    record_changes(db, entity_type="lead", entity_id=lead.lead_id, before=lead_before,
                   after=lead, fields=LEAD_FIELDS + ("current_disposition_id",
                   "enquiry_stage", "assigned_user_id"), changed_by_user_id=user.user_id)

    if "opportunity_status_id" in data:
        db.flush(); db.refresh(lead)
        if is_booking_done(lead):
            ensure_insurance_case(db, lead, user.user_id)      # BOOKING DONE -> insurance starts
    db.commit()
    return {"ok": True}


@router.post("/leads/{lead_id}/followups", status_code=201,
             dependencies=[Depends(require_roles(*SALES_ROLES))])
def add_followup(lead_id: int, body: FollowupCreate,
                 user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    # saved under the person who made the call (PBA or CRE); the lead stays
    # assigned to its PBA
    lead = get_visible_lead(db, user, lead_id)
    _require_listed(db, Disposition, body.disposition_id, "Follow-up Disposition")
    _require_listed(db, OpportunityStatus, body.opportunity_status_id, "Opportunity Status")
    try:
        body.next_followup_at = check_followup_date(body.next_followup_at)
    except ValueError as e:
        raise HTTPException(400, str(e))

    # ---- call details: an enquiry call is only counted when they are filled in ----
    disp = db.get(Disposition, body.disposition_id) if body.disposition_id else None
    for fld in ("showroom_visit", "test_ride_interest"):
        v = getattr(body, fld)
        if v is not None and v.upper() not in CHOICES:
            raise HTTPException(400, f"{fld.replace('_', ' ').title()} must be Yes, No or Planned")
    if needs_call_details(body.contacted, disp.name if disp else None):
        # take what was typed on the follow-up form, else what the lead already has
        if body.model_id:
            _require_listed(db, BikeModel, body.model_id, "Model")
        probe = type("P", (), {})()
        probe.model_id = body.model_id or lead.model_id
        probe.color = body.color or lead.color
        probe.showroom_visit = (body.showroom_visit or lead.showroom_visit or "").upper() or None
        probe.test_ride_interest = (body.test_ride_interest or lead.test_ride_interest or "").upper() or None
        missing = missing_call_details(probe)
        if missing:
            raise HTTPException(400, "This call is not counted until the call details are filled in: "
                                     + ", ".join(missing) + ".")
    if body.model_id:
        lead.model_id = body.model_id
    if (body.color or "").strip():
        lead.color = body.color.strip()
    if body.showroom_visit:
        lead.showroom_visit = body.showroom_visit.upper()
    if body.test_ride_interest:
        lead.test_ride_interest = body.test_ride_interest.upper()

    db.add(LeadFollowup(lead_id=lead_id, user_id=user.user_id, remark=body.remark,
                        contacted=body.contacted, disposition_id=body.disposition_id,
                        opportunity_status_id=body.opportunity_status_id,
                        next_followup_at=body.next_followup_at))
    if body.disposition_id:
        lead.current_disposition_id = body.disposition_id
    if body.opportunity_status_id:
        lead.opportunity_status_id = body.opportunity_status_id
    if body.next_followup_at:
        lead.next_followup_at = body.next_followup_at
    if body.contacted and not lead.first_contact_at:
        # the SLA state (on time / late / ...) is worked out from this time
        # and the enquiry time whenever it is shown — see leads/sla.py
        lead.first_contact_at = now_ist()
    update_callback_reminder(lead, disp.name if disp else None)   # Call Later -> reminder in 1 hour
    db.flush(); db.refresh(lead)
    if is_booking_done(lead):
        ensure_insurance_case(db, lead, user.user_id)      # BOOKING DONE -> insurance starts
    db.commit()
    return {"ok": True}


@router.post("/leads/{lead_id}/test-rides", status_code=201,
             dependencies=[Depends(require_roles(*SALES_ROLES))])
def add_test_ride(lead_id: int, body: TestRideCreate, user: AppUser = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    """Book a test ride (or record a spot ride that's happening right now).
    Rules + automatic lead-status update: app/modules/leads/test_rides.py"""
    lead = get_visible_lead(db, user, lead_id)
    t = create_test_ride(db, lead, status=body.status, scheduled_at=body.scheduled_at,
                         model_id=body.model_id, color=body.color, slot=body.slot,
                         preferred_location=body.preferred_location,
                         actor_user_id=user.user_id)
    db.commit(); db.refresh(t)
    if t.status.value == "BOOKED":     # WhatsApp to the customer and the PBA
        for who in ("CUSTOMER", "PBA"):
            wa.auto_send(db, "TEST_RIDE", lead, user=user, ref_id=t.id, recipient=who)
        db.commit()
    return {"test_ride_id": t.id, "status": t.status.value}


@router.patch("/test-rides/{ride_id}", dependencies=[Depends(require_roles(*SALES_ROLES))])
def change_test_ride(ride_id: int, body: TestRideAction, user: AppUser = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    """The buttons on a Test Ride History row: Mark Completed / Reschedule /
    Cancel. Rules: app/modules/leads/test_rides.py"""
    ride = db.get(TestRide, ride_id)
    # the ride's lead must be one this PBA can see
    if not ride or not scope(db.query(Lead), user).filter(Lead.lead_id == ride.lead_id).first():
        raise HTTPException(404, "Test ride not found")
    update_test_ride(db, ride, action=body.action, scheduled_at=body.scheduled_at,
                     slot=body.slot, actor_user_id=user.user_id)
    db.commit()
    if ride.status.value == "RESCHEDULED" or str(body.action).lower().startswith("resched"):
        lead = db.get(Lead, ride.lead_id)       # the new time goes to the customer and the PBA again
        for who in ("CUSTOMER", "PBA"):
            try:
                wa.send(db, "TEST_RIDE", lead, user=user, ref_id=ride.id, recipient=who)
            except Exception:
                pass
        db.commit()
    return {"ok": True, "status": ride.status.value}


@router.get("/customers/lookup", response_model=CustomerLookup,
            dependencies=[Depends(require_roles(*READ_ROLES))])
def lookup_customer(phone: str, db: Session = Depends(get_db)):
    """Walk-in form phone check: is this number already a customer?

    Searches ALL customers, not just the user's own leads — any PBA can take
    over a returning customer's enquiry. Only called with a number the PBA
    has just typed, so the full number is returned (not masked).
    """
    if len(normalize_phone(phone)) < 10:
        return CustomerLookup(exists=False)
    cust = find_customer_by_phone(db, phone)
    if not cust:
        return CustomerLookup(exists=False)
    leads = (db.query(Lead).filter(Lead.customer_id == cust.customer_id)
             .order_by(Lead.enquiry_at.desc(), Lead.lead_id.desc()).all())
    users = {u.user_id: u.full_name for u in db.query(AppUser).filter(
        AppUser.user_id.in_([l.assigned_user_id for l in leads if l.assigned_user_id] or [-1]))}
    return CustomerLookup(
        exists=True,
        customer=dict(customer_id=cust.customer_id, full_name=cust.full_name, phone=cust.phone,
                      alt_phone=cust.alt_phone, email=cust.email, city=cust.city,
                      pincode=cust.pincode),
        enquiries=[dict(lead_id=l.lead_id, enquiry_no=l.enquiry_no, enquiry_at=l.enquiry_at,
                        model_name=l.model.name if l.model else None,
                        enquiry_stage=l.enquiry_stage.value if l.enquiry_stage else None,
                        opportunity_status=l.opportunity.name if l.opportunity else None,
                        assigned_to=users.get(l.assigned_user_id),
                        branch_name=l.branch.name if l.branch else None) for l in leads],
        previous_details=list(cust.previous_details))


@router.get("/customers", response_model=CustomerListResponse,
            dependencies=[Depends(require_roles(*READ_ROLES))])
def list_customers(user: AppUser = Depends(get_current_user), db: Session = Depends(get_db),
                   search: str | None = None, page: int = 1, page_size: int = 10,
                   branch_id: int | None = None, whole_branch: bool = False):
    # Only customers who have at least one lead visible to this user (and in
    # the chosen branch, if the branch filter is set).
    lead_ids = scope(db.query(Lead.customer_id), user, branch_id, whole_branch).distinct().scalar_subquery()
    q = db.query(Customer).filter(Customer.customer_id.in_(lead_ids))
    if search:
        like = f"%{search}%"
        q = q.filter((Customer.full_name.ilike(like)) | (Customer.phone.ilike(like)) |
                     (Customer.city.ilike(like)))
    total = q.count()
    custs = q.order_by(Customer.full_name).offset((page - 1) * page_size).limit(page_size).all()
    rows = []
    for c in custs:
        visible = scope(db.query(Lead).filter(Lead.customer_id == c.customer_id), user, branch_id, whole_branch)
        latest = visible.order_by(Lead.enquiry_at.desc()).first()
        rows.append(dict(
            customer_id=c.customer_id, full_name=c.full_name,
            contact_masked=mask_phone(c.phone), city=c.city, pincode=c.pincode,
            leads_count=visible.count(),
            latest_enquiry_no=latest.enquiry_no if latest else None,
            latest_model=(latest.model.name if latest and latest.model else None),
            latest_enquiry_at=latest.enquiry_at if latest else None,
            latest_lead_id=latest.lead_id if latest else None))
    return CustomerListResponse(total=total, page=page, page_size=page_size, rows=rows)


@router.get("/followups", response_model=FollowupListResponse,
            dependencies=[Depends(require_roles(*READ_ROLES))])
def list_followups(user: AppUser = Depends(get_current_user), db: Session = Depends(get_db),
                   bucket: str = "all", search: str | None = None,
                   page: int = 1, page_size: int = 10, branch_id: int | None = None):
    now = now_ist()
    day_start = datetime(now.year, now.month, now.day)
    day_end = day_start + timedelta(days=1)

    def base():
        q = scope(db.query(Lead).join(Customer), user, branch_id).filter(
            Lead.next_followup_at.isnot(None))
        return q

    counts = {
        "overdue": base().filter(Lead.next_followup_at < day_start).count(),
        "today": base().filter(Lead.next_followup_at >= day_start,
                               Lead.next_followup_at < day_end).count(),
        "upcoming": base().filter(Lead.next_followup_at >= day_end).count(),
    }
    counts["all"] = counts["overdue"] + counts["today"] + counts["upcoming"]

    q = base()
    if bucket == "overdue":
        q = q.filter(Lead.next_followup_at < day_start)
    elif bucket == "today":
        q = q.filter(Lead.next_followup_at >= day_start, Lead.next_followup_at < day_end)
    elif bucket == "upcoming":
        q = q.filter(Lead.next_followup_at >= day_end)
    if search:
        like = f"%{search}%"
        q = q.filter((Customer.full_name.ilike(like)) | (Customer.phone.ilike(like)) |
                     (Lead.enquiry_no.ilike(like)))
    total = q.count()
    rows = q.order_by(Lead.next_followup_at.asc()).offset((page - 1) * page_size).limit(page_size).all()

    def bucket_of(l):
        if l.next_followup_at < day_start:
            return "overdue"
        if l.next_followup_at < day_end:
            return "today"
        return "upcoming"

    return FollowupListResponse(total=total, page=page, page_size=page_size, counts=counts, rows=[dict(
        lead_id=l.lead_id, enquiry_no=l.enquiry_no, customer_name=l.customer.full_name,
        contact_masked=mask_phone(l.customer.phone),
        model_name=l.model.name if l.model else None,
        opportunity_status=l.opportunity.name if l.opportunity else None,
        disposition=l.current_disposition.name if l.current_disposition else None,
        next_followup_at=l.next_followup_at,
        sla_flag=lead_sla(l)[1], sla_state=lead_sla(l)[0],
        bucket=bucket_of(l)) for l in rows])


@router.get("/pba/dashboard", response_model=PBADashboard,
            dependencies=[Depends(require_roles(*READ_ROLES))])
def pba_dashboard(period: str = "today", branch_id: int | None = None,
                  user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """PBA: their own numbers. CRE: one branch at a time (`branch_id`, one of
    theirs; defaults to their first branch). Owner/GM/Admin: everything, or
    one branch if `branch_id` is given."""
    branch_id = dashboard_branch(user, branch_id)

    # "PERFORMANCE TRACKER" tiles (open bookings/booked/invoiced/delivered)
    # respect the period dropdown ("today"/"week"/"month"/"year").
    period_start, period_end = period_range(period)

    def count_leads(condition):
        return scope(db.query(func.count(Lead.lead_id)).filter(
            condition,
            Lead.enquiry_at >= period_start, Lead.enquiry_at < period_end), user,
            branch_id).scalar() or 0

    # "TODAY'S" tiles (calls_today/quotations_shared) are always today's
    # activity, independent of the period dropdown — matches the UI label.
    today_start, today_end = period_range("today")

    # ── Test rides in the selected period ──────────────────────────────────
    # A test ride belongs to the period by its scheduled date. If it has none
    # (most LeadSquared imports), it falls back to its LEAD'S ENQUIRY DATE —
    # not the import date — so old test rides stay in the month they happened.
    tr_date = func.coalesce(TestRide.scheduled_at, Lead.enquiry_at, TestRide.created_at)
    today_start_dt = period_range("today")[0]

    def test_rides(*statuses, upcoming=None):
        q = (db.query(func.count(TestRide.id))
             .join(Lead, TestRide.lead_id == Lead.lead_id)
             .filter(tr_date >= period_start, tr_date < period_end))
        if statuses:
            q = q.filter(TestRide.status.in_(statuses))
        if upcoming is True:
            q = q.filter(tr_date >= today_start_dt)
        elif upcoming is False:
            q = q.filter(tr_date < today_start_dt)
        return scope(q, user, branch_id).scalar() or 0

    open_statuses = (TestRideStatus.BOOKED, TestRideStatus.RESCHEDULED)
    tr_completed = test_rides(TestRideStatus.COMPLETED)
    # Scheduled = still UPCOMING (booked/rescheduled, date today or later).
    tr_scheduled = test_rides(*open_statuses, upcoming=True)
    # Booked but the date has passed and nobody marked it Completed/Cancelled.
    tr_pending_update = test_rides(*open_statuses, upcoming=False)
    tr_cancelled = test_rides(TestRideStatus.CANCELLED)
    tr_total = test_rides()

    # TD Completed Ratio = completed ÷ test rides that were DUE by today
    # (completed + cancelled + past-dated still-open). Upcoming ones are left
    # out: they can't have been completed yet, so counting them would drag the
    # ratio down mid-month for no reason.
    tr_due = tr_total - tr_scheduled
    td_ratio = round(tr_completed * 100 / tr_due) if tr_due else 0

    # ── Total Target Ratio (stand-in until real targets exist) ─────────────
    # Same definition as the "Target Tracker" chart (dashboard/router.py), so
    # the two never disagree: leads that reached BOOKED or INVOICED ÷ all leads
    # enquired in the period.
    def leads_in_period(condition=None):
        q = db.query(func.count(Lead.lead_id)).filter(
            Lead.enquiry_at >= period_start, Lead.enquiry_at < period_end)
        if condition is not None:
            q = q.filter(condition)
        return scope(q, user, branch_id).scalar() or 0

    target_total = leads_in_period()
    target_achieved = leads_in_period(sold_condition(db))
    target_ratio = round(target_achieved * 100 / target_total) if target_total else 0
    from app.modules.targets import service as _tgt
    _real = _tgt.period_targets(db, user, branch_id, period, period_start, period_end)
    if _real:   # real monthly targets exist: bookings made vs target
        target_total = sum(_real.values())
        target_achieved = sum(_tgt.booked_by_model(db, user, branch_id, period_start, period_end).values())
        target_ratio = round(target_achieved * 100 / target_total) if target_total else 0

    calls_today = scope(db.query(func.count(Lead.lead_id)).filter(
        Lead.next_followup_at.isnot(None),
        Lead.next_followup_at >= today_start, Lead.next_followup_at < today_end), user,
        branch_id).scalar() or 0

    # Quotations shared today: a PBA counts their own; a CRE (and Owner/GM/
    # Admin) counts every quotation shared on the branch's leads.
    quotations_shared_q = (db.query(func.count(Quotation.quotation_id))
                           .join(Lead, Quotation.lead_id == Lead.lead_id)
                           .filter(Quotation.status == QuotationStatus.SHARED,
                                   Quotation.updated_at >= today_start,
                                   Quotation.updated_at < today_end))
    if user.role == Role.PBA:
        quotations_shared_q = quotations_shared_q.filter(
            Quotation.created_by_user_id == user.user_id)
    else:
        quotations_shared_q = scope(quotations_shared_q, user, branch_id)
    quotations_shared = quotations_shared_q.scalar() or 0

    # Open Bookings = booked, bike not handed over yet. Booked / Invoiced /
    # Delivered each mean "reached that step or beyond" (definitions: leads/stages.py).
    return PBADashboard(open_bookings=count_leads(open_booking_condition()),
                        booked=count_leads(sold_condition(db)),
                        invoiced=count_leads(invoiced_condition(db)),
                        delivered=count_leads(delivered_condition(db)),
                        calls_today=calls_today,
                        quotations_shared=quotations_shared, test_rides_completed=tr_completed,
                        test_rides_scheduled=tr_scheduled,
                        test_rides_pending_update=tr_pending_update,
                        test_rides_cancelled=tr_cancelled, test_rides_total=tr_total,
                        test_rides_due=tr_due, td_completed_ratio=td_ratio,
                        total_target_ratio=target_ratio,
                        target_achieved=target_achieved, target_total=target_total)


# ---------- unassigned pool: claim / assign ----------
class AssignIn(BaseModel):
    user_id: int


def _assign(db: Session, lead: Lead, target: AppUser, actor: AppUser, verb: str) -> None:
    before = {"assigned_user_id": lead.assigned_user_id}
    first_owner = lead.assigned_user_id is None
    lead.assigned_user_id = target.user_id
    lead.salesperson_email = target.email or target.ls_email or lead.salesperson_email
    record_changes(db, entity_type="lead", entity_id=lead.lead_id, before=before, after=lead,
                   fields=("assigned_user_id",), changed_by_user_id=actor.user_id)
    if target.user_id != actor.user_id:
        create_notification(
            db, user_id=target.user_id, type_=NotificationType.LEAD_ASSIGNED,
            title="Customer assigned to you",
            message=f"{lead.customer.full_name} (enquiry {lead.enquiry_no}) was {verb} you by {actor.full_name}.",
            reference_type="lead", reference_id=lead.lead_id, actor_user_id=actor.user_id)
    db.commit()
    if first_owner:        # the welcome message goes out once, when the customer first gets a PBA
        wa.auto_send(db, "WELCOME", lead, user=actor); db.commit()


@router.post("/leads/{lead_id}/claim", dependencies=[Depends(require_roles("PBA"))])
def claim_lead(lead_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """A PBA takes an unassigned customer of their own branch."""
    lead = get_visible_lead(db, user, lead_id)
    if lead.assigned_user_id is not None:
        owner = db.get(AppUser, lead.assigned_user_id)
        raise HTTPException(409, f"Already assigned to {owner.full_name if owner else 'another PBA'}")
    if lead.branch_id != user.branch_id:
        raise HTTPException(403, "This customer belongs to another branch")
    _assign(db, lead, user, user, "assigned to")
    return {"ok": True, "assigned_to": user.full_name}


@router.post("/leads/{lead_id}/assign", dependencies=[Depends(require_roles("PBA", "CRE", "OWNER", "GM", "ADMIN"))])
def assign_lead(lead_id: int, body: AssignIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """Give a customer to a PBA of the same branch.
    CRE / Owner / GM / Admin: any customer they can see. PBA: only their own, or an unassigned one."""
    lead = get_visible_lead(db, user, lead_id)
    if user.role == Role.PBA and lead.assigned_user_id not in (None, user.user_id):
        raise HTTPException(403, "Only the PBA who owns this customer (or the CRE) can hand it over")
    target = db.get(AppUser, body.user_id)
    if not target or not target.is_active or target.role != Role.PBA or target.branch_id != lead.branch_id:
        raise HTTPException(400, "Choose an active PBA of this customer's branch")
    if lead.assigned_user_id == target.user_id:
        raise HTTPException(400, "Already assigned to this PBA")
    _assign(db, lead, target, user, "handed to")
    return {"ok": True, "assigned_to": target.full_name}
