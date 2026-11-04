# Business Plugin Framework: session handoff

Handoff for continuing work on branch `feature/business-plugin-framework` on another machine.
Read `CLAUDE.md` and `docs/plugins.md` first. No secrets are included here.

## Where things stand

**Phase 1 (core plugin framework) is complete and verified. Phase 2 (business categories, plugin
bindings, per-business enablement, capabilities API) is implemented, its migration is applied to
`nativelife_dev`, its smoke tests passed and it is committed in `219d6e5`. Phase 3 (framework
hardening and module layout) is complete in `2566daa`. A PostgreSQL concurrency follow-up came
after it (a narrowed 409 mapping, an opt-in disposable-database guard and 12 concurrency tests)
and is uncommitted. It was run on a disposable PostgreSQL server only in an earlier state, before
the SQLSTATE `23503` narrowing and the guard hardening; the current working-tree code has not been
rerun against PostgreSQL and has only database-free verification. Its gaps are listed below. The
local reflog records `origin/feature/business-plugin-framework` at `3620249` as of 2026-10-22
13:59; the user did not push it from the previous session, and what performed that push is not
established. Later commits are not on the remote unless pushed since. Phase 4 has not started and
needs the user's approval. See `docs/plugins.md`.**

Latest work (after Phase 3, uncommitted, 2026-10-22). Static checks only (`ruff`, `mypy app
plugins`, `validate`); no automated tests were run or written for it:
- Framework (core API 1.3.0): plugin migrations (`migrations/NNNN_*.py`, `upgrade(op)`, tracked in
  `plg_<key>_migrations`), seeders (`seeders/NNNN_*.py`, `seed(connection)`), the SDK helper
  `record_activity`, local ZIP packaging (`package`, `install` CLI) and admin APIs under
  `/api/v1/admin/plugins`: `import` (extracts and installs in one request, loads the plugin into the
  running process, never enables it), `upgrade` (key read from the package), `{key}/uninstall`
  (disabled plugins only; optional file removal with a ZIP backup, tables and media always dropped),
  alongside the existing enable and disable. Details in `docs/plugins.md`.
- E-commerce plugin: built and packaged as `plugin_packages/ecommerce/ecommerce-1.0.0.zip`; the
  source folder `plugins/product/ecommerce/` is intentionally empty. The user reported import and
  install working in Postman. Documented in `docs/ecommerce-plugin.md`, including the enhancement
  backlog. The earlier "Phase 4 not started" statements are superseded by this work.
- Not done: tests for the new framework code and the plugin, re-running the PostgreSQL
  concurrency verification, committing. The two unrelated files `app/utils/phone.py` and
  `app/repositories/phone_otp_challenge_repository.py` must stay untouched (a formatter once
  reformatted them; they were reverted).

Phase 3 status as of 2026-10-22:
- Git: committed in `2566daa` ("feat(plugins): Phase 3 plugin framework hardening and module
  layout"), 19 files changed. `api-development` (`60718fe`, native places in the authenticated
  user response) was merged into this branch first in `ba3ae49`. The local reflog records the
  remote-tracking branch at `3620249` as of 2026-10-22 13:59; the user did not push it from the
  previous session, and the origin of that push is not established.
- No migration, schema change or database access in Phase 3; `nativelife_dev` is still at
  `a2a66b712e24`. Core API version is now 1.2.0. `hello` is unchanged (1.1.0, same content hash
  `360dc47...`), so the dev database keeps loading it.
- Implemented: the business access check is added by the framework, with the plugin's own key,
  to every route with a `business_id` path parameter (typed converters included); foreign keys
  and `business_id` outside the path are rejected; only standard FastAPI `APIRoute` objects are
  accepted (WebSocket, plain Starlette, mounted, host, custom-class and nested-router routes are
  rejected); routes are mounted in groups and the app lifespan is kept, so about 1,000 routes
  start without `RecursionError`; `dependency_overrides` is rejected in plugin source; symlinks
  and stray `.pyc`/`.pyo` files are rejected; plugin modules compile from source only, so forged
  `__pycache__` bytecode never runs; enable/disable lock the row and resolve the first-enable
  race with `ON CONFLICT DO NOTHING`; nested `plugins/<type>/<key>/` layout with a `backend/`
  sub-package, build-tool hash exclusions and `frontend`/`admin_panel` manifest metadata.
