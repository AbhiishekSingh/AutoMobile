"""Bulk stock upload (CSV / Excel): add items, add stock, or set stock to the numbers in a file.

One file, one row per item per place:
    Type | Name | Variant | Color | Location | Quantity | Reference | Note

Modes
  items  create the items only (Quantity ignored)
  add    Quantity is added to the place: warehouse -> "received at warehouse", showroom -> "received at showroom"
  set    the place is set to Quantity (a physical-count entry: the difference shows in the discrepancy report)

Every row is checked first (preview). Nothing is saved unless the whole file is clean.
"""
import csv
import io

from fastapi import HTTPException
from openpyxl import Workbook, load_workbook
from sqlalchemy.orm import Session

from app.modules.stock import service as svc
from app.modules.stock.models import StockItem, StockKind
from app.modules.users.models import Branch

MAX_ROWS = 2000
COLUMNS = ["Type", "Name", "Variant", "Color", "Location", "Quantity", "Reference", "Note"]
ALIASES = {
    "type": "type", "kind": "type", "category": "type",
    "name": "name", "model": "name", "item": "name",
    "variant": "variant", "size": "variant",
    "color": "color", "colour": "color",
    "location": "location", "showroom": "location", "branch": "location", "place": "location",
    "quantity": "qty", "qty": "qty", "stock": "qty",
    "reference": "reference", "challan": "reference", "ref": "reference",
    "note": "note", "notes": "note", "remark": "note",
}
KIND_WORDS = {"vehicle": "VEHICLE", "vehicles": "VEHICLE", "bike": "VEHICLE", "bikes": "VEHICLE",
              "helmet": "HELMET", "helmets": "HELMET",
              "parking cover": "PARKING_COVER", "parking covers": "PARKING_COVER", "cover": "PARKING_COVER",
              "covers": "PARKING_COVER", "parking_cover": "PARKING_COVER"}
KIND_LABEL = {"VEHICLE": "Vehicle", "HELMET": "Helmet", "PARKING_COVER": "Parking cover"}


def _s(v):
    return "" if v is None else str(v).strip()


# ---------- reading the file ----------
def read_rows(filename: str, content: bytes):
    """-> list of (line_no, {type,name,variant,color,location,qty,reference,note})"""
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(400, "The file is larger than 5 MB")
    low = (filename or "").lower()
    if low.endswith(".xlsx") or low.endswith(".xlsm"):
        try:
            wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            raw = [list(r) for r in wb.worksheets[0].iter_rows(values_only=True)]
        except Exception:
            raise HTTPException(400, "Could not read this Excel file. Save it as .xlsx and try again")
    elif low.endswith(".csv"):
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = content.decode("latin-1")
        raw = [list(r) for r in csv.reader(io.StringIO(text))]
    else:
        raise HTTPException(400, "Upload a .xlsx or .csv file (old .xls files: save as .xlsx first)")
    raw = [r for r in raw if any(_s(c) for c in r)]
    if not raw:
        raise HTTPException(400, "The file is empty")
    head = [ALIASES.get(_s(h).lower().replace("_", " ")) or ALIASES.get(_s(h).lower()) for h in raw[0]]
    missing = [c for c in ("type", "name") if c not in head]
    if missing:
        raise HTTPException(400, "The first row must be the column names. Missing: " + ", ".join(m.title() for m in missing)
                            + ". Download the template to see the format")
    out = []
    for n, r in enumerate(raw[1:], start=2):
        d = {k: "" for k in ("type", "name", "variant", "color", "location", "qty", "reference", "note")}
        for i, key in enumerate(head):
            if key and i < len(r):
                d[key] = _s(r[i])
        out.append((n, d))
    if len(out) > MAX_ROWS:
        raise HTTPException(400, f"Too many rows ({len(out)}). Upload at most {MAX_ROWS} rows at a time")
    return out


def _qty(v):
    if v == "":
        return None
    try:
        f = float(v.replace(",", ""))
    except ValueError:
        raise ValueError(f"Quantity '{v}' is not a number")
    if f != int(f) or f < 0:
        raise ValueError("Quantity must be a whole number, 0 or more")
    return int(f)


def _place(db_branches, text):
    """'' / warehouse -> (None, 'Warehouse'); else branch id by name, short name or dealer code."""
    t = text.strip().lower()
    if t in ("", "warehouse", "wh", "main warehouse"):
        return None, "Warehouse"
    for b in db_branches:
        short = b.name.lower().replace("s.k ktm ", "").replace("sk ktm ", "").strip()
        if t in (b.name.lower(), short, (b.dealer_code or "").lower()):
            return b.branch_id, b.name
    hits = [b for b in db_branches if t in b.name.lower()]
    if len(hits) == 1:
        return hits[0].branch_id, hits[0].name
    raise ValueError(f"Unknown location '{text}'. Use Warehouse or a showroom name from the Branches list")


