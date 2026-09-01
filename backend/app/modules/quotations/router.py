"""API endpoints for the Quotations module."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from fastapi.responses import Response
from app.modules.quotations.pdf import build_quotation_pdf
from app.core.database import get_db, now_ist
from app.core.deps import get_current_user, require_roles
from app.modules.leads.models import Lead
from app.modules.quotations.models import (Quotation, QuotationDocument,
                                           QuotationEmiOption,
                                           QuotationInclusion)
from app.modules.quotations.schemas import (DocumentsBulkUpdate,
                                            EmiBulkUpdate,
                                            InclusionsBulkUpdate,
                                            QuotationCreate, QuotationDetail,
                                            QuotationListItem,
                                            QuotationStatusUpdate,
                                            QuotationUpdate)
from app.modules.quotations.service import (default_valid_until,
                                            mark_lead_quoted,
                                            next_quotation_no, scope,
                                            seed_defaults)
from app.modules.users.models import AppUser

router = APIRouter(tags=["quotations"])
READ_ROLES = ("PBA", "OWNER", "GM", "ADMIN")
WRITE_ROLES = ("PBA",)


def _get_or_404(db: Session, quotation_id: int, user: AppUser) -> Quotation:
    q = scope(db.query(Quotation), user).filter(
        Quotation.quotation_id == quotation_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Quotation not found")
    return q


@router.post("/leads/{lead_id}/quotations", response_model=QuotationDetail,
            status_code=201, dependencies=[Depends(require_roles(*WRITE_ROLES))])
def create_quotation(lead_id: int, body: QuotationCreate,
                     user: AppUser = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.lead_id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    quotation = Quotation(
        quotation_no=next_quotation_no(db), lead_id=lead.lead_id,
        customer_id=lead.customer_id, branch_id=user.branch_id,
        created_by_user_id=user.user_id, customer_name=body.customer_name,
        contact_no=body.contact_no, email=body.email, model_id=body.model_id,
        color=body.color, on_road_price=body.on_road_price,
        hspr_registration_type=body.hspr_registration_type,
        sales_manager_name=body.sales_manager_name,
        finance_bank_name=body.finance_bank_name,
        finance_financer_name=body.finance_financer_name,
        valid_until=default_valid_until(),
    )
    db.add(quotation); db.flush()
    seed_defaults(db, quotation)
    mark_lead_quoted(lead)
    db.commit(); db.refresh(quotation)
    return quotation


@router.get("/leads/{lead_id}/quotations", response_model=list[QuotationListItem],
           dependencies=[Depends(require_roles(*READ_ROLES))])
def list_lead_quotations(lead_id: int, user: AppUser = Depends(get_current_user),
                         db: Session = Depends(get_db)):
    return scope(db.query(Quotation), user).filter(
        Quotation.lead_id == lead_id).order_by(Quotation.created_at.desc()).all()


@router.get("/quotations", response_model=list[QuotationListItem],
           dependencies=[Depends(require_roles(*READ_ROLES))])
def list_quotations(user: AppUser = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    """The Quotations page shows only quotations the logged-in user created."""
    return scope(db.query(Quotation), user).filter(
        Quotation.created_by_user_id == user.user_id).order_by(
        Quotation.created_at.desc()).all()


@router.get("/quotations/{quotation_id}", response_model=QuotationDetail,
           dependencies=[Depends(require_roles(*READ_ROLES))])
def get_quotation(quotation_id: int, user: AppUser = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    return _get_or_404(db, quotation_id, user)


@router.patch("/quotations/{quotation_id}", response_model=QuotationDetail,
             dependencies=[Depends(require_roles(*WRITE_ROLES))])
def update_quotation(quotation_id: int, body: QuotationUpdate,
                     user: AppUser = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    quotation = _get_or_404(db, quotation_id, user)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(quotation, field, value)
    db.commit(); db.refresh(quotation)
    return quotation


@router.patch("/quotations/{quotation_id}/inclusions", response_model=QuotationDetail,
             dependencies=[Depends(require_roles(*WRITE_ROLES))])
def update_inclusions(quotation_id: int, body: InclusionsBulkUpdate,
                      user: AppUser = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    quotation = _get_or_404(db, quotation_id, user)
    db.query(QuotationInclusion).filter(
        QuotationInclusion.quotation_id == quotation_id).delete()
    for i, row in enumerate(body.inclusions):
        db.add(QuotationInclusion(quotation_id=quotation_id, description=row.description,
                                  included=row.included, sort_order=row.sort_order or i))
    db.commit(); db.refresh(quotation)
    return quotation


@router.patch("/quotations/{quotation_id}/emi", response_model=QuotationDetail,
             dependencies=[Depends(require_roles(*WRITE_ROLES))])
def update_emi(quotation_id: int, body: EmiBulkUpdate,
               user: AppUser = Depends(get_current_user),
               db: Session = Depends(get_db)):
    quotation = _get_or_404(db, quotation_id, user)
    db.query(QuotationEmiOption).filter(
        QuotationEmiOption.quotation_id == quotation_id).delete()
    for row in body.emi_options:
        db.add(QuotationEmiOption(quotation_id=quotation_id, **row.model_dump()))
    db.commit(); db.refresh(quotation)
    return quotation


@router.patch("/quotations/{quotation_id}/documents", response_model=QuotationDetail,
             dependencies=[Depends(require_roles(*WRITE_ROLES))])
def update_documents(quotation_id: int, body: DocumentsBulkUpdate,
                     user: AppUser = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    quotation = _get_or_404(db, quotation_id, user)
    db.query(QuotationDocument).filter(
        QuotationDocument.quotation_id == quotation_id).delete()
    for row in body.documents:
        db.add(QuotationDocument(quotation_id=quotation_id, **row.model_dump()))
    db.commit(); db.refresh(quotation)
    return quotation

@router.get("/quotations/{quotation_id}/pdf",
           dependencies=[Depends(require_roles(*READ_ROLES))])
def get_quotation_pdf(quotation_id: int, user: AppUser = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    quotation = _get_or_404(db, quotation_id, user)
    branch = quotation.lead.branch if quotation.lead else None
    pdf_bytes = build_quotation_pdf(
        quotation,
        branch_name=branch.name if branch else "S.K Automobiles",
        branch_address=branch.address if branch and branch.address else "-",
        branch_contact=branch.contact_no if branch else None,
    )
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{quotation.quotation_no}.pdf"'})

@router.patch("/quotations/{quotation_id}/status", response_model=QuotationDetail,
             dependencies=[Depends(require_roles(*READ_ROLES))])
def update_status(quotation_id: int, body: QuotationStatusUpdate,
                  user: AppUser = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    quotation = _get_or_404(db, quotation_id, user)
    quotation.status = body.status
    db.commit(); db.refresh(quotation)
    return quotation