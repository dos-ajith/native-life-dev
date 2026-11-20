# Packages plugin

Handoff notes. Last updated 2026-11-17 (day 2: Travel and Resorts refinement, then owner/promoter ownership refinement). The plugin is applied and enabled on
the local dev DB at version 1.4.0 and lives on `feature/packages` (not pushed). See `plugins/service/packages/README.md`
for the endpoint and wizard reference, and `docs/plugins.md` for the framework.

## What it is

A plugin for **Travel** and **Resort** businesses (`plugins/service/packages/`, key `packages`, needs core API
`>=1.9,<2.0`). A package has a title, description, ordered map destinations with their own media, a business, a price
and offer, and the locations where it is listed. A business owner or a Promoter builds it in a 6-step wizard that
saves a draft after every step. A Promoter's package needs the business owner's approval before it is published.
Customers browse published packages and book them through core's Bookings module (request, then the owner confirms).

## Decisions (do not reopen)

| Topic | Decision |
|---|---|
| Categories | The manifest binds only `business-service-travel-tours` (Travel) and `business-service-hotels-stays` (Resorts) with descendants. The other four sub-categories and the Service root are no longer bound. Their rows still exist in `categories` (the framework never deletes categories; none has a business). Existing display names are unchanged (`Travel & Tours`, `Hotels & Stays`); rename them through the admin category API if wanted. |
| Business category (owner) | After enabling Packages the owner chooses Travel or Resorts (`/businesses/{id}/package-category`, table `plg_packages_business_config`). A business already in the Travel or Resorts category uses that category and cannot pick the other. Locked once the business has packages. Package creation is refused until it is set. The manifest also binds the Service root exactly (no descendants) so a verified Service business created under just "Service" is offered the plugin; Food & Dining and other leaves are not. |
| Package category | `travel` or `resort`. Effective business category = category chain (Travel/Resorts leaf) first, then the owner's saved choice. Owners create only for their own business (path business, owner check); Promoters choose it when creating and can only pick an eligible business whose effective category matches. Fixed after creation. Submit re-checks the match. |
| Package types | Removed from the API and code. The `plg_packages_package_types` table is kept (safe multi-step) and can be dropped by a later migration. |
| Destinations | `plg_packages_route_points` (sequence, name, coordinates). Travel: 2 to 20 pins connected in order. Resort: exactly one pin plus an `origin_*` snapshot of the creator's primary native place, set by the server. Lines are straight segments between pins (no routing engine). |
| Media | Belongs to a route point (`route_point_id`). Up to 10 files per location, same formats and 50 MB limit. Travel needs at least one per location. Legacy media has no route point. |
| Pricing | Core has no business price. The owner can store a default price per business (`plg_packages_business_pricing`); a package either offers against it (`pricing_source = business_default`, original price copied from it) or uses manual prices. Order links still snapshot both prices. |
| Visibility | Unchanged: primary listing location plus extras. It only affects Explore listing, not destinations. Required to publish. |
| Role separation | The `/promoter` routes require the verified `promoter` role (router-level dependency). Owners use `/businesses/{id}` routes; a business owner, an individual user or an admin gets 403 on promoter routes. Core change: a business that is not active (not yet verified) is offered no plugins at all. |
| Approval | New statuses `pending_approval` and `rejected`, history in `plg_packages_approval_events`. Promoters submit; only the business owner approves or rejects; no promoter publish route. Owners still publish their own drafts directly. A promoter can edit only draft or rejected packages; a pending package is locked for everyone. |
| Notifications | Core change (API 1.9): `notify_approval_requested` and `notify_approval_decided` in `app/plugins/approvals.py` reuse `NotificationService` (in-app, WebSocket, browser push) and add an email to the owner. New enum values `plugin_approval_*` (notification) and `plugin_approval_requested` (email) came from core migration `a3c5e7f91b24`. |
| Inclusions | Kept as an optional "what each business provides" list; no longer required to publish. |
| Bookings | Service plugins use bookings, not orders. Core (API 1.10) has a Bookings module (`bookings` table, `/businesses/{id}/bookings`, `/me/bookings`, `/me/businesses/{id}/bookings`). The plugin only registers a `BookingProvider` that says which packages are bookable and at what price. Flow: requested → confirmed or rejected → completed, cancellable by the customer (requested, confirmed) or the owner (confirmed). Owner gets in-app, WebSocket, push and email on a request; the customer gets in-app, WebSocket and push on each response. No payment yet. Packages left the core cart, checkout and deals; old `order_links` and the `package-orders` routes stay as read-only history. |
| Out of scope | Admin approval, payments, real frontend or mobile app, road routing, per-customer route origin. |

## Data

Tables `plg_packages_*`, migrations `0001_initial_schema`, `0002_travel_resort_approval` and `0003_business_package_category` (additive; keeps packages,
media and order links; backfills one route point per package whose primary location has coordinates). `business_id` on
packages is nullable so a Promoter can draft before choosing the business; a published package must have one (DB check).
`docs/schema.dbml` is for core Alembic only; its two enums were extended for the core migration.

## Run, test, deploy

```bash
python -m app.plugins.cli validate
python -m app.plugins.cli apply --key packages      # then restart; the folder hash includes every file
python -m app.plugins.cli package --key packages    # ZIP into plugin_packages/packages/
pytest plugins/service/packages/tests               # SQLite in memory
PACKAGES_TEST_PG=1 pytest plugins/service/packages/tests   # real Postgres, throwaway test_sp_<hex> schema
ruff check . && mypy app plugins
```

Order on a new environment: deploy, `alembic upgrade head` (core migration first), `validate`, `apply`, restart, admin
enables the plugin, then the owner enables it for the business.

## Traps

- Applying changes the folder hash: any edit under `plugins/service/packages/` (tests, Postman, README too) after `apply` makes the loader skip the plugin until the version is bumped and applied again.
- The plugin's `tests/` folder is lost by uninstall with `remove_files`, ZIP upgrade and ZIP import. Restore with `git checkout -- plugins/service/packages/tests`; a copy is at `/Users/ajithm/App/packages-plugin-source-backup/` (taken before this refinement).
- Plugin seeders run before the framework inserts permission rows, so a seeder must insert its own.
- Serve the api-tester from `tools/api-tester` bound to 127.0.0.1; serving the repo root exposes `.env` and `secrets/`.
- The Promoter role has no `business.create`; Promoters use the `/promoter` routes.

## Known gaps

1. WebSocket and push were not observed live; email rows are recorded as `pending` with provider `mandrill` in dev. Booking and approval flows are covered by tests with the notification helpers faked, and were walked through in the api-tester.
2. The api-tester notification list does not deep-link a `packages_package` notification to the review screen; the owner opens Package pending approval from Manage packages.
3. Explore still lists published packages of a deactivated business or one that disabled the plugin (ordering then fails).
4. The resort route starts at the creator's native place, not the customer's.
5. No cross-business list for Native Admin or Super Admin.