- Validation: `ruff check .`, `mypy app` and `mypy app plugins` are clean;
  `tests/unit/plugins` plus the `hello` tests passed 221 at the Phase 3 commit and pass 263 on
  the current working tree (database-free tests only, including the new guard and 409-mapping
  unit tests), including regression tests for every review finding and the forged-bytecode
  protection. This is not the whole unit suite. Known baseline failures remain and are
  unrelated: 30 in `tests/unit` (20 realtime, 10 sms) and 2 collection errors in
  `tests/unit/auth`. The whole test suite does not pass. `tests/integration/` was not run at
  the time of this commit; see the PostgreSQL follow-up below.
- PostgreSQL concurrency follow-up (after `2566daa`, uncommitted): run on a disposable
  PostgreSQL 18.6 + PostGIS 3.6.3 server (temporary data directory, Unix socket only, no TCP
  listener, database `nl_concurrency_test`), never on `nativelife_dev`, but only in an earlier
  state of the code and tests. The current working tree has NOT been rerun against PostgreSQL.
  - Current state: only database-free verification (`ruff`, `mypy app plugins`, 263 plugin and
    `hello` unit tests). The 409 narrowing and the guard hardening are covered by unit tests with
    fake repositories and constructed driver errors, which do not verify database behaviour.
  - Earlier PostgreSQL results, obtained before the SQLSTATE `23503` narrowing and the guard
    hardening: `tests/integration/plugins/test_business_plugin_concurrency.py` passed 12/12
    (forced and repeated first-enable races; enable/disable waiting on a locked row; a change
    committed while waiting is seen and not logged twice; concurrent enable and disable with
    consistent status and audit counts; disable not waiting for an uncommitted first enable;
    enum binding, server defaults, `RETURNING` and reload; a business removed mid-enable
    returning 409 with no row or audit entry; the winning row removed before re-read returning
    409; lock lifetime for an already-active enable, a completed HTTP request and a fresh
    insert, as those scenarios behaved then). The existing `tests/integration/plugins` suite also
    passed 30/30 on the same server, including the verified Business / Service Provider owner
    path. These results do not verify the current code, including the two 409 paths as they
    behave now.
  - Earlier mutation result, from that same earlier state: reverting the insert-race handling
    and the 409 mapping failed 4 of the 12 tests. The current locking behaviour has not been
    mutation-verified.
  - The 409 mapping now applies only to foreign-key violations (SQLSTATE 23503); other
    integrity errors are rolled back and re-raised. The disposable-database guard rejects
    repeated or comma-separated `host` values and anything but exactly one socket port; both
    are covered by database-free unit tests only.
  - Gaps that remain: the concurrency module and the plugin integration suite have not been
    rerun on a disposable server against the current code; the broader `tests/integration` tree
    has not been run against a disposable server; the locking behavior has not been proven by a
    mutation test that removes `FOR UPDATE` (a procedure is prepared, not run), and no
    deterministic test pauses a worker between the locked read and its write (two writers on one
    existing association); repeated-run and flakiness testing has not been done; a plugin row or
    the acting user deleted during an enable request are not separately tested; and the
    "business deleted mid-enable" scenario has not been re-run on a disposable server since the
    409 mapping was narrowed.
  - The guard, the run commands and the full verified / not-verified list are in
    `docs/plugins.md`.
- Remaining limitations: plugins are still trusted in-process code, so the static checks are a
  guardrail, not a sandbox (runtime-built names, `exec` or patching core modules are not
  stopped); the plugin source-only import finder is a process-wide import hook limited to
  `native_life_plugin_*` modules; business-scoped routes are restricted to the owner or
  `business.view_any`, so public storefront-style routes need an explicit opt-in later
  (product decision).

