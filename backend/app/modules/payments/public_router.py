"""Customer-facing "I AGREE" page — NO login; protected by a long random link.

  GET  /public/receipt/{token}            the receipt page with the I AGREE box
  GET  /public/receipt/{token}/pdf        the receipt PDF  (?lang=en|mr)
  POST /public/receipt/{token}/agree      record the acknowledgement (once)

Staff side (login needed):
  POST /payments/{payment_id}/agree-link  create / fetch the link to send to the customer
"""
import json
import secrets
from html import escape

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db, now_ist
from app.core.deps import get_current_user, require_roles
from app.modules.payments import receipt_pdf
from app.modules.payments.models import Payment
from app.modules.payments.receipt_data import receipt_bytes
from app.modules.users.access import get_visible_lead
from app.modules.users.models import AppUser

router = APIRouter(tags=["payments-public"])

TEXT = {
    "en": {"h": "Payment receipt", "intro": "Please check the details below.",
           "amt": "Amount received", "tot": "Total vehicle cost", "paid": "Total paid till date",
           "bal": "Balance outstanding", "pdf": "View / download PDF receipt",
           "agree": "I confirm that I have paid the amount shown on this receipt and the details are correct.",
           "btn": "I AGREE", "need": "Please tick the box to continue.",
           "done": "Thank you. Your acknowledgement was recorded on", "other": "मराठी"},
    "mr": {"h": "पेमेंट पावती", "intro": "कृपया खालील तपशील तपासा.",
           "amt": "स्वीकारलेली रक्कम", "tot": "वाहनाची एकूण किंमत", "paid": "आजपर्यंत भरलेली एकूण रक्कम",
           "bal": "शिल्लक रक्कम", "pdf": "पावती PDF पहा / डाउनलोड करा",
           "agree": "मी या पावतीवर दर्शवलेली रक्कम भरली असून तपशील बरोबर असल्याची खात्री देतो/देते.",
           "btn": "मी सहमत आहे", "need": "पुढे जाण्यासाठी बॉक्सवर खूण करा.",
           "done": "धन्यवाद. तुमची संमती नोंदवली गेली:", "other": "English"},
}


def _by_token(db: Session, token: str) -> Payment:
    pay = db.query(Payment).filter(Payment.agree_token == token).first() if len(token) >= 20 else None
    if not pay:
        raise HTTPException(404, "This link is not valid.")
    return pay


def _lang(lang: str) -> str:
    return "mr" if lang == "mr" and receipt_pdf.marathi_ready() else "en"


def _page(pay: Payment, entry: dict, summ: dict, token: str, lang: str, error: str = "",
          rel: str = None) -> str:
    # links are relative so they also work behind a /api proxy; `rel` is the prefix from the
    # page's own address: '<token>/' at .../receipt/<token>, '' at .../receipt/<token>/agree
    rel = f"{token}/" if rel is None else rel
    t = TEXT[lang]
    paid_till = sum(float(p["amount"]) for p in summ["payments"] if p["receipt_seq"] <= entry["receipt_seq"])
    total = float(summ["total_vehicle_cost"]) if summ["total_vehicle_cost"] is not None else None
    money = lambda v: "Rs. " + f"{v:,.2f}"
    rows = [(t["amt"], money(float(entry["amount"]))),
            (t["tot"], money(total) if total is not None else "-"),
            (t["paid"], money(paid_till)),
            (t["bal"], money(total - paid_till) if total is not None else "-")]
    rows_html = "".join(f"<tr><td>{escape(a)}</td><td><b>{escape(b)}</b></td></tr>" for a, b in rows)
    if pay.agreed_at:
        action = f'<div class="ok">{t["done"]} {pay.agreed_at.strftime("%d-%m-%Y %H:%M")}</div>'
    else:
        action = (f'<form method="post" action="{rel}agree?lang={lang}">'
                  f'<label class="chk"><input type="checkbox" name="agree" value="yes" required> {escape(t["agree"])}</label>'
                  f'{"<div class=err>" + escape(error) + "</div>" if error else ""}'
                  f'<button type="submit">{t["btn"]}</button></form>')
    other = "en" if lang == "mr" else "mr"
    sw = (f'<a class="sw" href="?lang={other}">{t["other"]}</a>'
          if (other == "en" or receipt_pdf.marathi_ready()) else "")
    return f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(entry["receipt_no"])}</title>
