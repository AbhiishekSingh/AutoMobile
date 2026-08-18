# S.K. Automobiles CRM

Real application (not prototype). React (Vite) + FastAPI + PostgreSQL.
Modular **package-by-feature** structure so the project scales cleanly as more
modules (CRE, RTO, quotations, delivery, reports) are added.

## Folder structure

```
skcrm/
├─ backend/
│  └─ app/
│     ├─ core/            # cross-cutting: config, database, security, deps
│     │  ├─ config.py       # settings (.env)
│     │  ├─ database.py     # engine, SessionLocal, Base, get_db
│     │  ├─ security.py     # password hashing + JWT create/decode
│     │  └─ deps.py         # get_current_user, require_roles (RBAC)
│     ├─ db/
│     │  └─ base.py         # imports every model so metadata is complete
│     ├─ modules/         # one package per feature (self-contained)
│     │  ├─ auth/           # login / refresh / me
│     │  │  ├─ router.py
│     │  │  └─ schemas.py
│     │  ├─ users/          # user model + admin user management
│     │  │  ├─ models.py     # Role, Branch, AppUser
│     │  │  ├─ schemas.py
│     │  │  └─ router.py
│     │  └─ leads/          # PBA: leads, followups, test rides, dashboard
│     │     ├─ models.py     # Customer, Lead, LeadFollowup, TestRide, lookups
│     │     ├─ schemas.py
│     │     ├─ service.py    # mask_phone, scope, bucket_filter helpers
│     │     └─ router.py
│     ├─ seeds/           # data seeding scripts
│     │  ├─ users.py        # 6 branches + 6 role users
│     │  └─ leads.py        # lookups + sample leads
│     └─ main.py          # FastAPI app, mounts module routers
│  ├─ requirements.txt
│  └─ .env.example
└─ frontend/
   └─ src/
      ├─ lib/             # shared: api client, auth context
      │  ├─ api.js          # axios + auto refresh on 401
      │  └─ auth.jsx        # AuthProvider, useAuth, ROLE_HOME
      ├─ components/       # shared UI (Layout, ProtectedRoute)
      ├─ features/         # one folder per feature (mirrors backend modules)
      │  ├─ auth/           # LoginPage
      │  ├─ admin/          # UsersPage
      │  ├─ home/           # RoleHome (per-role landing)
      │  ├─ dashboard/      # (PBA dashboard — phase 2)
      │  └─ leads/          # (leads screens — phase 2)
      ├─ styles/
      ├─ App.jsx
      └─ main.jsx
```

## Backend — run (Windows PowerShell)

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env      # then edit DATABASE_URL / JWT_SECRET
python -m app.seeds.users   # branches + users
python -m app.seeds.leads   # lookups + sample leads
uvicorn app.main:app --reload
```

`.env` example:
```
DATABASE_URL=postgresql+psycopg2://postgres:YOUR_PASSWORD@localhost:5432/skcrm
JWT_SECRET=change-me
CORS_ORIGINS=http://localhost:5173
```

## Frontend — run

```powershell
cd frontend
npm install
npm run dev
```

## Logins (seeded)

| Role  | Login ID | Password |
|-------|----------|----------|
| Owner | OWNER    | owner123 |
| GM    | GM-001   | gm123    |
| PBA   | PBA-014  | pba123   |
| CRE   | CRE-003  | cre123   |
| RTO   | RTO-001  | rto123   |
| Admin | ADMIN    | admin123 |

## Notes

- **Imports are absolute** (`from app.core...`, `from app.modules...`) so scripts
  run as modules (`python -m app.seeds.users`) and files can move without breaking
  relative paths.
- Adding a new module = new folder under `modules/`, add its models to `db/base.py`,
  mount its router in `main.py`. Frontend mirror = new folder under `features/`.
- RBAC is enforced on the backend via `require_roles(...)` on each endpoint; the
  frontend `ProtectedRoute` is UX only.
```