# ---------- running it ----------
def process(db: Session, user, filename: str, content: bytes, mode: str, apply: bool, ref_default: str):
    if mode not in ("items", "add", "set"):
        raise HTTPException(400, "Choose what to do with the file")
    rows = read_rows(filename, content)
    branches = db.query(Branch).filter(Branch.is_active == True).all()  # noqa: E712
    results, errors = [], 0
    counts = {"items_new": 0, "items_existing": 0, "stock_changed": 0, "unchanged": 0}
    for line, d in rows:
        res = {"line": line, "item": " · ".join(x for x in (d["name"], d["variant"], d["color"]) if x) or "—", "place": "", "action": "", "status": "ok", "message": ""}
        try:
            kind = KIND_WORDS.get(d["type"].lower().replace("-", " "))
            if not kind:
                raise ValueError(f"Type '{d['type']}' is not Vehicle, Helmet or Parking cover")
            if not d["name"]:
                raise ValueError("Name is empty")
            res["item"] = f"{KIND_LABEL[kind]} – {res['item']}"
            qty = _qty(d["qty"]) if mode != "items" else None
            if mode in ("add", "set") and qty is None:
                raise ValueError("Quantity is empty")
            if mode == "add" and qty == 0:
                raise ValueError("Quantity to add must be above zero")
            bid, pname = _place(branches, d["location"]) if mode != "items" else (None, "")
            res["place"] = pname
            # the item
            item = db.query(StockItem).filter(StockItem.kind == kind, StockItem.name == d["name"],
                                              StockItem.variant == d["variant"], StockItem.color == d["color"]).first()
            if item is None:
                item = StockItem(kind=kind, name=d["name"], variant=d["variant"], color=d["color"]); db.add(item); db.flush()
                counts["items_new"] += 1; res["action"] = "New item"
            else:
                if not item.is_active:
                    item.is_active = True; counts["items_new"] += 1; res["action"] = "Item brought back"
                else:
                    counts["items_existing"] += 1; res["action"] = "Item exists"
            if mode == "add":
                svc.record(db, user, {"item_id": item.id, "move_type": "RECEIVE" if bid is None else "RECEIPT",
                                      "to_branch_id": bid, "qty": qty, "reference": d["reference"] or ref_default, "note": d["note"] or None})
                counts["stock_changed"] += 1; res["action"] += f" · add {qty}"
            elif mode == "set":
                try:
                    svc.record(db, user, {"item_id": item.id, "move_type": "COUNT", "to_branch_id": bid, "counted_qty": qty,
                                          "reference": d["reference"] or ref_default, "note": d["note"] or "Set from bulk upload"})
                    counts["stock_changed"] += 1; res["action"] += f" · set to {qty}"
                except HTTPException as e:
                    if "matches the system" in str(e.detail):
                        counts["unchanged"] += 1; res["action"] += f" · already {qty}"
                    else:
                        raise
        except ValueError as e:
            res["status"], res["message"] = "error", str(e); errors += 1
        except HTTPException as e:
            res["status"], res["message"] = "error", str(e.detail); errors += 1
        results.append(res)
    applied = bool(apply and errors == 0)
    if applied:
        db.commit()
    else:
        db.rollback()
    return {"applied": applied, "preview": not apply, "rows": len(rows), "errors": errors, "counts": counts, "results": results}


# ---------- template / export ----------
def _book(rows, sheet="Stock"):
    wb = Workbook(); ws = wb.active; ws.title = sheet
    ws.append(COLUMNS)
    for r in rows:
        ws.append(r)
    for col, w in zip("ABCDEFGH", (16, 22, 18, 16, 22, 10, 18, 30)):
        ws.column_dimensions[col].width = w
    buf = io.BytesIO(); wb.save(buf)
    return buf.getvalue()


def template_xlsx():
    return _book([["Vehicle", "390 DUKE", "Std", "Orange", "Warehouse", 10, "Challan 1234", "Opening stock"],
                  ["Vehicle", "390 DUKE", "Std", "Orange", "Thane", 3, "", ""],
                  ["Helmet", "Touring helmet", "L", "Black", "Warehouse", 25, "", ""],
                  ["Parking cover", "KTM cover", "", "", "Warehouse", 40, "", ""]])


def template_csv():
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(COLUMNS)
    w.writerows([["Vehicle", "390 DUKE", "Std", "Orange", "Warehouse", 10, "Challan 1234", "Opening stock"],
                 ["Vehicle", "390 DUKE", "Std", "Orange", "Thane", 3, "", ""],
                 ["Helmet", "Touring helmet", "L", "Black", "Warehouse", 25, "", ""],
                 ["Parking cover", "KTM cover", "", "", "Warehouse", 40, "", ""]])
    return buf.getvalue().encode("utf-8-sig")


def export_xlsx(db: Session):
    """Current stock in the upload format (one row per item per place) - edit the Quantity column and upload with 'Set'."""
    items = db.query(StockItem).filter(StockItem.is_active == True).order_by(StockItem.kind, StockItem.name, StockItem.variant).all()  # noqa: E712
    bal, _, _ = svc.balances(db)
    branches = db.query(Branch).filter(Branch.is_active == True).order_by(Branch.name).all()  # noqa: E712
    rows = []
    for i in items:
        b = bal[i.id]
        rows.append([KIND_LABEL[i.kind], i.name, i.variant, i.color, "Warehouse", b.get(None, 0), "", ""])
        for br in branches:
            rows.append([KIND_LABEL[i.kind], i.name, i.variant, i.color, br.name, b.get(br.branch_id, 0), "", ""])
    return _book(rows, "Current stock")
