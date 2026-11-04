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
    realtime/     # WebSocket connection manager, publisher, event envelope (see docs/websocket.md)
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

### Authentication

Three sign-in methods share one `users` table and one session model. Every
successful sign-in returns the same `TokenResponse`: a 30-minute access token
(sent as `Authorization: Bearer ...`) and a refresh token. `POST /auth/refresh`
rotates both, and a refresh token works only once. `POST /auth/logout` revokes
the current pair.

| Method | Endpoints |
|---|---|
| Email + password | `POST /users/register`, `POST /auth/verify-email`, `POST /auth/login` |
| Phone OTP | `POST /auth/phone/request-otp` -> `POST /auth/phone/verify-otp` -> (new users) `POST /auth/phone/register` |
| Google | `POST /auth/google/sign-in` -> (new users) `POST /auth/google/register`; signed-in users: `POST /auth/google/link` |

`verify-otp` and `google/sign-in` return `data.status`:

- `authenticated` — tokens and the user, for an existing active account.
- `registration_required` — a 15-minute `registration_token`. The app must
  collect `first_name`, `last_name` and `accept_terms: true` and call the
  matching `register` endpoint. No tokens are issued before that.

Rules:

- Only a **verified** phone number signs in. Numbers typed during email
  registration are unverified and never grant access.
- Google accounts are matched on Google's stable `sub`, never on email. If the
  Google email already belongs to an account, sign-in returns 409
  `account_exists_sign_in_to_link`. The user signs in with their existing
  method and calls `POST /auth/google/link`. Accounts are never merged
  automatically.
- Errors that the app should branch on carry `errors[0].code`.

**SMS provider** (`SMS_PROVIDER`): `disabled` (default, phone endpoints return
503), `console` (local development only; the code is written to the server log
and the app refuses to start with it when `APP_ENV=production`), or `twilio`
(set `TWILIO_ACCOUNT_SID`, `TWILIO_API_KEY_SID`, `TWILIO_API_KEY_SECRET`,
`TWILIO_FROM_NUMBER`). Twilio trial accounts can only send to numbers verified
in the Twilio console. Sending to Indian numbers on the domestic route requires
DLT registration (entity, sender ID and the OTP message template from
`app/core/sms_templates.py`) before going live.

**Google** (`GOOGLE_CLIENT_IDS`): a JSON array with every OAuth client ID that
the apps request ID tokens for (Android, iOS, web). Empty disables Google
sign-in (503).

For console URLs, environment variables, how to get a Google ID token for
Postman, and the manual test flow, see
[docs/SSO_SETUP_GUIDE.md](docs/SSO_SETUP_GUIDE.md).

Phone OTP limits are per phone and per client IP. Behind a reverse proxy, run
Uvicorn with `--proxy-headers --forwarded-allow-ips=<proxy ip>`. Otherwise
every request appears to come from the proxy.

## Local setup

### Prerequisites

- Python 3.12+ (`py -V:3.12`)
- PostgreSQL running locally

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
one dev user per role, and default app settings. The seeder is the source of
truth for roles: it creates exactly the six roles in
[docs/roles-and-permissions.md](docs/roles-and-permissions.md), matched by
slug, sets each role's display name and permission set to match the code
(adding and removing permissions), and deletes any other role that has no
users. If a role outside the final six still has users, it stops and asks you
to run `alembic upgrade head` first. It's idempotent — safe to re-run, and
always run it after migrating. Seeded users all use the password
`Password123!`, e.g. `dev@nativelife.com` for the Super Admin role.

Deals settings seeded here (both editable later under `/api/v1/admin/settings`):

- `deal_accepting_roles` — JSON array with exactly one role slug that may accept
  deals, seeded as `["promoter"]` (resolved from the roles table). An existing
  value is never overwritten. If the `promoter` role is missing the seeder stops
  with an error; until the setting is valid, deal submission and acceptance
  return 503 instead of falling back to another role.
- `deal_acceptance_timeout_hours` — how long a submitted deal waits for
  acceptance before it expires (default `72`, allowed 1–720). The deadline is
  fixed when the deal is first submitted.

Delivery timing settings (also editable under `/api/v1/admin/settings`; if a row
is missing the default is used):

- `delivery_response_minutes` — how long the deal's own promoter has to answer
  a delivery request (default `30`, allowed 1–1440). If they reject it or the
  time runs out, the request opens to the other promoters serving that area.
- `delivery_claim_minutes` — how long the other promoters have to claim an
  opened request, first to accept wins (default `60`, allowed 1–1440). After
  that the request expires and the customer is notified.

Expired deals are enforced at request time; to also mark them expired and notify
creators without waiting for traffic, schedule this (e.g. hourly cron):

```powershell
python -m scripts.expire_deals
```

### Reset local database

Wipe all tables, rebuild the schema, and re-seed (local dev only — this
destroys all data):

```powershell
alembic downgrade base
alembic upgrade head
python -m scripts.seed
```

## Testing

```powershell
pytest
```

Full fixture/test-database setup lands in Phase 8 — for now, tests rely on
your local `.env` being populated (see below for a known gap).

Authentication tests live in `tests/auth/` (`unit/`, `integration/`, `live/`)
with their own fixtures. Integration tests create and drop a throwaway
`test_auth_*` schema in the database from `.env`. SMS and Google are faked:

```powershell
pytest tests/auth
```

`tests/auth/live/` is skipped unless configured. `LIVE_SMS_TO_PHONE=+91...`
sends one real SMS with the Twilio settings in `.env`.
`LIVE_GOOGLE_CLIENT_ID` plus `LIVE_GOOGLE_ID_TOKEN` (a fresh token from the
app) verifies against Google.

## Business plugins

Optional features for the Business / Service Provider role live in `plugins/` and are
loaded by the framework in `app/plugins/`. A plugin only runs after it has been applied and
the app restarted; Super Admin then enables it under `/api/v1/admin/plugins`.

```powershell
python -m app.plugins.cli validate          # check manifests, no database
python -m app.plugins.cli apply --key hello # register metadata and permissions
```

See [docs/plugins.md](docs/plugins.md).

## Linting & type checking

```powershell
ruff check .
mypy app plugins
```

## How to add a new module *(pending — filled in once Users module exists)*
