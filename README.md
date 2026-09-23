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
    api/v1/       # versioned routers, grouped by module (auth/, users/, admin/, ai/, posts/, ...)
    ai/           # centralized AI integration layer (see "AI integration" below)
        client.py     # provider-specific SDK calls (OpenAI Responses / Groq Chat Completions)
        service.py    # orchestrates the client + tool registry + activity logging
        exceptions.py # AI-specific AppError subclasses
        tools/        # read-only tool definitions, calling existing services only
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

### AI integration

The AI layer never touches the database directly. A request flows:

```
Router (app/api/v1/ai/routes.py)
    -> AIService (app/ai/service.py)
        -> AIClient (app/ai/client.py)            -- talks to the provider SDK
        -> AIToolRegistry (app/ai/tools/registry.py)
            -> AITool (app/ai/tools/post_tools.py) -- validates args, calls...
                -> existing domain Service (PostService, PostCommentService, ...)
                    -> Repository -> PostgreSQL
```

Tools are read-only for now (`get_post`, `search_posts`, `get_post_comments`,
`get_post_tags`, `get_user_posts`). Every tool call still goes through normal
authorization — the AI is never trusted as an authorization authority.

The provider is swappable via `AI_PROVIDER` in `.env` without touching any
other layer:

- `openai` (default) — OpenAI's Responses API, via `OPENAI_API_KEY`.
- `groq` — Groq's OpenAI-compatible Chat Completions API, via `GROQ_API_KEY`.
  Handy for local/dev testing without OpenAI credits (Groq has a free tier).
  Set `AI_MODEL` to a Groq-hosted model (e.g. `llama-3.3-70b-versatile`) when
  using this provider.

If neither key is configured for the selected provider, `/api/v1/ai/ask`
returns a 503 rather than the app failing to start.

## Local setup

### Prerequisites

- Python 3.12+ (`py -V:3.12`)
- PostgreSQL running locally (or via Docker later)

### 1. Virtual environment

**Windows (PowerShell)**
```powershell
py -V:3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
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
| `AI_PROVIDER` | `openai` or `groq` — see "AI integration" above |
| `AI_MODEL` | Model name for the selected provider |
| `OPENAI_API_KEY` | Required when `AI_PROVIDER=openai`; leave unset to disable AI |
| `GROQ_API_KEY` | Required when `AI_PROVIDER=groq`; leave unset to disable AI |
| `GROQ_BASE_URL` | Groq's OpenAI-compatible base URL (default is correct as-is) |

### 4. Run the app

```powershell
uvicorn app.main:app --reload
```

Visit `http://127.0.0.1:8000/api/v1/health` (should return `{"status":"ok"}`)
and `http://127.0.0.1:8000/docs` for interactive API docs.

### 5. Database

Create a local database and user matching your `.env`'s `DATABASE_URL`:

```sql
CREATE USER nativelife WITH PASSWORD 'change-me-locally';
CREATE DATABASE nativelife_dev OWNER nativelife;
```

Check connectivity from the app itself:
```
GET http://127.0.0.1:8000/api/v1/health/ready  -> {"status": "ok"}
```

### 6. Migrations (Alembic)

Apply the latest schema to your database:
```powershell
alembic upgrade head
```

Common commands:
```powershell
alembic revision --autogenerate -m "add products table"   # generate a migration after changing models
alembic upgrade head                                        # apply all pending migrations
alembic downgrade -1                                         # roll back the most recent migration
alembic current                                              # show which migration is applied
alembic check                                                 # confirm models match the latest migration (no drift)
```

Alembic ≈ Laravel's migration system, with one key difference: `--autogenerate`
diffs your SQLAlchemy models against the live database schema and writes the
migration for you — Laravel migrations are always hand-written. That
convenience comes with a rule: **always open and read a generated migration
before running it.** Autogenerate can miss things (renamed columns look like
a drop + an add; some index/type changes aren't detected) or generate a
correct-but-suboptimal migration for a large existing table.

Migration rules for this project:
1. Never hand-edit the database schema outside of a migration.
2. Every schema change is a migration, committed to git.
3. Always review an autogenerated migration before applying it.
4. Never edit a migration that has already been applied anywhere real
   (shared dev DB, staging, production) — write a new migration to fix it
   instead. (Editing an unapplied, uncommitted migration on your own machine,
   before anyone else has seen it, is fine.)
5. Be careful with destructive operations (dropping columns/tables) once
   real data exists.

### 7. Seed data

Populate roles, permissions, dev users, and default settings:

```powershell
python -m scripts.seed
```

This runs `scripts/seed.py`, which seeds (in order): permissions and roles,
one dev user per role, and default app settings. It's idempotent — safe to
re-run, existing rows are left as-is. Seeded users all use the password
`Password123!`, e.g. `dev@nativelife.com` for the Super Admin role.

### 8. Docker (optional, not required for local dev)

A `Dockerfile` and `docker-compose.yml` exist for later/deployment use, but
local development in this project currently runs directly against a
locally-installed PostgreSQL, not containers. To use Docker once you have it
installed:

```powershell
docker compose up --build
```

Note: inside `docker-compose.yml`, the `api` service overrides `DATABASE_URL`
to point at `db:5432` (the container's network name) instead of `localhost`,
since `localhost` inside a container means the container itself, not your
host machine.

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
