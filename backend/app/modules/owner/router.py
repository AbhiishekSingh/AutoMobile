import io
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_roles
from app.modules.owner import service as svc
from app.modules.users.models import AppUser

router = APIRouter(prefix="/owner", tags=["owner"])
OWNER = Depends(require_roles("OWNER", "ADMIN"))


def _args(period, on, branch_id):
    if period not in svc.PERIODS:
        raise HTTPException(400, "Unknown period")
    return period, on or date.today(), branch_id


@router.get("/dashboard", dependencies=[OWNER])
def dashboard(period: str = "month", on: date | None = None, branch_id: int | None = None, db: Session = Depends(get_db)):
    p, a, b = _args(period, on, branch_id)
    return svc.dashboard(db, p, a, b)


@router.get("/pending", dependencies=[OWNER])
def pending(kind: str, branch_id: int | None = None, db: Session = Depends(get_db)):
    if kind not in svc.KINDS:
        raise HTTPException(400, "Unknown list")
    return {"kind": kind, "label": svc.KINDS[kind], "rows": svc.pending_list(db, kind, branch_id)}


@router.get("/dashboard/export", dependencies=[OWNER])
def export(period: str = "month", on: date | None = None, branch_id: int | None = None, db: Session = Depends(get_db)):
    from openpyxl import Workbook
    from openpyxl.styles import Font
    p, a, b = _args(period, on, branch_id)
    d = svc.dashboard(db, p, a, b)
    wb = Workbook()

    def sheet(title, header, rows, first=False):
        ws = wb.active if first else wb.create_sheet()
        ws.title = title
        ws.append(header)
        for c in ws[1]:
            c.font = Font(bold=True)
        for r in rows:
            ws.append(r)
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = min(max(len(str(c.value or "")) for c in col) + 2, 40)
    sheet("Summary", ["Measure", d["label"], d["previous_label"], "Growth %"],
          [[h["label"], h["current"], h["previous"], h["growth"]] for h in d["headline"]], first=True)
    sheet("PBA-wise", ["PBA", "Branch", "Leads", "Bookings", "Prev bookings", "Target", "Achievement %", "Invoiced", "Delivered",
                       "Collected (Rs)", "Outstanding (Rs)", "Paid", "Partly paid", "Unpaid", "Insurance done", "Insurance pending",
                       "RTO done", "RTO pending", "Test rides", "Test rides done", "Cancelled", "Conversion %"],
          [[r["name"], r["branch"], r["leads"], r["bookings"], r["bookings_prev"], r["target"], r["achievement_pct"], r["invoiced"],
            r["delivered"], r["booking_amount"], r["outstanding"], r["pay_paid"], r["pay_partial"], r["pay_pending"], r["ins_done"],
            r["ins_pending"], r["rto_done"], r["rto_pending"], r["test_rides"], r["test_rides_done"], r["cancelled"], r["conversion_pct"]]
           for r in d["pba"]])
    sheet("Branch-wise", ["Branch", "Code", "Leads", "Bookings", "Prev bookings", "Invoiced", "Delivered", "Target", "Achievement %",
                          "Vehicles in stock", "Booked stock", "Insurance pending", "RTO pending", "Invoice pending", "Delivery pending",
                          "Collected (Rs)", "Booked value (Rs)", "Outstanding (Rs)", "Paid", "Partly paid", "Unpaid", "Cancelled",
                          "Cancelled amount (Rs)"],
          [[r["name"], r["code"], r["leads"], r["bookings"], r["bookings_prev"], r["invoiced"], r["delivered"], r["target"],
            r["achievement_pct"], r["stock_vehicles"], r["booked_stock"], r["ins_pending"], r["rto_pending"], r["invoice_pending"],
            r["delivery_pending"], r["booking_amount"], r["booked_value"], r["outstanding"], r["pay_paid"], r["pay_partial"],
            r["pay_pending"], r["cancelled"], r["cancelled_amount"]] for r in d["branches"]])
    sheet("Model-wise", ["Model", "Bookings", "Invoiced", "Delivered"], [[r["model"], r["bookings"], r["invoiced"], r["delivered"]] for r in d["models"]])
    sheet("Stock", ["Type", "Item", "Closing stock", "Warehouse", "Received", "Allocated", "Transferred", "Issued", "Count difference"],
          [[r["kind"], r["label"], r["closing"], r["warehouse"], r["received"], r["allocated"], r["transferred"], r["issued"], r["count_diff"]]
           for r in d["stock"]["items"]])
    for k, lab in svc.KINDS.items():
        rows = svc.pending_list(db, k, b)
        sheet(lab[:31], ["Enquiry", "Customer", "Phone", "Branch", "PBA", "Stage", "Detail"],
              [[r["enquiry_no"], r["customer"], r["phone"], r["branch"], r["pba"], r["stage"], r["detail"]] for r in rows])
    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    name = f"owner-report-{p}-{d['start']}.xlsx"
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f'attachment; filename="{name}"'})
