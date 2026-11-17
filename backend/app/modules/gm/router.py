"""GM consolidated reporting (also open to Owner / Admin).
  GET /gm/performance   PBA-wise, CRE-wise, PBA vs CRE, funnel, SLA, bottlenecks
  GET /gm/customers     customer-wise booking / insurance / RTO / delivery status
  GET /gm/export        Excel of all of the above
The Owner dashboard endpoints (/owner/*) are open to GM as well and give the dealership overview.
"""
import io
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_roles
from app.modules.gm import service as svc

router = APIRouter(prefix="/gm", tags=["gm"], dependencies=[Depends(require_roles("GM", "OWNER", "ADMIN"))])


def _src(source):
    if source and source not in ("CSV", "WALKIN"):
        raise HTTPException(400, "Unknown source")
    return source or None


@router.get("/performance")
def performance(date_from: Optional[date] = None, date_to: Optional[date] = None, branch_id: Optional[int] = None,
                pba_id: Optional[int] = None, cre_id: Optional[int] = None, model_id: Optional[int] = None,
                source: Optional[str] = None, db: Session = Depends(get_db)):
    return svc.performance(db, date_from, date_to, branch_id, pba_id, cre_id, model_id, _src(source))


@router.get("/customers")
def customers(branch_id: Optional[int] = None, pba_id: Optional[int] = None, model_id: Optional[int] = None, source: Optional[str] = None,
              booking_status: str = "ACTIVE", insurance_status: Optional[str] = None, rto_status: Optional[str] = None,
              delivery_status: Optional[str] = None, date_from: Optional[date] = None, date_to: Optional[date] = None,
              db: Session = Depends(get_db)):
    if booking_status not in ("ACTIVE", "CANCELLED"):
        raise HTTPException(400, "Unknown booking status")
    return {"rows": svc.customers(db, branch_id, pba_id, model_id, _src(source), booking_status, insurance_status or None,
                                  rto_status or None, delivery_status or None, date_from, date_to)}


@router.get("/export")
def export(date_from: Optional[date] = None, date_to: Optional[date] = None, branch_id: Optional[int] = None,
           pba_id: Optional[int] = None, cre_id: Optional[int] = None, model_id: Optional[int] = None,
           source: Optional[str] = None, db: Session = Depends(get_db)):
    from openpyxl import Workbook
    from openpyxl.styles import Font
    p = svc.performance(db, date_from, date_to, branch_id, pba_id, cre_id, model_id, _src(source))
    c = svc.customers(db, branch_id, pba_id, model_id, _src(source), date_from=date_from, date_to=date_to)
    wb = Workbook()

    def sheet(title, header, rows, first=False):
        ws = wb.active if first else wb.create_sheet()
        ws.title = title
        ws.append(header)
        for cell in ws[1]:
            cell.font = Font(bold=True)
        for r in rows:
            ws.append(r)
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = min(max(len(str(x.value or "")) for x in col) + 2, 40)
    sheet("PBA-wise", ["PBA", "Branch", "Leads", "Contacted", "SLA green", "SLA red", "SLA waiting", "SLA %", "Calls", "Overdue follow-ups", "Test rides",
                       "Test rides done", "Quotations", "Booked", "Invoiced", "Delivered", "Cancelled", "Insurance pending", "RTO pending", "Conversion %"],
          [[r["name"], r["branch"], r["leads"], r["contacted"], r["sla_green"], r["sla_red"], r["sla_wait"], r["sla_pct"], r["calls"], r["overdue_followups"],
            r["test_rides"], r["test_rides_done"], r["quotations"], r["booked"], r["invoiced"], r["delivered"], r["cancelled"], r["ins_pending"],
            r["rto_pending"], r["conversion_pct"]] for r in p["pba"]], first=True)
    sheet("CRE-wise", ["CRE", "Branches", "Total leads", "Contacted", "Calls", "Connected calls", "Pending follow-ups", "Overdue", "Test ride scheduled",
                       "Test ride completed", "Booked", "Delivered", "Lost", "Conversion %"],
          [[r["name"], ", ".join(r["branches"]), r["total"], r["contacted"], r["calls"], r["calls_connected"], r["pending"], r["overdue"], r["tr_scheduled"],
            r["tr_completed"], r["booked"], r["delivered"], r["lost"], r["conversion_pct"]] for r in p["cre"]])
    sheet("PBA vs CRE", ["Team", "Leads", "Contacted", "Calls", "Test rides", "Quotations", "Booked", "Delivered", "Conversion %"],
          [[v["team"], v["leads"], v["contacted"], v["calls"], v["test_rides"], v["quotations"], v["booked"], v["delivered"], v["conversion_pct"]] for v in p["versus"]])
    sheet("Funnel", ["Step", "Customers"], [[f["label"], f["count"]] for f in p["funnel"]])
    sheet("Bottlenecks", ["Department", "Pending item", "Count"], [[b["dept"], b["label"], b["count"]] for b in p["bottlenecks"]])
    sheet("Customers", ["Enquiry", "Customer", "Phone", "Branch", "PBA", "Model", "Source", "Stage", "Payment", "Outstanding", "Insurance", "RTO", "Delivery"],
          [[r["enquiry_no"], r["customer"], r["phone"], r["branch"], r["pba"], r["model"], r["source"], r["stage"], r["payment"], r.get("outstanding"),
            r["insurance"], r["rto"], r["delivery"]] for r in c])
    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f'attachment; filename="gm-report-{p["from"]}-{p["to"]}.xlsx"'})
