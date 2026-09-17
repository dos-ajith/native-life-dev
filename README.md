# Native Life API

Backend API serving the Native Life mobile application and web admin panel.

> This README grows alongside the project. Sections marked *(pending)* will
> be filled in as later phases land.

## Architecture

Modular monolith — one deployable service, internally split into isolated
modules (auth, users, and future modules like products/orders), each with
its own router, schemas, service, and repository. No microservices, no
message brokers, no premature distributed-systems complexity.

Layering per module:

```
Router (app/api/v1/...)     -- HTTP in/out, thin
    -> Schema (app/schemas) -- request/response validation (Pydantic)
    -> Service (app/services)     -- business logic
    -> Repository (app/repositories) -- persistence queries
    -> Model (app/models)   -- SQLAlchemy ORM table definitions
    -> PostgreSQL
```

If you've worked with Laravel: Router ≈ Controller, Schema ≈
FormRequest/API Resource, Service ≈ Service class, Repository ≈ Repository
pattern, Model ≈ Eloquent Model, Alembic ≈ Laravel Migrations.

## Tech stack

- Python 3.12, FastAPI, Pydantic v2
- PostgreSQL, SQLAlchemy 2.x, Alembic
- JWT auth (PyJWT), Argon2 password hashing
- pytest, Ruff, mypy

## Project structure

```
app/
    core/         # config, database, security, logging, exceptions (cross-module)
    api/v1/       # versioned routers, grouped by module (auth/, users/, admin/)
    models/       # SQLAlchemy ORM models
    schemas/      # Pydantic request/response schemas
    repositories/ # database query logic
    services/     # business logic
    utils/        # small shared helpers
migrations/       # Alembic migrations (committed to git)
tests/
    unit/         # no database/network
    integration/  # hits a real (test) database
scripts/          # one-off dev/ops scripts
```

## Local setup

### Prerequisites

- Python 3.12+ (`py -V:3.12`)
- PostgreSQL running locally (or via Docker later)

### 1. Virtual environment

```powershell
py -V:3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
pip install -e ".[dev]"
```

### 3. Environment variables

```powershell
Copy-Item .env.example .env
```

Then edit `.env` — at minimum set `DATABASE_URL` to point at your local
Postgres database, and `JWT_SECRET_KEY` to a random value (generate one
with `python -c "import secrets; print(secrets.token_urlsafe(64))"`).

| Variable | Purpose |
|---|---|
| `APP_NAME` | Display name, used in docs/logs |
| `APP_ENV` | `local` / `staging` / `production` |
| `DEBUG` | Verbose errors, docs enabled, etc. |
| `API_V1_PREFIX` | Base path for v1 routes, e.g. `/api/v1` |
| `DATABASE_URL` | `postgresql+psycopg://user:pass@host:port/dbname` |
| `JWT_SECRET_KEY` | Signing secret for access tokens — never commit a real value |
| `JWT_ALGORITHM` | JWT signing algorithm (default `HS256`) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime |
| `CORS_ORIGINS` | JSON array of allowed origins for the admin panel |

### 4. Run the app

```powershell
uvicorn app.main:app --reload
```

Visit `http://127.0.0.1:8000/api/v1/health` (should return `{"status":"ok"}`)
and `http://127.0.0.1:8000/docs` for interactive API docs.

### 5. Database & migrations *(pending — Phase 3/4)*

### 6. Docker *(pending — Phase 3, optional for local dev)*

## Testing

```powershell
pytest
```

Full fixture/test-database setup lands in Phase 8 — for now, tests rely on
your local `.env` being populated (see below for a known gap).

## Linting & type checking

```powershell
ruff check .
mypy app
```

## How to add a new module *(pending — filled in once Users module exists)*
