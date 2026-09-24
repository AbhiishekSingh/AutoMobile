"""One-time cleanup: merge duplicate lookup values created by earlier imports.

Before the importer learned to match names loosely (see
app/modules/leads/lookup_names.py), a LeadSquared file spelling a value
differently from the seed list created a second row — e.g. "Cross-Sell" next
to "Cross Sell", or "250 Duke" next to "DUKE 250". This script finds those
groups, keeps ONE row per group, moves every lead / follow-up / test ride /
quotation onto it, and deletes the extras.

Which row is kept: the one whose name is in the seed list
(app/seeds/leads.py), otherwise the oldest (lowest id). So "CROSS SELL"
stays, "CROSS-SELL" goes, and its leads move across.

Usage (from the backend folder, same place you run uvicorn):

    python -m app.seeds.merge_duplicate_lookups            # dry run: only prints the plan
    python -m app.seeds.merge_duplicate_lookups --apply    # actually merges

Safe to run more than once — when there's nothing left to merge it says so.
Everything happens in one transaction: if anything fails, nothing changes.
"""
import sys
from collections import defaultdict

from app.core.database import SessionLocal
from app.db import base as _base  # noqa: F401  (register all models)
from app.modules.leads.lookup_names import lookup_key
from app.modules.leads.models import (BikeModel, Disposition, EnquiryMode, Lead,
                                      LeadFollowup, LostReason, OpportunityStatus,
                                      TestRide)
from app.modules.quotations.models import Quotation
from app.seeds.leads import (DISPOSITIONS, ENQUIRY_MODES, LOST_REASONS, MODELS,
                             OPPORTUNITY)

# lookup table -> (seed names, [(table, fk column), ...] that point at it)
TABLES = [
    (EnquiryMode, ENQUIRY_MODES, [(Lead, Lead.mode_id)]),
    (BikeModel, MODELS, [(Lead, Lead.model_id), (TestRide, TestRide.model_id),
                         (Quotation, Quotation.model_id)]),
    (OpportunityStatus, OPPORTUNITY, [(Lead, Lead.opportunity_status_id),
                                      (LeadFollowup, LeadFollowup.opportunity_status_id)]),
    (Disposition, DISPOSITIONS, [(Lead, Lead.current_disposition_id),
                                 (LeadFollowup, LeadFollowup.disposition_id)]),
    (LostReason, LOST_REASONS, [(Lead, Lead.lost_reason_id)]),
]


def _pick_keeper(rows, seed_names):
    seeded = {n.strip().upper() for n in seed_names}
    in_seed = [r for r in rows if (r.name or "").strip().upper() in seeded]
    return min(in_seed or rows, key=lambda r: r.id)


def run(apply: bool) -> None:
    db = SessionLocal()
    total_groups = 0
    try:
        for Model, seed_names, refs in TABLES:
            groups = defaultdict(list)
            for row in db.query(Model).all():
                k = lookup_key(row.name)
                if k:
                    groups[k].append(row)

            for rows in groups.values():
                if len(rows) < 2:
                    continue
                total_groups += 1
                keeper = _pick_keeper(rows, seed_names)
                dupes = [r for r in rows if r.id != keeper.id]
                print(f"[{Model.__tablename__}] keep '{keeper.name}' (id {keeper.id})")
                for d in dupes:
                    moved = []
                    for Table, col in refs:
                        n = db.query(Table).filter(col == d.id).update(
                            {col: keeper.id}, synchronize_session=False)
                        if n:
                            moved.append(f"{n} {Table.__tablename__}")
                    print(f"    merge '{d.name}' (id {d.id}) -> moves "
                          f"{', '.join(moved) or 'nothing'}")
                    # a merged-away row that was active keeps the keeper active
                    if hasattr(keeper, "is_active") and getattr(d, "is_active", False):
                        keeper.is_active = True
                    db.delete(d)

        if total_groups == 0:
            print("No duplicate lookup values found — nothing to do.")
            db.rollback()
            return
        if apply:
            db.commit()
            print(f"\nDone. Merged {total_groups} duplicate group(s).")
        else:
            db.rollback()
            print(f"\nDRY RUN — {total_groups} group(s) would be merged. "
                  f"Nothing was changed. Re-run with --apply to merge.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run(apply="--apply" in sys.argv)