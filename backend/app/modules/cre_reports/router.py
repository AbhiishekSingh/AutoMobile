"""CRE-wise reports for Owner / GM / Admin (a CRE sees only their own row).

  GET /cre-reports                    the whole report (rows, funnel, distribution, trend, review links)
  GET /cre-reports/leads?kind=...     drill-down list behind a number
  GET /cre-reports/export             the same report as an Excel file
Filters: date_from, date_to, cre_id, branch_id, source, opportunity_status_id, disposition_id
"""
from datetime import date
from io import BytesIO
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.modules.cre_reports import service as svc
from app.modules.users.models import AppUser

router = APIRouter(prefix="/cre-reports", tags=["cre-reports"], dependencies=[Depends(require_roles("OWNER", "GM", "ADMIN", "CRE"))])


def _f(source, opportunity_status_id, disposition_id):
    if source and source not in ("CSV", "WALKIN"):
        raise HTTPException(400, "Unknown lead source")
    return {"source": source, "opportunity_status_id": opportunity_status_id, "disposition_id": disposition_id}


def _only(user: AppUser):
    return user.user_id if user.role.value == "CRE" else None


@router.get("")
def get_report(date_from: Optional[date] = None, date_to: Optional[date] = None, cre_id: Optional[int] = None, branch_id: Optional[int] = None,
               source: Optional[str] = None, opportunity_status_id: Optional[int] = None, disposition_id: Optional[int] = None,
               user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(400, "From date is after the To date")
    return svc.report(db, date_from, date_to, cre_id, branch_id, _f(source, opportunity_status_id, disposition_id), _only(user))


@router.get("/leads")
def drill(kind: str = Query("all"), date_from: Optional[date] = None, date_to: Optional[date] = None, cre_id: Optional[int] = None,
          branch_id: Optional[int] = None, source: Optional[str] = None, opportunity_status_id: Optional[int] = None,
          disposition_id: Optional[int] = None, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    if kind not in svc.KINDS:
        raise HTTPException(400, "Unknown list")
    start, end, *_ = svc.window(date_from, date_to)
    bids = set()
    for c in svc.cres(db, _only(user)):
        if not cre_id or c.user_id == cre_id:
            bids |= {b for b in c.branch_ids if not branch_id or b == branch_id}
    return {"title": svc.KINDS[kind], "rows": svc.lead_list(db, kind, list(bids), start, end, _f(source, opportunity_status_id, disposition_id))}


@router.get("/export")
def export(date_from: Optional[date] = None, date_to: Optional[date] = None, cre_id: Optional[int] = None, branch_id: Optional[int] = None,
           source: Optional[str] = None, opportunity_status_id: Optional[int] = None, disposition_id: Optional[int] = None,
           user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    from openpyxl import Workbook
    from openpyxl.styles import Font
    d = svc.report(db, date_from, date_to, cre_id, branch_id, _f(source, opportunity_status_id, disposition_id), _only(user))
    wb = Workbook(); first = [True]

    def sheet(title, header, rows):
        ws = wb.active if first[0] else wb.create_sheet(); first[0] = False
        ws.title = title; ws.append(header)
        for c in ws[1]: c.font = Font(bold=True)
        for r in rows: ws.append(r)
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = min(max(len(str(c.value or "")) for c in col) + 2, 40)
    sheet("CRE-wise", ["CRE", "Branches", "Leads", "Contacted", "Qualified", "Calls logged", "Customers contacted", "Follow-up pending", "Due today", "Overdue",
                       "Follow-up completion %", "Quotations created", "Test rides scheduled", "Test rides completed", "Test ride completion %", "Showroom visits",
                       "Bookings", "Conversion %", "Lost leads", "Review links sent", "Final reviews done", "Final reviews pending"],
          [[r["name"], ", ".join(r["branches"]), r["total"], r["contacted"], r["qualified"], r["calls"], r["customers_contacted"], r["pending"], r["due_today"], r["overdue"],
            r["followup_completion_pct"], r["quotations_created"], r["tr_scheduled"], r["tr_completed"], r["tr_completion_pct"], r["showroom"], r["booked"],
            r["conversion_pct"], r["lost"], r["review_sent"], r["final_done"], r["final_pending"]] for r in d["rows"]])
    sheet("Funnel", ["Stage", "Leads"], [[x["label"], x["count"]] for x in d["funnel"]])
    sheet("Opportunity status", ["Status", "Leads"], [[x["name"], x["count"]] for x in d["opportunity"]])
    sheet("Disposition", ["Disposition", "Leads"], [[x["name"], x["count"]] for x in d["disposition"]])
    sheet("Follow-up trend", ["Date", "Calls logged"], [[x["date"], x["count"]] for x in d["trend"]])
    rv = d["review"]
    sheet("Review links by CRE", ["CRE", "Sent"], [[x["name"], x["count"]] for x in rv["by_cre"]])
    sheet("Review links by branch", ["Branch", "Sent"], [[x["name"], x["count"]] for x in rv["by_branch"]])
    sheet("Review links by date", ["Date", "Sent"], [[x["date"], x["count"]] for x in rv["by_day"]])
    buf = BytesIO(); wb.save(buf); buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f'attachment; filename="cre-report-{d["from"]}-{d["to"]}.xlsx"'})
