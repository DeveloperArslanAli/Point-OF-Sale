# Run Full Stack (Backend + POS + SuperAdmin)

**Prereqs**
- Python 3.11+, Poetry, Git, and Docker Desktop running.
- Ports: API 8000, POS 8080, SuperAdmin 8081, Postgres 5432, Redis 6379 (if enabled).
- Windows users: run PowerShell scripts with `./scripts/<name>.ps1`; macOS/Linux use `./scripts/<name>.sh`.

**1) Start infrastructure (Postgres/Redis/API container)**
- From repo root: `./scripts/dev_env_up.ps1` (or `./scripts/dev_env_up.sh`).
- Wait until Postgres and the backend container report healthy; stop later with `./scripts/dev_env_down.ps1`.

**2) Backend API (FastAPI)**
- Copy [backend/.env.example](backend/.env.example) to `backend/.env.local` and set `DATABASE_URL`, `JWT_SECRET_KEY`, `ALLOWED_HOSTS`, and `CORS_ORIGINS`.
- Install deps: `cd backend` then `py -m poetry install`.
- Apply migrations/seed admin: `./scripts/db_bootstrap.ps1` (or run `py -m poetry run alembic upgrade head`).
- Run API: `py -m poetry run uvicorn app.api.main:app --reload --port 8000`.

**3) POS client (modern_client)**
- Create `modern_client/.env` (dotenv is loaded automatically):
  ```
  API_BASE_URL=http://localhost:8000/api/v1
  TERMINAL_ID=POS-1
  ```
- Install deps: `cd modern_client` then `py -m poetry install`.
- Launch POS: `py -m poetry run python main.py` (opens on port 8080 by default).
- After login, if you see "No active shift" in the header, click the Start Shift icon to open one; the message is expected until a shift exists.
- If session restore misbehaves, remove the cached tokens at [modern_client/.auth_tokens.json](modern_client/.auth_tokens.json) and log in again.

**4) SuperAdmin portal (super_admin_client)**
- Install deps: `cd super_admin_client` then `py -m poetry install`.
- Launch portal: `py -m poetry run python main.py` (opens on port 8081 in the browser view).

**Troubleshooting quick hits**
- Backend refuses to start: confirm `DATABASE_URL` points to the Compose Postgres (typically `postgresql+asyncpg://postgres:1234@localhost:5432/retail_pos`).
- POS shows drawer closed: use the drawer icon to open one for the terminal.
- API auth errors: ensure the admin seed ran (via db_bootstrap) and the POS client `API_BASE_URL` matches the running backend.
