from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db, now_ist
from app.core.deps import get_current_user, require_roles
from app.modules.leads.models import (BikeModel, Customer, Disposition,
                                      EnquiryMode, Lead, LeadFollowup, LeadType,
                                      LeadSource, LostReason, OpportunityStatus,
                                      SLAFlag, TestRide, TestRideStatus,
                                      EnquiryStage)
from app.modules.leads.schemas import (CustomerListResponse, FollowupCreate,
                                       FollowupListResponse, LeadCreate,
                                       LeadDetail, LeadListResponse, LeadUpdate,
                                       Lookups, PBADashboard, TestRideCreate)
from app.modules.leads.service import bucket_filter, mask_phone, scope
from app.modules.users.models import AppUser, Branch

router = APIRouter(tags=["pba"])
READ_ROLES = ("PBA", "OWNER", "GM", "ADMIN")


@router.get("/lookups", response_model=Lookups,
            dependencies=[Depends(require_roles(*READ_ROLES))])
def lookups(db: Session = Depends(get_db)):
    q = lambda M: db.query(M).order_by(M.id).all()  # noqa: E731
    return Lookups(enquiry_modes=q(EnquiryMode), opportunity_statuses=q(OpportunityStatus),
                   dispositions=q(Disposition), lost_reasons=q(LostReason), models=q(BikeModel))