<style>body{{font-family:system-ui,'Noto Sans Devanagari',sans-serif;background:#f4f4f7;margin:0;padding:16px;color:#222}}
.c{{max-width:460px;margin:0 auto;background:#fff;border-radius:12px;padding:20px;box-shadow:0 2px 10px #0002}}
h1{{font-size:18px;color:#2b2560;margin:0}} .sub{{color:#666;font-size:13px;margin:2px 0 14px}}
table{{width:100%;border-collapse:collapse;margin:12px 0}} td{{padding:8px 4px;border-bottom:1px solid #eee;font-size:14px}}
td:last-child{{text-align:right}} a.pdf{{display:block;text-align:center;padding:10px;border:1px solid #2b2560;border-radius:8px;color:#2b2560;text-decoration:none;margin:12px 0}}
.chk{{display:flex;gap:10px;font-size:14px;margin:14px 0}} button{{width:100%;padding:13px;background:#f5820c;color:#fff;border:0;border-radius:8px;font-size:16px;font-weight:600}}
.ok{{background:#e6f6ea;color:#1b6b34;padding:12px;border-radius:8px;font-size:14px}} .err{{color:#b3261e;font-size:13px;margin-bottom:8px}}
.sw{{float:right;font-size:13px}}</style></head><body><div class="c">
{sw}<h1>S.K Automobiles</h1><div class="sub">{escape(t["h"])} · {escape(entry["receipt_no"])} · {entry["payment_date"].strftime("%d-%m-%Y")}</div>
<div>{escape(t["intro"])}</div><table>{rows_html}</table>
<a class="pdf" href="{rel}pdf?lang={lang}" target="_blank">{escape(t["pdf"])}</a>{action}</div></body></html>"""


@router.get("/public/receipt/{token}", response_class=HTMLResponse)
def receipt_page(token: str, lang: str = "en", db: Session = Depends(get_db)):
    pay = _by_token(db, token)
    lang = _lang(lang)
    _, entry, summ = receipt_bytes(db, pay, "en")
    return _page(pay, entry, summ, token, lang)


@router.get("/public/receipt/{token}/pdf")
def receipt_public_pdf(token: str, lang: str = "en", db: Session = Depends(get_db)):
    pay = _by_token(db, token)
    lang = _lang(lang)
    data, entry, _ = receipt_bytes(db, pay, lang)
    return Response(data, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{entry["receipt_no"]}-{lang}.pdf"'})


@router.post("/public/receipt/{token}/agree", response_class=HTMLResponse)
def receipt_agree(token: str, request: Request, lang: str = "en", agree: str = Form(""),
                  db: Session = Depends(get_db)):
    pay = _by_token(db, token)
    lang = _lang(lang)
    _, entry, summ = receipt_bytes(db, pay, "en")
    if agree != "yes":
        return HTMLResponse(_page(pay, entry, summ, token, lang, TEXT[lang]["need"], rel=""), status_code=400)
    if not pay.agreed_at:                       # first confirmation wins; repeats change nothing
        pay.agreed_at = now_ist()
        pay.agreed_ip = request.client.host if request.client else None
        pay.agreed_user_agent = (request.headers.get("user-agent") or "")[:300]
        paid_till = sum(float(p["amount"]) for p in summ["payments"] if p["receipt_seq"] <= entry["receipt_seq"])
        pay.agreed_receipt_snapshot = json.dumps({
            "receipt_no": entry["receipt_no"], "amount": float(entry["amount"]),
            "total_vehicle_cost": float(summ["total_vehicle_cost"]) if summ["total_vehicle_cost"] is not None else None,
            "paid_till_receipt": paid_till, "language": lang})
        db.commit()
    # redirect back to the normal page (so a refresh does not re-post and links stay right)
    return RedirectResponse(f"../{token}?lang={lang}", status_code=303)


@router.post("/payments/{payment_id}/agree-link",
             dependencies=[Depends(require_roles("PBA", "CRE", "OWNER", "GM", "ADMIN"))])
def make_agree_link(payment_id: int, user: AppUser = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    pay = db.get(Payment, payment_id)
    if not pay:
        raise HTTPException(404, "Payment not found")
    get_visible_lead(db, user, pay.lead_id)
    if not pay.agree_token:
        pay.agree_token = secrets.token_urlsafe(32)
        db.commit()
    return {"url": f"{settings.PUBLIC_API_URL.rstrip('/')}/public/receipt/{pay.agree_token}",
            "agreed_at": pay.agreed_at}