Phase 2 status as of 2026-10-22:
- Git: committed in `219d6e5` ("feat(plugins): add business category bindings and
  per-business enablement"), 54 files changed, 2,807 insertions and 44 deletions. The working tree
  was clean after the commit. It is an ancestor of `3620249`, which the local reflog records as
  the remote-tracking branch tip as of 2026-10-22 13:59 (see the Phase 3 Git note).
- Implemented: the business category tree, plugin-to-category bindings, per-business plugin
  enablement and the capabilities API.
- Database: migration `a2a66b712e24` is applied; `alembic current` = `a2a66b712e24` (head).
  Verified after applying: `categories.sort_order`, `plugin_category_bindings` and
  `business_plugins` exist with the expected enums, FKs and indexes; the 13 pre-existing
  categories, `spatial_ref_sys` (8500 rows) and all existing indexes, including the 9 GiST
  spatial indexes, are unchanged.
- Plugin: `python -m app.plugins.cli apply --key hello` upgraded `hello` from 1.0.0 to 1.1.0. It
  is globally enabled; `plugin_installations` has the 1.0.0 install and the 1.0.0 -> 1.1.0
  upgrade, both succeeded.
- Categories: `apply` created `business`, `business-product`, `business-service` and
  `business-service-reference` (Reference Services, under Service), and one binding from `hello`
  to `business-service-reference` (`created`, applies to businesses, include_descendants).
  All have `sort_order` 0, so listings stay alphabetical.
- Smoke tests passed for every scenario exercised: category listing and ordering, capabilities,
  available plugins, owner enable (idempotent) and disable, cross-user enable/disable/capabilities
  denied with 403, the business-scoped `hello` greeting before enable, after enable and after
  disable, and existing business creation (an unverified Business / Service Provider is still
  refused with 403).
- How the smoke tests ran: an isolated in-process app (FastAPI `TestClient`) against
  `nativelife_dev`, without touching the running servers. Authentication was replaced by loading
  an existing user from a test header instead of the normal stored-session token flow; all
  ownership, permission, verification and status rules ran unchanged.
- Coverage gap: the test business owner was the Super Admin, whose `business.update_any` lets the
  enable check pass. The verified Business / Service Provider owner path is still untested
  against the dev DB (no verified provider exists there). `tests/integration/plugins/` covers it;
  it was not run then because it creates a temporary schema, and it passed 30/30 in
  an earlier run on a disposable PostgreSQL server, before the latest 409 and guard changes (see
  the Phase 3 PostgreSQL follow-up).
- Test data, kept for debugging: business `6350776e-c42b-48fb-a4aa-8bcc5cd21004` (owner Super
  Admin, Reference Services) was soft-deleted through `DELETE /api/v1/businesses/{id}`. Its
  `business_plugins` row `96d7d026-75ae-4196-809e-dfe07cf9ee8d` stays `disabled`. The audit
  history is preserved: `BUSINESS_CREATED`, `BUSINESS_PLUGIN_ENABLED`, `BUSINESS_PLUGIN_DISABLED`
  and `BUSINESS_DELETED` activity log entries.
- Validation: `ruff check .`, `mypy app` and `mypy app plugins` are clean;
  `tests/unit/plugins` plus the `hello` tests pass (147). Known baseline failures remain and are
  unrelated to Phase 2: 30 in `tests/unit` (20 realtime, 10 sms) and 2 collection errors in
  `tests/unit/auth`. The whole test suite does not pass.
- A server started before the `hello` upgrade must be restarted to serve `hello` 1.1.0.
- The three Phase 2 review follow-ups (business-route enforcement with the plugin's own key,
  the concurrent-enable 500, and the missing authorization and concurrency tests) were resolved
  in Phase 3; PostgreSQL concurrency was run on a disposable server afterwards, in an earlier state of the
  code, with the gaps listed above.

Phase 2 notes:
- `alembic revision --autogenerate` is unsafe here: it proposes dropping PostGIS
  `spatial_ref_sys` and spatial/GIS indexes the models don't declare. Write migrations by hand.
- Plugin integration tests live in `tests/integration/plugins/` (temp-schema isolated) and are
  tracked in git like the unit plugin tests.

- Branch `feature/business-plugin-framework`, created from `api-development` at `1ec8b5c`.
- Scope is the **Business / Service Provider role only**. Manifests with any other `role_scope`
  are rejected.
- The Business Creation flow is unchanged and must stay unchanged until the agreed integration
  phase.
- A separate, older effort exists on `origin/feature/business-plugin-platform` (JSON manifest,
  `app/plugin_runtime`, Product Management plugin, category model changes). It uses a different
  design. Do not merge or borrow from it without asking.

## Working agreements (from the user)

- Work in phases. Stop and wait for approval after each phase and before any database change.
- Never create a new database (no `nativelife_test`). Use only the local `nativelife_dev`.
- No backups unless the user asks. Never run `alembic downgrade`, `drop_all`, a fresh migrate,
  a restore or a forced revision.
- Apply migrations only after explicit approval for that step. Show the pending chain and the
  offline SQL (`alembic upgrade <current>:head --sql`) first.
- Do not run the full `scripts/seed.py`.
- Commit or push only when asked.
- Do not modify unrelated realtime, SMS or auth code to make old tests pass.
- Follow `CLAUDE.md`: no comments or docstrings in code, message constants, `ApiTag` constants,
  Postman entries, `docs/schema.dbml` updated with every schema change, `ruff check .` and
  `mypy app` clean.

## What Phase 1 contains

See `docs/plugins.md` for the full design. In short:

- Framework in `app/plugins/`: strict `plugin.toml` manifest, versioning, discovery with a
  content hash, dependency resolution, static import boundaries, `PluginContext`, per-plugin
  SQLAlchemy metadata isolation, loader, immutable `PluginRegistry`, startup mounting in the
  `app/main.py` lifespan, request-time status check, subprocess smoke-load, CLI and SDK.
- Tables `plugins` and `plugin_installations` (migration `ad327d0c75ba`).
- Permissions `plugin.view` and `plugin.manage` (Super Admin only, through the existing seed).
- Admin API under `/api/v1/admin/plugins` (list, load-report, detail, enable, disable).
- Reference plugin `plugins/_reference/hello/` with `GET /api/v1/plugins/hello/greeting`
  (permission `plugin.hello.greeting.view`).
- CLI: `python -m app.plugins.cli validate` and `python -m app.plugins.cli apply [--key KEY]`.
- Install and upgrade need `apply` and then an app restart. Enable and disable take effect
  immediately. A plugin's code loads only if its on-disk version and content hash match the
  applied row; any code change needs a version bump, `apply`, then a restart.

### Phase 0 spike conclusions (SQLAlchemy 2.1.1, Alembic 1.20.0)

- A separate `DeclarativeBase` per plugin keeps a broken plugin mapper from breaking core
  queries. With the shared core `Base`, it breaks every query.
- `backref` onto a core model breaks the core permanently, so it is rejected statically.
- Cross-registry foreign keys must use column objects; string FKs and string relationships fail.
- Alembic `depends_on` branches take over the core `alembic_version` row. Plugin migrations
  (later phase) should use a per-plugin version table `plg_<key>_alembic_version`. Verified
  offline only.

### Review fixes already made

Import allowlist (stdlib, installed packages, own modules, `app.plugins.sdk`); production code
cannot import the plugin's `tests` package; router `on_startup`/`on_shutdown`/`lifespan`
rejected; trial OpenAPI generation at load; unregistered model bases and core-model subclasses
rejected; `SystemExit` contained; optional dependency failures don't cascade; apply closes its
read transaction before the smoke subprocess; an activity-log failure after commit no longer
marks the apply as failed; duplicate-key failures map to the right directory; `apply --key`
with an unknown key exits 1; `validate` runs the import checks; version length capped at 50.

## Verification done on the original machine (2026-10-21)

- Migrations applied there: `cc467734a535` → `a9c4e2b7d815` → `ad327d0c75ba` (head).
- `hello` applied (`installed`, then idempotent `unchanged`), then enabled, disabled and
  re-enabled through the API with no restart: 28/28 live checks passed. It was left **enabled**.
- `ruff check .`, `mypy app`, `mypy app plugins` clean. 139 plugin tests passed.

### Known pre-existing failures (identical on base commit `1ec8b5c`; not caused by this branch)

- `tests/unit`: 30 failures (realtime and SMS tests call old signatures).
- `tests/unit/auth`: 2 collection errors (import removed functions).
- `tests/integration/account_roles`: 10 failures (create-business denial gets 422 instead of
  403; role-selection expectations).

## Setting up on another machine

1. `git fetch && git switch feature/business-plugin-framework`.
2. Python virtualenv, `pip install -e ".[dev]"`. Copy `.env` from `.env.example` and fill in
   values; never commit `.env`. `PLUGINS_DIR=plugins` is the default.
3. **Plugin tests are in git.** `tests/unit/plugins/` (134 framework tests) and
   `plugins/_reference/hello/tests/` (5 tests) are committed, with the shared
   `tests/__init__.py`, `tests/unit/__init__.py` and `tests/conftest.py`. Run them with
   `pytest tests/unit/plugins plugins` (no database needed). The rest of `tests/` (the older
   suite) is still gitignored and will not exist on a fresh clone.
4. **Check the database before running anything**:
   `alembic current` and `alembic heads`.
   - If the other machine's `nativelife_dev` was used for `feature/business-plugin-platform`,
     it may be at revision `c5d8e2f7a1b4` and already contain a different `plugins` table.
     This branch does not know that revision, and `ad327d0c75ba` would collide with the
     existing `plugins` table. **Stop and ask the user how to reconcile; do not force a
     revision or drop tables.**
   - If it is at `cc467734a535` or `a9c4e2b7d815`, show the pending SQL and ask before
     `alembic upgrade head`.
5. After approval: `python -m app.plugins.cli validate`, `python -m app.plugins.cli apply
   --key hello`, start `uvicorn app.main:app --reload`, and enable through
   `POST /api/v1/admin/plugins/hello/enable` as Super Admin (`dev@nativelife.com`).

Notes from the original machine: seeded `individual@` and `business@` accounts could not log
in (email unverified); `dev@` and `native.admin@` could. Postgres.app 18 needed its own
`pg_dump` (Homebrew's v16 refuses the v18 server).

## Pending decisions for the user

1. Proposed `CLAUDE.md` exceptions listed in `docs/plugins.md` (manifest API tags, per-plugin
   Postman collections, plugin-local messages/permissions/actions, `mypy app plugins`). The
   plugin-tests exception is already approved and recorded in `CLAUDE.md`.
2. Whether to create the `plugin.view` / `plugin.manage` permission rows with a focused insert
   (only needed to grant them to roles other than Super Admin).
3. Whether to keep the reference plugin enabled on dev.
4. Approval to start Phase 2.

## Next phase (Phase 2, not started)

From the approved architecture: business category integration and per-business plugin
enablement, without changing Business Creation yet.

- `categories.sort_order` (default 0, order by `sort_order, name, id`).
- Core-owned business category roots `business`, `business-product`, `business-service`.
- Manifest-driven category sync by explicit slug (create, adopt, conflict rules), recorded in
  `plugin_category_bindings` (`ownership` created/adopted, `include_descendants`).
- `business_plugins` (per-business enablement, explicit opt-in only).
- `PluginBusinessDep` (business exists, ownership via `ensure_can_modify`, plugin enabled,
  business-plugin row active) and a capabilities endpoint for the mobile and admin apps.

Later phases: first real plugin (Product Catalog), plugin migrations with per-plugin version
tables, signed ZIP packaging and install, then E-commerce and Hotel.

Open questions carried over from the architecture review: whether user category suggestions
should be blocked under the `business` tree; whether Events and Lost & Found should be scoped
to their own category roots (unrelated modules); whether pending providers may use plugin
features; which admin roles get plugin `*_any` permissions.
