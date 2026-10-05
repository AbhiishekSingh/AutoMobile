from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.db.schema_updates import apply_schema_updates
from app.db import base  # noqa: F401  (registers all models)
from app.modules.auth.router import router as auth_router
from app.modules.users.router import router as users_router
from app.modules.users.me_router import router as me_router
from app.modules.leads.router import router as leads_router
from app.modules.imports.router import router as imports_router
from app.modules.quotations.router import router as quotations_router
from app.modules.dashboard.router import router as dashboard_router
from app.modules.notifications.router import router as notifications_router
from app.modules.audit.router import router as audit_router
from app.modules.leads.service import sync_dropdown_lists

app = FastAPI(title="S.K. Automobiles CRM — API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(me_router)
app.include_router(leads_router)
app.include_router(imports_router)
app.include_router(quotations_router)
app.include_router(dashboard_router)
app.include_router(notifications_router)
app.include_router(audit_router)


@app.on_event("startup")
def sync_lookups_on_startup():
    """Keep the Opportunity Status and Follow-up Disposition dropdowns in line
    with their fixed lists (app/modules/leads/service.py) on every start —
    creates missing values, switches the rest off. No manual step needed."""
    # 1. add any new database columns (e.g. lead.branch_code) — must run
    #    before anything reads the lead table
    try:
        apply_schema_updates(engine)
    except Exception as e:
        print(f"[startup] WARNING: database column update failed: {e}")

    # 2. fixed dropdown lists
    db = SessionLocal()
    try:
        for table, (active, off) in sync_dropdown_lists(db).items():
            print(f"[startup] {table}: {active} in dropdown, {off} switched off.")
    except Exception as e:   # never block the API from starting over this
        db.rollback()
        print(f"[startup] WARNING: could not sync dropdown lists: {e}")
    finally:
        db.close()


@app.get("/health")
def health():
    return {"status": "ok"}