from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db import base  # noqa: F401  (registers all models)
from app.modules.auth.router import router as auth_router
from app.modules.users.router import router as users_router
from app.modules.leads.router import router as leads_router
from app.modules.imports.router import router as imports_router

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
app.include_router(leads_router)
app.include_router(imports_router)


@app.get("/health")
def health():
    return {"status": "ok"}