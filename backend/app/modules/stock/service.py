"""Stock rules: balances come from movements; negative stock is refused."""
from collections import defaultdict

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.stock.models import MOVE_TYPES, StockItem, StockKind, StockMovement
from app.modules.users.models import Branch, Role

WH = None   # warehouse = branch_id NULL


def _effects(m):
    """[(place, signed qty)] for a movement. place = branch_id or None (warehouse)."""
    t, q = m.move_type, m.qty
    if t == "RECEIVE":
        return [(None, q)]
    if t == "ALLOCATE":
        return [(None, -q), (m.to_branch_id, q)]
    if t == "TRANSFER":
        return [(m.from_branch_id, -q), (m.to_branch_id, q)]
    if t == "RECEIPT":
        return [(m.to_branch_id, q)]
    if t == "ISSUE":
        return [(m.from_branch_id, -q)]
    if t == "COUNT":
        return [(m.to_branch_id, q)]     # q is signed; place in to_branch_id (None = warehouse)
    return []


def balances(db: Session, item_id=None):
    """{item_id: {place: qty}} plus totals received/issued per item."""
    qy = db.query(StockMovement)
    if item_id:
        qy = qy.filter(StockMovement.item_id == item_id)
    bal = defaultdict(lambda: defaultdict(int))
    recv = defaultdict(int)
    issued = defaultdict(int)
    for m in qy.all():
        for place, d in _effects(m):
            bal[m.item_id][place] += d
        if m.move_type in ("RECEIVE", "RECEIPT"):
            recv[m.item_id] += m.qty
        if m.move_type == "ISSUE":
            issued[m.item_id] += m.qty
    return bal, recv, issued


def _name(db, place):
    if place is None:
        return "Warehouse"
    b = db.get(Branch, place)
    return b.name if b else f"Branch {place}"


def record(db: Session, user, d: dict) -> StockMovement:
    t = (d.get("move_type") or "").upper()
    if t not in MOVE_TYPES:
        raise HTTPException(400, "Unknown stock action")
    item = db.get(StockItem, d.get("item_id"))
    if not item or not item.is_active:
        raise HTTPException(400, "Pick a stock item")
    is_owner = user.role in (Role.OWNER, Role.ADMIN)
    own = set(user.branch_ids or ([user.branch_id] if user.branch_id else []))
    frm, to = d.get("from_branch_id"), d.get("to_branch_id")
    qty = d.get("qty")
    if t != "COUNT":
        if not isinstance(qty, int) or qty <= 0:
            raise HTTPException(400, "Quantity must be a whole number above zero")
    # who may do what
    if t in ("RECEIVE", "ALLOCATE", "TRANSFER") and not is_owner:
        raise HTTPException(403, "Only the Owner can receive into the warehouse, allocate or transfer stock")
    if user.role == Role.GM:
        place = to if t in ("RECEIPT", "COUNT") else frm if t == "ISSUE" else None
        if t not in ("RECEIPT", "ISSUE", "COUNT") or place not in own:
            raise HTTPException(403, "The GM can record receipts, issues and counts for their own showroom only")
    elif not is_owner:
        raise HTTPException(403, "Not allowed")
    # shape
    if t == "ALLOCATE":
        frm = None
        if not to: raise HTTPException(400, "Choose the showroom to allocate to")
    if t == "TRANSFER":
        if not frm or not to or frm == to: raise HTTPException(400, "Choose two different showrooms")
    if t == "RECEIPT" and not to: raise HTTPException(400, "Choose the showroom")
    if t == "ISSUE" and not frm: raise HTTPException(400, "Choose the showroom")
    if t == "RECEIVE": frm = to = None
    if t in ("RECEIPT", "ISSUE", "TRANSFER", "ALLOCATE"):
        for bid in (frm, to):
            if bid and not db.get(Branch, bid): raise HTTPException(400, "Unknown showroom")
    bal, _, _ = balances(db, item.id)
    cur = bal[item.id]
    if t == "COUNT":
        counted = d.get("counted_qty")
        if not isinstance(counted, int) or counted < 0:
            raise HTTPException(400, "Enter the counted quantity (0 or more)")
        place = to
        qty = counted - cur.get(place, 0)
        if qty == 0:
            raise HTTPException(400, "Counted quantity matches the system - nothing to record")
        d["counted_qty"] = counted
        if not (d.get("note") or "").strip():
            raise HTTPException(400, "Add a note explaining the difference")
    else:
        src = frm if t in ("TRANSFER", "ISSUE") else (None if t == "ALLOCATE" else "x")
        if src != "x" and cur.get(src, 0) < qty:
            raise HTTPException(400, f"Only {cur.get(src, 0)} available at {_name(db, src)} - stock cannot go below zero")
    m = StockMovement(item_id=item.id, move_type=t, from_branch_id=frm, to_branch_id=to, qty=qty,
                      counted_qty=d.get("counted_qty"), reference=(d.get("reference") or "").strip() or None,
                      received_by=(d.get("received_by") or "").strip() or None,
                      note=(d.get("note") or "").strip() or None, by_user_id=user.user_id)
    db.add(m); db.flush()
    return m


def item_dict(i): return {"id": i.id, "kind": i.kind, "name": i.name, "variant": i.variant, "color": i.color,
                          "label": " · ".join(x for x in (i.name, i.variant, i.color) if x)}


def summary(db: Session, branch_ids=None):
    """branch_ids None = whole dealership (incl. warehouse); list = just those showrooms."""
    items = db.query(StockItem).filter(StockItem.is_active == True).order_by(StockItem.kind, StockItem.name).all()  # noqa: E712
    bal, recv, issued = balances(db)
    branches = {b.branch_id: b.name for b in db.query(Branch).filter(Branch.is_active == True).all()}  # noqa: E712
    show = list(branches) if branch_ids is None else [b for b in branch_ids if b in branches]
    kinds = {k.value: {"available_total": 0, "warehouse": 0, "allocated": 0, "received": 0, "issued": 0} for k in StockKind}
    rows, per_branch = [], {b: {k.value: 0 for k in StockKind} for b in show}
    for i in items:
        b = bal[i.id]
        at = {bid: b.get(bid, 0) for bid in show}
        wh = b.get(None, 0) if branch_ids is None else 0
        k = kinds[i.kind]
        k["available_total"] += sum(at.values()) + wh
        k["warehouse"] += wh
        k["allocated"] += sum(at.values())
        if branch_ids is None:
            k["received"] += recv[i.id]; k["issued"] += issued[i.id]
        for bid, q in at.items(): per_branch[bid][i.kind] += q
        rows.append({**item_dict(i), "warehouse": wh, "by_branch": at, "total": sum(at.values()) + wh,
                     "received": recv[i.id] if branch_ids is None else None,
                     "issued": issued[i.id] if branch_ids is None else None})
    return {"kinds": kinds, "items": rows, "branches": [{"id": b, "name": branches[b], **per_branch[b]} for b in show]}
