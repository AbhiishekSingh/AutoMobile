"""API endpoints for the Quotations module."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from fastapi.responses import Response
from app.modules.quotations.pdf import build_quotation_pdf
from app.modules.quotations.email import (EmailNotConfigured, EmailSendError,
                                          send_quotation_email)
# WhatsApp sending is temporarily disabled while the Meta production message
# template is pending approval (~1 week) — see the commented-out endpoint
# below and "Send via Email" as the stopgap. Re-enable by uncommenting both
# this import and the endpoint once the template is approved.
# from app.modules.quotations.whatsapp import (WhatsAppNotConfigured,
#                                              WhatsAppSendError,
#                                              send_quotation_pdf)
from app.core.database import get_db, now_ist
from app.core.deps import get_current_user, require_roles
from app.modules.leads.models import Lead
from app.modules.quotations.models import (Quotation, QuotationDocument,
                                           QuotationEmiOption,
                                           QuotationInclusion,
                                           QuotationStatus)
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
from app.modules.users.access import MANAGER_ROLES, SALES_ROLES, get_visible_lead
from app.modules.users.models import AppUser

router = APIRouter(tags=["quotations"])
READ_ROLES = SALES_ROLES + MANAGER_ROLES
WRITE_ROLES = SALES_ROLES          # PBA and CRE create/edit quotations


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
    lead = get_visible_lead(db, user, lead_id)

    quotation = Quotation(
        quotation_no=next_quotation_no(db), lead_id=lead.lead_id,
        # the LEAD's branch, not the creator's: a CRE covers two branches, and
        # the PDF / per-branch WhatsApp number must match the lead's showroom
        customer_id=lead.customer_id, branch_id=lead.branch_id,
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
    get_visible_lead(db, user, lead_id)
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


# --- "Send via WhatsApp" temporarily disabled ------------------------------
# The Meta production message template is pending approval (~1 week).
# "Send via Email" below is the stopgap in the meantime. To re-enable:
# uncomment the whatsapp import near the top of this file, and uncomment
# the whole block below.
#
# @router.post("/quotations/{quotation_id}/whatsapp-send",
#             dependencies=[Depends(require_roles(*READ_ROLES))])
# def send_quotation_whatsapp(quotation_id: int, user: AppUser = Depends(get_current_user),
#                             db: Session = Depends(get_db)):
#     """Sends the quotation PDF straight to the customer's WhatsApp as a
#     document attachment, via Meta's approved WhatsApp template (see
#     app/modules/quotations/whatsapp.py). On success, marks the quotation as
#     SHARED so it shows correctly in the Quotation Funnel dashboard chart.
#     """
#     quotation = _get_or_404(db, quotation_id, user)
#     branch = quotation.lead.branch if quotation.lead else None
#     pdf_bytes = build_quotation_pdf(
#         quotation,
#         branch_name=branch.name if branch else "S.K Automobiles",
#         branch_address=branch.address if branch and branch.address else "-",
#         branch_contact=branch.contact_no if branch else None,
#     )
#
#     try:
#         message_id = send_quotation_pdf(
#             contact_no=quotation.contact_no,
#             pdf_bytes=pdf_bytes,
#             filename=f"{quotation.quotation_no}.pdf",
#             customer_name=quotation.customer_name,
#             model_name=quotation.model.name if quotation.model else "",
#         )
#     except WhatsAppNotConfigured as e:
#         raise HTTPException(status_code=400, detail=str(e))
#     except WhatsAppSendError as e:
#         raise HTTPException(status_code=502, detail=str(e))
#
#     quotation.status = QuotationStatus.SHARED
#     db.commit()
#
#     return {"success": True, "message_id": message_id, "sent_to": quotation.contact_no}
# -----------------------------------------------------------------------------


@router.post("/quotations/{quotation_id}/email-send",
            dependencies=[Depends(require_roles(*READ_ROLES))])
def send_quotation_email_route(quotation_id: int, user: AppUser = Depends(get_current_user),
                               db: Session = Depends(get_db)):
    """Emails the quotation PDF straight to the customer's email address as
    an attachment (see app/modules/quotations/email.py). Stopgap for "Send
    via WhatsApp" while the Meta template is pending approval — on success,
    marks the quotation as SHARED, same as the WhatsApp path did, so the
    Quotation Funnel dashboard chart doesn't need to know or care which
    channel was actually used.
    """
    quotation = _get_or_404(db, quotation_id, user)
    branch = quotation.lead.branch if quotation.lead else None
    pdf_bytes = build_quotation_pdf(
        quotation,
        branch_name=branch.name if branch else "S.K Automobiles",
        branch_address=branch.address if branch and branch.address else "-",
        branch_contact=branch.contact_no if branch else None,
    )

    try:
        result = send_quotation_email(
            to_email=quotation.email,
            pdf_bytes=pdf_bytes,
            filename=f"{quotation.quotation_no}.pdf",
            customer_name=quotation.customer_name,
            model_name=quotation.model.name if quotation.model else "",
            quotation_no=quotation.quotation_no,
        )
    except EmailNotConfigured as e:
        raise HTTPException(status_code=400, detail=str(e))
    except EmailSendError as e:
        raise HTTPException(status_code=502, detail=str(e))

    quotation.status = QuotationStatus.SHARED
    db.commit()

    return {"success": True, "result": result, "sent_to": quotation.email}


@router.patch("/quotations/{quotation_id}/status", response_model=QuotationDetail,
             dependencies=[Depends(require_roles(*READ_ROLES))])
def update_status(quotation_id: int, body: QuotationStatusUpdate,
                  user: AppUser = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    quotation = _get_or_404(db, quotation_id, user)
    quotation.status = body.status
    db.commit(); db.refresh(quotation)
    return quotation