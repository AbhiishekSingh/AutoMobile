"""Customer-facing delivery receipt page — NO login, protected by a long random link.

  GET  /public/delivery/{token}        review the receipt, tick and press I AGREE
  GET  /public/delivery/{token}/pdf    the receipt PDF (the accepted copy once accepted)
  POST /public/delivery/{token}/agree  record the acknowledgement (once)
"""
from html import escape

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.documents import service as docs
from app.modules.documents.models import CustomerDocument
from app.modules.handoffs import delivery as dlv
from app.modules.handoffs.delivery_pdf import ACK_TEXT
from app.modules.handoffs.models import DeliveryRecord
from app.modules.leads.models import Lead

router = APIRouter(tags=["delivery-public"])


def _rec(db: Session, token: str) -> DeliveryRecord:
    rec = db.query(DeliveryRecord).filter(DeliveryRecord.ack_token == token).first() if len(token) >= 20 else None
    if not rec or not rec.generated_at:
        raise HTTPException(404, "This link is not valid.")
    return rec


def _page(db, rec, lead, token, rel=None, error="") -> str:
    rel = f"{token}/" if rel is None else rel       # links are relative so they work behind /api
    d = dlv.delivery_data(db, lead, rec)
    rows = [("Receipt no.", d["receipt_no"]), ("Customer", d["customer_name"]), ("Mobile", d["mobile"]),
            ("Vehicle", f'{d["model"] or ""} {d["color"] or ""}'.strip() or "-"), ("Chassis no.", d["chassis_no"]),
            ("Engine no.", d["engine_no"]), ("Registration no.", d["registration_no"] or "-"),
            ("Delivery date", d["delivery_date"].strftime("%d-%m-%Y")),
            ("Total amount paid", f'Rs. {d["total_paid"]:,.2f}'), ("Outstanding", f'Rs. {d["outstanding"]:,.2f}')]
    trs = "".join(f"<tr><td>{escape(a)}</td><td><b>{escape(str(b))}</b></td></tr>" for a, b in rows)
    if rec.agreed_at:
        action = f'<div class="ok">Thank you. Your acknowledgement was recorded on {rec.agreed_at:%d-%m-%Y %H:%M}.</div>'
    else:
        action = (f'<form method="post" action="{rel}agree"><label class="chk"><input type="checkbox" name="agree" value="yes" required> '
                  f'{escape(ACK_TEXT)}</label>{"<div class=err>" + escape(error) + "</div>" if error else ""}'
                  f'<button type="submit">I AGREE</button></form>')
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(d["receipt_no"])}</title>
<style>body{{font-family:system-ui,sans-serif;background:#f4f4f7;margin:0;padding:16px;color:#222}}
.c{{max-width:480px;margin:0 auto;background:#fff;border-radius:12px;padding:20px;box-shadow:0 2px 10px #0002}}
h1{{font-size:18px;color:#2b2560;margin:0 0 2px}}.sub{{color:#666;font-size:13px;margin-bottom:12px}}
table{{width:100%;border-collapse:collapse;margin:10px 0}}td{{padding:7px 4px;border-bottom:1px solid #eee;font-size:14px}}td:last-child{{text-align:right}}
a.pdf{{display:block;text-align:center;padding:10px;border:1px solid #2b2560;border-radius:8px;color:#2b2560;text-decoration:none;margin:12px 0}}
.chk{{display:flex;gap:10px;font-size:14px;margin:14px 0}}button{{width:100%;padding:13px;background:#f5820c;color:#fff;border:0;border-radius:8px;font-size:16px;font-weight:600}}
.ok{{background:#e6f6ea;color:#1b6b34;padding:12px;border-radius:8px;font-size:14px}}.err{{color:#b3261e;font-size:13px;margin-bottom:8px}}</style></head>
<body><div class="c"><h1>S.K Automobiles</h1><div class="sub">Bike delivery receipt</div><table>{trs}</table>
<a class="pdf" href="{rel}pdf" target="_blank">View / download the full delivery receipt (PDF)</a>{action}</div></body></html>"""


@router.get("/public/delivery/{token}", response_class=HTMLResponse)
def delivery_page(token: str, db: Session = Depends(get_db)):
    rec = _rec(db, token)
    return _page(db, rec, db.get(Lead, rec.lead_id), token)


@router.get("/public/delivery/{token}/pdf")
def delivery_public_pdf(token: str, db: Session = Depends(get_db)):
    rec = _rec(db, token)
    doc = db.get(CustomerDocument, rec.accepted_doc_id) if rec.accepted_doc_id else None
    if doc:
        return FileResponse(docs.full_path_of(doc.stored_path), media_type="application/pdf",
                            filename=doc.original_name, content_disposition_type="inline")
    return Response(dlv.make_pdf(db, db.get(Lead, rec.lead_id), rec), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{rec.receipt_no}.pdf"'})


@router.post("/public/delivery/{token}/agree", response_class=HTMLResponse)
def delivery_agree(token: str, request: Request, agree: str = Form(""), db: Session = Depends(get_db)):
    rec = _rec(db, token)
    lead = db.get(Lead, rec.lead_id)
    if agree != "yes":
        return HTMLResponse(_page(db, rec, lead, token, rel="", error="Please tick the box to continue."), status_code=400)
    try:
        dlv.accept(db, lead, rec, request.client.host if request.client else None, request.headers.get("user-agent"))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return RedirectResponse(f"../{token}", status_code=303)