@router.get("/leads/tiles", dependencies=[Depends(require_roles(*READ_ROLES))])
def tiles(user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    base = scope(db.query(Lead.mode_id, func.count(Lead.lead_id)), user).group_by(Lead.mode_id)
    counts = {mid: c for mid, c in base.all()}
    modes = db.query(EnquiryMode).order_by(EnquiryMode.id).all()
    out = [{"key": "total", "label": "Total Leads", "count": sum(counts.values())}]
    for m in modes:
        out.append({"key": m.name, "label": m.name, "count": counts.get(m.id, 0)})
    return out


@router.get("/leads/pipeline", dependencies=[Depends(require_roles(*READ_ROLES))])
def pipeline(user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    buckets = [("all", "All Leads"), ("completed", "Completed"), ("pending", "Pending"),
               ("overdue", "Overdue"), ("calllater", "Call Later"), ("testride", "Test Ride"),
               ("casual", "Casual Enquiry"), ("future", "Future Lead"),
               ("service", "Service / Spare Part"), ("closed", "Closed")]
    out = []
    for key, label in buckets:
        q = bucket_filter(scope(db.query(func.count(Lead.lead_id)), user), key, db)
        out.append({"key": key, "label": label, "count": q.scalar() or 0})
    return out


@router.get("/leads", response_model=LeadListResponse,
            dependencies=[Depends(require_roles(*READ_ROLES))])
def list_leads(user: AppUser = Depends(get_current_user), db: Session = Depends(get_db),
               mode: str | None = None, bucket: str = "all", search: str | None = None,
               page: int = 1, page_size: int = 10):
    q = scope(db.query(Lead).join(Customer), user)
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
    return LeadListResponse(total=total, page=page, page_size=page_size, rows=[dict(
        lead_id=l.lead_id, enquiry_no=l.enquiry_no, enquiry_at=l.enquiry_at,
        enquiry_mode=l.mode.name if l.mode else None, customer_name=l.customer.full_name,
        contact_masked=mask_phone(l.customer.phone), model_name=l.model.name if l.model else None,
        opportunity_status=l.opportunity.name if l.opportunity else None,
        disposition=l.current_disposition.name if l.current_disposition else None,
        sla_flag=l.sla_flag.value if l.sla_flag else "YELLOW") for l in rows])


@router.get("/leads/{lead_id}", response_model=LeadDetail,
            dependencies=[Depends(require_roles(*READ_ROLES))])
def lead_detail(lead_id: int, db: Session = Depends(get_db)):
    l = db.get(Lead, lead_id)
    if not l:
        raise HTTPException(404, "Lead not found")
    branch = db.get(Branch, l.branch_id) if l.branch_id else None
    sp = db.get(AppUser, l.assigned_user_id) if l.assigned_user_id else None
    within3 = None
    if l.first_contact_at and l.enquiry_at:
        within3 = (l.first_contact_at - l.enquiry_at) <= timedelta(hours=3)
    return LeadDetail(
        lead_id=l.lead_id, enquiry_no=l.enquiry_no, enquiry_date=l.enquiry_at,
        enquiry_time=l.enquiry_at.strftime("%H:%M") if l.enquiry_at else None,
        dealer_code=l.dealer_code, branch_name=branch.name if branch else None,
        salesperson_name=sp.full_name if sp else None, salesperson_email=l.salesperson_email,
        first_contact_at=l.first_contact_at, within_3hrs=within3,
        followup_enquiry_mode=l.mode.name if l.mode else None,
        customer_name=l.customer.full_name, mobile=l.customer.phone, pincode=l.customer.pincode,
        model_name=l.model.name if l.model else None, color=l.color, sku_code=l.sku_code,
        enquiry_stage=l.enquiry_stage.value if l.enquiry_stage else None,
        opportunity_status=l.opportunity.name if l.opportunity else None,
        disposition=l.current_disposition.name if l.current_disposition else None,
        lost_reason=l.lost_reason.name if l.lost_reason else None,
        next_followup_at=l.next_followup_at, ageing_days=l.ageing_days or 0,
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
                    for t in l.test_rides])


@router.post("/leads", status_code=201, dependencies=[Depends(require_roles("PBA"))])
def create_lead(body: LeadCreate, user: AppUser = Depends(get_current_user),
                db: Session = Depends(get_db)):
    cust = db.query(Customer).filter(Customer.phone == body.phone).first()
    if not cust:
        cust = Customer(phone=body.phone, full_name=body.full_name, alt_phone=body.alt_phone,
                        city=body.city, pincode=body.pincode)
        db.add(cust); db.flush()
    seq = (db.query(func.count(Lead.lead_id)).scalar() or 0) + 1
    lead = Lead(enquiry_no=f"ENQ{100000 + seq}", customer_id=cust.customer_id,
                branch_id=user.branch_id, assigned_user_id=user.user_id, mode_id=body.mode_id,
                model_id=body.model_id, color=body.color, lead_type=LeadType(body.lead_type),
                source=LeadSource(body.source), enquiry_at=now_ist(),
                sla_flag=SLAFlag.YELLOW, salesperson_email=user.email)
    db.add(lead); db.commit(); db.refresh(lead)
    return {"lead_id": lead.lead_id, "enquiry_no": lead.enquiry_no}


EDIT_ROLES = ("PBA", "OWNER", "GM", "ADMIN")
CUSTOMER_FIELDS = ("full_name", "phone", "pincode", "city", "alt_phone")
LEAD_FIELDS = ("enquiry_at", "first_contact_at", "dealer_code", "salesperson_email",
               "mode_id", "model_id", "color", "sku_code", "opportunity_status_id",
               "lost_reason_id", "next_followup_at", "ageing_days")


@router.patch("/leads/{lead_id}", dependencies=[Depends(require_roles(*EDIT_ROLES))])
def update_lead(lead_id: int, body: LeadUpdate, db: Session = Depends(get_db)):
    lead = db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    data = body.model_dump(exclude_unset=True)   # only the keys actually sent

    # customer fields
    cust = lead.customer
    for f in CUSTOMER_FIELDS:
        if f in data and cust is not None:
            setattr(cust, f, data[f])

    # simple lead fields
    for f in LEAD_FIELDS:
        if f in data:
            setattr(lead, f, data[f])

    # fields that need mapping / casting
    if "disposition_id" in data:
        lead.current_disposition_id = data["disposition_id"]
    if "enquiry_stage" in data and data["enquiry_stage"]:
        lead.enquiry_stage = EnquiryStage(data["enquiry_stage"])

    db.commit()
    return {"ok": True}


@router.post("/leads/{lead_id}/followups", status_code=201,
             dependencies=[Depends(require_roles("PBA"))])
def add_followup(lead_id: int, body: FollowupCreate,
                 user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    lead = db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
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
        lead.first_contact_at = now_ist()
        elapsed = lead.first_contact_at - (lead.enquiry_at or lead.first_contact_at)
        lead.sla_flag = SLAFlag.GREEN if elapsed <= timedelta(hours=3) else SLAFlag.RED
    db.commit()
    return {"ok": True}


@router.post("/leads/{lead_id}/test-rides", status_code=201,
             dependencies=[Depends(require_roles("PBA"))])
def add_test_ride(lead_id: int, body: TestRideCreate, db: Session = Depends(get_db)):
    if not db.get(Lead, lead_id):
        raise HTTPException(404, "Lead not found")
    t = TestRide(lead_id=lead_id, model_id=body.model_id, color=body.color,
                 status=TestRideStatus(body.status), scheduled_at=body.scheduled_at,
                 slot=body.slot, preferred_location=body.preferred_location,
                 completed=(body.status == "COMPLETED"))
    db.add(t); db.commit(); db.refresh(t)
    return {"test_ride_id": t.id}


@router.get("/customers", response_model=CustomerListResponse,
            dependencies=[Depends(require_roles(*READ_ROLES))])
def list_customers(user: AppUser = Depends(get_current_user), db: Session = Depends(get_db),
                   search: str | None = None, page: int = 1, page_size: int = 10):
    # Only customers who have at least one lead visible to this user (branch-scoped).
    lead_ids = scope(db.query(Lead.customer_id), user).distinct().scalar_subquery()
    q = db.query(Customer).filter(Customer.customer_id.in_(lead_ids))
    if search:
        like = f"%{search}%"
        q = q.filter((Customer.full_name.ilike(like)) | (Customer.phone.ilike(like)) |
                     (Customer.city.ilike(like)))
    total = q.count()
    custs = q.order_by(Customer.full_name).offset((page - 1) * page_size).limit(page_size).all()
    rows = []
    for c in custs:
        visible = scope(db.query(Lead).filter(Lead.customer_id == c.customer_id), user)
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
                   page: int = 1, page_size: int = 10):
    now = now_ist()
    day_start = datetime(now.year, now.month, now.day)
    day_end = day_start + timedelta(days=1)

    def base():
        q = scope(db.query(Lead).join(Customer), user).filter(Lead.next_followup_at.isnot(None))
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
        sla_flag=l.sla_flag.value if l.sla_flag else "YELLOW",
        bucket=bucket_of(l)) for l in rows])


@router.get("/pba/dashboard", response_model=PBADashboard,
            dependencies=[Depends(require_roles(*READ_ROLES))])
def pba_dashboard(user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    def stage(s):
        return scope(db.query(func.count(Lead.lead_id)).filter(Lead.enquiry_stage == s), user).scalar() or 0
    tr_completed = db.query(func.count(TestRide.id)).filter(TestRide.status == TestRideStatus.COMPLETED).scalar() or 0
    tr_scheduled = db.query(func.count(TestRide.id)).filter(TestRide.status == TestRideStatus.BOOKED).scalar() or 0
    return PBADashboard(open_bookings=stage("BOOKED"), booked=stage("BOOKED"),
                        invoiced=stage("INVOICED"), delivered=0,
                        calls_today=scope(db.query(func.count(Lead.lead_id)).filter(Lead.next_followup_at.isnot(None)), user).scalar() or 0,
                        quotations_shared=0, test_rides_completed=tr_completed,
                        test_rides_scheduled=tr_scheduled, total_target_ratio=78, td_completed_ratio=64)