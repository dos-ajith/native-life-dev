# Business plugins (Phases 1-3)

Plugins add features for the **Business / Service Provider** role without changing core code.
Phase 1 provides the framework, the registry, the admin API and a reference plugin. Phase 2
adds the business category tree, plugin-to-category bindings, per-business enablement and the
capabilities API. Phase 3 hardens business-scoped routes and the enable race, adds the nested
module layout, build-tool hash exclusions and frontend/admin-panel manifest metadata. There is
still **no** HTTP upload, signatures, frontend delivery, rollback, uninstall or purge. Core API
1.3 adds plugin migrations, seeders and local ZIP packaging (see "Migrations, seeders and ZIP
packages").

See `docs/ecommerce-plugin.md` for the first real plugin built on this framework.

## Trust model

Plugin code runs inside the API process with full access to its memory, settings and database
session. Python cannot sandbox it. So:

- Plugins are **trusted code**, reviewed like core code.
- Nothing runs because a directory or file exists. A plugin's code is imported at startup
  only after `python -m app.plugins.cli apply` has recorded that exact version **and** content
  hash in the `plugins` table.
- HTTP requests never import plugin code or run plugin migrations.
- The framework never installs Python dependencies.

## Layout

```
app/plugins/                  framework (core)
  manifest.py                 plugin.toml schema (strict, extra fields rejected)
  versioning.py               semantic versions, version ranges, CORE_API_VERSION
  discovery.py                finds plugin.toml files, hashes plugin contents
  resolution.py               duplicate keys, dependencies, cycles, load order
  boundaries.py               static checks: core imports only via app.plugins.sdk, no backref
  context.py                  PluginContext passed to register(ctx)
  metadata.py                 per-plugin SQLAlchemy registry isolation checks
  loader.py / registry.py     import + register, immutable PluginRegistry
  mounting.py / bootstrap.py  startup wiring (app/main.py lifespan)
  deps.py                     request-time plugin status and business access checks
  scoping.py                  business_id route detection, business-access key checks
  layout.py                   test, cache, build-tool and generated-file exclusions
  source_imports.py           source-only import finder/loader for plugin modules
  smoke.py / cli.py           subprocess smoke load, `validate` and `apply`
  sdk.py                      the only core module plugins may import
plugins/                      plugin packages (folder names carry no meaning)
  _reference/hello/           reference plugin
  <business-type>/<key>/      recommended layout for business modules, e.g. product/ecommerce
```

Recommended module layout (Phase 3). Folder names stay meaningless; identity and business type
come only from the manifest. A plugin directory inside another plugin directory is rejected.

```
plugins/product/ecommerce/
  plugin.toml                 [entrypoint] module = "backend.plugin" (or a root plugin.py)
  __init__.py
  backend/                    __init__.py, plugin.py (register), routes/, services/, schemas/,
                              repositories/, models/ — relative imports only
  frontend/  admin_panel/     built bundles declared in the manifest; never imported or served
  postman/
  tests/                      excluded from the content hash and boundary checks
```

Excluded from the content hash, plugin discovery and the boundary checks, and not importable by
plugin code: `tests/`, caches (`__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`) and
build-tool directories (`node_modules`, `.git`, `.venv`, `venv`, `.tox`, `.nox`, `.cache`,
`.parcel-cache`, `.next`, `.nuxt`, `.turbo`, `.svelte-kit`, `htmlcov`, `.idea`, `.vscode`) at
any depth, plus `.DS_Store` and `Thumbs.db` files. Built bundles such as `frontend/dist/` are
hashed, so changing them requires a version bump.

Discovery rejects a plugin directory that is itself a symlink or contains any symlink (file or
directory, including a symlinked `node_modules`), and any `.pyc`/`.pyo` file outside
`__pycache__`, so no unhashed or unscanned code can be imported. It does not look inside the
excluded directories above, so links inside a real `node_modules` (such as `.bin/`) are allowed;
plugin code cannot import from those directories.

Plugin modules (everything under `native_life_plugin_<key>`) are compiled from their `.py`
source on every load and never read or write cached bytecode, so a forged `.pyc` in
`__pycache__/` (timestamp-matched or unchecked-hash) is never executed, and a cache entry with
no source file cannot be imported. The plugin import finder only considers `.py` sources, so
native extension modules (`.so`/`.pyd`) inside a plugin directory cannot be imported either.
This applies to plugins loaded by the framework; a plugin's own `tests/` run under pytest use
normal imports.

## Manifest (`plugin.toml`)

Identity and business type come only from the manifest, never from folder names. See
`plugins/_reference/hello/plugin.toml`. Rules enforced:

| Field | Rule |
|---|---|
| `manifest_version` | `1` |
| `plugin.key` | 3-30 chars, `^[a-z][a-z0-9]*(_[a-z0-9]+)*$`, unique across plugins |
| `plugin.version` | `MAJOR.MINOR.PATCH` |
| `plugin.role_scope` | must be `business-service-provider` |
| `plugin.business_type` | `product` or `service` |
| `compatibility.core_api` | range such as `>=1.0,<2.0`, checked against `CORE_API_VERSION` |
| `dependencies` | required list (may be empty) of `{ key, version, optional }` |
| `categories` | required list (may be empty) of `{ slug, name, parent, bind, include_descendants }`; slugs under `business-<type>-`, parents declared earlier or the `business-<type>` root. Synced by `apply` (see below) |
| `api.prefix` | must be `/plugins/<key>`; mounted under `/api/v1` |
| `api.tag` | must start with `1.5 Businesses · ` |
| `database.table_prefix` | must be `plg_<key>_` |
| `database.migrations` | `true` requires a `migrations/` directory (see below) |
| `database.seeders` | `true` requires a `seeders/` directory (see below) |
| `permissions` | names `plugin.<key>.<resource>.<action>`; created by `apply`, never granted automatically |
| `capabilities` | optional `[[capabilities]]` of `{ key, title, type = menu\|widget, path, permission }`; `path` is relative to the plugin prefix and may use `{business_id}`; `permission` must be declared above |
| `frontend`, `admin_panel` | optional `{ path, entry }` (core API 1.2+); relative paths without hidden, test, cache or build-tool segments; `path/entry` must be a file inside the plugin directory. Metadata only: the backend never serves or loads these files |

## Lifecycle

| Step | How | Restart needed |
|---|---|---|
| Validate manifests and dependencies | `python -m app.plugins.cli validate` (no database) | no |
| Apply (install / upgrade) | `python -m app.plugins.cli apply [--key KEY]` | **yes** |
| Enable / disable | `POST /api/v1/admin/plugins/{key}/enable` and `/disable` | no |
| Grant plugin permissions to roles | existing `PUT /api/v1/roles/update/{id}/permissions` | no |

`apply`, per plugin, in dependency order:

1. Checks that the `migrations/` and `seeders/` directories declared in the manifest exist.
2. Static boundary check of the plugin's source.
3. Required dependencies must be applied at a compatible version (in this run or earlier).
4. Smoke load in a **separate Python process**: import, `register(ctx)`, model configuration,
   OpenAPI generation. A crash there cannot affect the caller.
5. Under a Postgres advisory transaction lock, in one transaction: insert or update the
   `plugins` row (new plugins start as `installed`, not enabled), insert missing permission
   rows, insert a `plugin_installations` row with status `succeeded`. Then an activity log
   entry (`PLUGIN_INSTALLED` / `PLUGIN_UPGRADED`, system actor).
6. Any failure rolls back and records a `plugin_installations` row with status `failed`. No
   activity log entry is written for failures.

Reapplying an identical plugin does nothing (`unchanged`). Same version with different
contents is refused: bump the version. Lower versions are refused.

At startup the app loads only plugins whose on-disk version and content hash match the
`plugins` row. Others are reported as `skipped` in `GET /api/v1/admin/plugins/load-report`. A
plugin that fails to load is reported as `failed`; the core API and other plugins keep running.

Every plugin route runs `require_plugin_enabled` first: one primary-key lookup. Disabled or
unregistered plugins return 404 immediately. If the database holds a newer version than the
code loaded by this process (applied but not restarted), routes return 503.

## Migrations, seeders and ZIP packages (core API 1.3)

Plugin migrations never touch the core Alembic history. A plugin with `database.migrations = true`
ships `migrations/NNNN_description.py` files, each defining `upgrade(op)` where `op` is an Alembic
`Operations` object. During `apply`, inside the same locked transaction as the registry update,
pending files run in name order and each applied revision is recorded in `plg_<key>_migrations`.
A failure rolls back the whole apply. A revision recorded as applied but missing from the plugin
is refused (no downgrades). Migration files are plugin source: they are boundary-checked and may
only import the standard library and installed packages. Tables must start with `plg_<key>_`.

With `database.seeders = true`, `seeders/NNNN_description.py` files define `seed(connection)` and
run after the migrations on every install or upgrade (not on an unchanged reapply). They must be
idempotent and must not overwrite administrator-managed rows.

`python -m app.plugins.cli package --key KEY [--output-dir plugin_packages]` writes
`plugin_packages/<key>/<key>-<version>.zip`
(deterministic; excludes tests, caches and build-tool directories; includes a `CONTENT_SHA256`
entry). `python -m app.plugins.cli install ARCHIVE [--replace]` verifies the checksum, rejects
unsafe entries, symlinks, oversized archives, incompatible core versions and boundary
violations, then extracts to `plugins/<business_type>/<key>/`. It does not register anything:
run `apply` and restart. Packages are not signed.

`POST /api/v1/admin/plugins/import` (multipart field `file`, permission `plugin.manage`) does the
same extraction for an uploaded ZIP and additionally refuses keys already registered in the
database (409). It then installs the plugin in the same request (`apply`: migrations, seeders,
permissions, categories) and loads it into the running process, removing the extracted files if
the install fails. It never enables the plugin.

The hot load only affects the worker that handled the import request: with several workers,
restart the others. If the hot load fails the response has `loaded=false` and the application must
be restarted before enabling.

`POST /api/v1/admin/plugins/upgrade` (multipart `file`; the key comes from the package, `plugin.manage`) swaps in a newer
version's files and applies it, restoring the old files if the apply fails; the new code runs after
a restart (routes return 503 until then). `POST /api/v1/admin/plugins/{key}/uninstall` (JSON `remove_files`)
requires the plugin to be disabled with no installed dependents; it removes the registry row,
bindings and per-business enablement, always drops the `plg_<key>_*` tables and the plugin's
uploaded media, and backs up and deletes the files unless `remove_files` is false. Created
categories and permissions are kept.

## Business categories and plugin bindings (Phase 2)

Core-owned category roots, created idempotently by `seed_business_categories()` in
`scripts/seed.py` and, when needed, by `apply`:

| Slug | Name | Parent |
|---|---|---|
| `business` | Business | none |
| `business-product` | Product | `business` |
| `business-service` | Service | `business` |

`categories.sort_order` (default 0) orders category listings by `sort_order, name, id`; set it
with `PATCH /api/v1/categories/{id}`. Existing categories keep their alphabetical order.

During `apply`, inside the same locked transaction as the registry update, each declared
category is resolved by **slug** (never by name):

| Situation | Result |
|---|---|
| Slug not found | Created (published, active, system-created). Binding ownership `created` |
| Slug found, published, inside the plugin's `business-<type>` tree | Adopted unchanged (admin edits are kept). Ownership `adopted` unless this plugin created it |
| Slug found but pending or rejected | Apply fails |
| Slug found outside the plugin's tree | Apply fails |
| Different slug with the same name under the same parent | Apply fails |
| Parent category not published and active | Apply fails |
| Declaration removed in a newer version | Binding gets `removed_at`; the category is kept |
| Same category declared by two plugins | Shared; the second plugin adopts it |

Any failure rolls back the whole apply and records a failed `plugin_installations` row.
Repeated applies change nothing. Categories bound to a plugin cannot be deleted (422).

A business is compatible with a plugin when its category chain is published and active and the
plugin has a binding with `bind = true` on the business's category, or on an ancestor with
`include_descendants = true`.

## Per-business enablement and capabilities (Phase 2)

| Endpoint | Who | Notes |
|---|---|---|
| `GET /api/v1/me/businesses/{id}/capabilities` | owner or `business.view_any` | business type, category chain, enabled plugins with capabilities the caller may see, compatible plugins not yet enabled |
| `GET /api/v1/me/businesses/{id}/plugins/available` | owner or `business.view_any` | compatible, usable plugins with `enabled_for_business` |
| `POST /api/v1/me/businesses/{id}/plugins/{key}` | owner holding `business.create`, or `business.update_any` | business must be active; plugin globally enabled, loaded and compatible; idempotent |
| `DELETE /api/v1/me/businesses/{id}/plugins/{key}` | owner or `business.update_any` | idempotent; allowed even when the plugin is globally disabled or incompatible |

"Usable" means globally enabled and loaded by this process at the applied version. Enabling or
disabling for a business never changes the plugin's global status. Errors follow the existing
conventions: 401 anonymous, 403 not owner or role not approved, 404 business or plugin not
found/available, 422 business inactive or category not compatible.

Plugins may only declare standard FastAPI `APIRoute` HTTP routes and must register each
`APIRouter` with `ctx.include_router`. The loader rejects WebSocket routes, plain Starlette
routes (`router.add_route`), mounted sub-applications, hosts, custom route classes and nested
`router.include_router(...)`, because FastAPI does not apply the framework's dependencies to
most of them.

Every plugin route with a `business_id` path parameter is business-scoped, detected by
parameter name, so typed converters such as `{business_id:uuid}` count. The framework adds the
business access check to it at mount time, with the plugin's own key, after the global enabled
check; a plugin cannot opt out. The check enforces: business exists and is not deleted, owner
(with an approved role) or `business.view_any`, business active, plugin globally enabled,
plugin enabled for the business, and category still compatible (403 otherwise). `business_id`
must be a UUID (422 otherwise).

To read the business, a route declares `require_business_plugin("<own key>")`, which returns a
read-only `PluginBusiness`; it shares the framework's check, so it runs once per request. The
loader rejects a plugin that passes another plugin's key, uses the dependency on a route
without a `business_id` path parameter, or takes `business_id` as a query, header, cookie or
body parameter anywhere in a route's dependencies.

Routes are mounted in order, grouping consecutive routes that need the same checks. Plugin
routers cannot declare lifespan or startup/shutdown handlers, so mounting keeps the app's
original lifespan instead of wrapping it once per group.

Product decision pending: business-scoped routes are restricted to the owner or
`business.view_any`, so a plugin cannot yet offer public, customer-facing pages keyed by
`business_id` (for example a storefront). That needs an explicit opt-in in a later phase.

Enable and disable lock the association row (`SELECT ... FOR UPDATE`). Concurrent first enables
insert with `ON CONFLICT DO NOTHING`; the request that loses the race returns the winner's row
(200) and writes no second activity log entry. A disable that runs while a first enable is still
uncommitted does not see the row and is a no-op (the enable wins). If the business or plugin row
is removed while a plugin is being enabled, the foreign-key failure is rolled back and returned
as 409 `ENABLE_TARGET_REMOVED` with no association row and no audit entry; if the winning row
disappears before it is re-read, enable returns 409 `ENABLE_CONFLICT`. An already-active enable
holds the row lock until the request commits; a fresh insert commits immediately. This paragraph
describes the intended behaviour of the current code. The PostgreSQL results below were obtained
before the latest changes (see "PostgreSQL verification status"), so they do not verify the
current code.

The scenarios below were verified in an earlier run against a disposable PostgreSQL 18.6 +
PostGIS 3.6.3 server (temporary data directory, Unix socket only, no TCP listener, database
`nl_concurrency_test`) by `tests/integration/plugins/test_business_plugin_concurrency.py`. That
run took place before the SQLSTATE `23503` narrowing of the 409 mapping and before the
disposable-database guard was hardened. That module only runs on such a
server: it skips itself unless `NATIVE_LIFE_DISPOSABLE_PG=1`. With the flag,
`tests/integration/conftest.py` refuses (exit code 3) before any schema is created unless the
URL names the `nl_concurrency_test` database, no TCP host or port, exactly one absolute
Unix-socket directory (a repeated or comma-separated `host` is rejected) and exactly one socket
port, 55432, and the live server then confirms the same database, port 55432, a socket
connection and `listen_addresses = ''`. The URL rules and refusals are covered by database-free
tests in `tests/unit/plugins/test_disposable_postgres_guard.py`. Never point it at
`nativelife_dev`. To run it:

```bash
PGBIN=/Applications/Postgres.app/Contents/Versions/18/bin
PGROOT=$(mktemp -d) PGSOCK=$(mktemp -d /tmp/nlpg.XXXXXX)
"$PGBIN/initdb" -D "$PGROOT/data" -U nl_test --auth=trust -E UTF8 --locale=C
"$PGBIN/pg_ctl" -D "$PGROOT/data" -l "$PGROOT/server.log" -w start \
  -o "-c listen_addresses='' -k $PGSOCK -p 55432 -c fsync=off"
"$PGBIN/createdb" -h "$PGSOCK" -p 55432 -U nl_test nl_concurrency_test
"$PGBIN/psql" -h "$PGSOCK" -p 55432 -U nl_test -d nl_concurrency_test -c "CREATE EXTENSION postgis"
DATABASE_URL="postgresql+psycopg://nl_test@/nl_concurrency_test?host=$PGSOCK&port=55432" \
NATIVE_LIFE_DISPOSABLE_PG=1 .venv/bin/pytest tests/integration/plugins -v
"$PGBIN/pg_ctl" -D "$PGROOT/data" -m fast stop; rm -rf "$PGROOT" "$PGSOCK"
```

Only a foreign-key violation (SQLSTATE 23503) during the first insert becomes the 409; any other
integrity error (NOT NULL, unique, check) is rolled back and re-raised unchanged.

PostgreSQL verification status:

- Current state of the code: the working tree has NOT been rerun against PostgreSQL since the
  SQLSTATE `23503` narrowing and the guard hardening. The current changes have only
  database-free verification (`ruff`, `mypy app plugins` and 263 plugin and `hello` unit tests,
  which include the guard and 409-mapping unit tests using fake repositories and constructed
  driver errors). That is not the whole unit suite: 30 tests in `tests/unit` (20 realtime, 10
  sms) and 2 auth collection errors still fail for unrelated, pre-existing reasons. No
  database-free test verifies database behaviour.
- Earlier PostgreSQL results, obtained before the SQLSTATE `23503` narrowing and the guard
  hardening, on the disposable server: the concurrency module passed 12/12 (forced and repeated
  first-enable races, enable/disable ordering on a locked row, a disable that does not wait for
  an uncommitted first enable, enum binding, server defaults, `RETURNING` and reload, the two
  409 paths as they behaved then, and lock lifetime for an already-active enable, a completed
  HTTP request and a fresh insert). The existing `tests/integration/plugins` suite also passed
  30/30 on the same server. These results do not verify the current code, and in particular not
  the two 409 paths as they behave now.
- Earlier mutation result, from that same earlier test and code state: reverting the
  insert-race handling and the 409 mapping made 4 of the 12 tests fail. The current locking
  behaviour has not been mutation-verified.
- Not yet verified:
  - Everything above against the current code: the concurrency module and the plugin
    integration suite have not been rerun on a disposable server after the 409 narrowing and
    the guard hardening.
  - The broader `tests/integration` tree (deals, auth, account roles, native places and so on)
    has not been run against a disposable server. Two account-role tests there
    (`test_migration.py`, `test_final_role_migration.py`) run migration downgrades and should
    stay excluded.
  - The locking behavior is not yet proven by a mutation test: no run has removed `FOR UPDATE`
    to show that the lock-dependent tests fail. A procedure is prepared, but it has not been run.
  - No deterministic test pauses a worker between the locked read and its write, so two
    concurrent writers on one existing association (a lost-update or duplicate-audit race) are
    covered only by the probabilistic stress tests. By reading the tests, those that wait on a
    locked row are expected to be delayed by the later `UPDATE` even without the
    `SELECT ... FOR UPDATE`, so they are probably only partly sensitive to its removal; this
    prediction has not been observed.
  - Repeated-run and flakiness testing has not been done. The module has passed once on a
    single disposable server; the 20-round stress tests are probabilistic, and the forced-order
    tests are the deterministic evidence.
  - A plugin row or the acting user deleted during an enable request are not tested separately.
    They take the same foreign-key path (SQLSTATE 23503) as a deleted business and return the
    same 409, whose message mentions only the business or plugin.
  - The narrowing of the 409 mapping to SQLSTATE 23503 is covered by unit tests with constructed
    psycopg errors; scenario "business deleted mid-enable" has not been re-run on a disposable
    server since that change.

PostgreSQL concurrency verification is not complete: the earlier results cover an earlier state
of the code, the current code is verified only without a database, and the gaps above remain.

Plugin code is still trusted, in-process Python. The boundary check rejects references to
`dependency_overrides` (attribute, name, import alias or string, which covers `getattr`,
`setattr` and `vars()` lookups), but it cannot stop deliberately obfuscated access such as
building the name at runtime or `exec`. It is a guardrail, not a sandbox.

## Writing a plugin

- Import from the core only through `app.plugins.sdk`. Use relative imports inside the plugin.
- Name the business path parameter `business_id` on every route that acts on a business, and
  never accept `business_id` as a query, header, cookie or body parameter.
- Register every router with `ctx.include_router`; set prefixes on the `APIRouter` itself
  instead of nesting routers.
- Do not give routers or routes their own `tags`; the framework applies the manifest tag.
- Models (from a later phase) must use their own `DeclarativeBase` with a separate `MetaData`,
  call `ctx.register_models(Base)`, prefix tables with `plg_<key>_`, reference core tables
  with column objects, and never use `backref` (it would attach attributes to core models).
- Keep plugin messages, permission names and action names in the plugin's own modules.
- To let the app AI use the plugin, subclass `AITool` (SDK) and call `ctx.register_ai_tool(...)`
  (core API 1.5). The tool name must start with `<key>_`. Tools are offered to the AI only while
  the plugin is enabled and its loaded version is the applied one. To scope results to the user's
  native places, call `find_businesses_near_native_places(db, user, key)`; it returns only active
  businesses near those places that have the plugin enabled, nearest first.
- To let deals sell the plugin's products (core API 1.6), subclass `DealCommerceProvider` (SDK) and
  call `ctx.register_deal_commerce(...)` (one per plugin). `find_products` describes a business's
  products (name, selling price, active) so core can build deal items from them; `currency`,
  `reserve_stock` and `release_stock` back core's deal orders with the plugin's stock (they flush
  but never commit, core owns the transaction). Core finds the provider
  only while the plugin is enabled, at the applied version, and enabled for the deal's business.
- Ship a Postman collection under `postman/` that uses `{{base_url}}` and `{{access_token}}`.
- After changing code, bump `plugin.version`, run `apply`, then restart.

## Local commands

Do not use `alembic revision --autogenerate` blindly: the models don't declare the PostGIS
`spatial_ref_sys` table or several spatial/GIS indexes, so autogenerate proposes dropping them.
Write migrations by hand or strip those operations.

```bash
python -m app.plugins.cli validate
alembic upgrade head                      # plugin registry, bindings, business_plugins
python -m app.plugins.cli apply --key hello
uvicorn app.main:app --reload
# as Super Admin: POST /api/v1/admin/plugins/hello/enable
# then:           GET  /api/v1/plugins/hello/greeting
```

## Phase 0 findings (SQLAlchemy 2.1.1, Alembic 1.20.0)

- A separate `DeclarativeBase` per plugin has its own registry and `MetaData`. A broken plugin
  mapper does not break core queries, even after a global `configure_mappers()`. With the
  shared core `Base`, the same broken mapper breaks every core query.
- `backref` onto a core model makes the core registry depend on the plugin; after a failure
  the core cannot recover. The framework rejects `backref` statically.
- Cross-registry foreign keys work with column objects; string foreign keys and string
  `relationship("CoreModel")` do not.
- `registry.configure(cascade=True)` is needed when plugin models relate to core models.
- Alembic `depends_on` branches take over the core's `alembic_version` row, which breaks plain
  `alembic upgrade head` when plugin locations are not configured. The planned approach for
  plugin migrations (Phase 3) is a per-plugin version table (`plg_<key>_alembic_version`) run
  by the framework, which leaves core history untouched. Verified offline only.

## Proposed rule exceptions (not yet in CLAUDE.md)

These need approval before CLAUDE.md is changed:

1. Plugin endpoints use the manifest `api.tag` instead of an `ApiTag` constant.
2. Plugin endpoints are authored in the plugin's own Postman collection (shipped in its ZIP) and
   copied into the core collection by `python scripts/sync_plugin_postman.py`, so one import
   covers everything. Run it after editing a plugin collection; `_reference` plugins are skipped.
   A plugin collection mirrors the core path `1. Platform App (Mobile)` > `1.5 Businesses` >
   `<plugin folder>`; the script merges two folder levels deep and replaces the plugin folder.
3. Plugin messages, permission names and action names live in the plugin package, not in
   `app/core/messages.py`, `app/core/permissions.py` or `app/core/activity_actions.py`.
4. Type checking runs as `mypy app plugins`.
5. Plugin tests live in the plugin's `tests/` folder and framework tests in
   `tests/unit/plugins/`; both are committed (approved: `.gitignore` re-includes them and
   CLAUDE.md records the exception). The rest of `tests/` stays gitignored.
