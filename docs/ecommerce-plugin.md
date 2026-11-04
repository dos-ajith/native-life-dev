# E-commerce plugin

Status as of 2026-10-22: implemented, packaged, imported and installed once by the user through
Postman (import returned 201, install returned `installed` with `loaded: true`). Not covered by
automated tests. Enable, business enablement, the product and inventory endpoints,
upgrade and uninstall have not been exercised. Treat everything below as built but unverified.

## Where the code is

The source is not in the working tree. `plugins/product/ecommerce/` was emptied on purpose and the
only copy is the package `plugin_packages/ecommerce/ecommerce-1.0.0.zip` (not in git). To edit it,
extract the ZIP back into `plugins/product/ecommerce/`, change the code, bump `version` in
`plugin.toml`, then rebuild with `python -m app.plugins.cli package --key ecommerce` and use the
upgrade endpoint. Uninstalling with `remove_files=true` also backs the plugin up to
`plugin_packages/ecommerce/`.

## Layout (inside the package)

```
plugin.toml                 key ecommerce, version 1.0.0, prefix /plugins/ecommerce, tables plg_ecommerce_*
backend/                    plugin.py (register), models/, schemas/, repositories/, services/, routes/
migrations/0001_initial_schema.py     creates the tables, tracked in plg_ecommerce_migrations
seeders/0001_default_product_categories.py   10 global product categories, idempotent
postman/ecommerce.postman_collection.json
```

Layering follows the core rules: routes call services, services own transactions and activity
logs, repositories only query. Plugin code imports core only through `app.plugins.sdk`.

## Categories

Declared in the manifest and synced by install: Business > Product > E-commerce, plus Fashion &
Apparel, Electronics, Home & Living, Grocery & Food and Beauty & Personal Care. The plugin is bound
to E-commerce with descendants, so businesses under it are compatible. Product categories for
catalog items are a separate plugin table (global defaults from the seeder plus per-business ones).

## What it does

| Area | Endpoints (under `/api/v1/plugins/ecommerce/businesses/{business_id}`) |
|---|---|
| Products | list (filters, search), create, view, update, activate, deactivate, add and remove images |
| Product categories | list, create (per business) |
| Inventory | stock levels, low-stock list, product stock, adjust stock, set low-stock threshold, stock movements |
| Settings | get, update (currency, default low-stock threshold) |

Rules in code: SKU unique per business; stock never below zero; every stock change writes a
movement record under row locks; every write is activity-logged after commit with plugin-local
action names. Permissions: `plugin.ecommerce.{products,inventory,settings}.{view,manage}` (settings has view and
manage too); they are never granted automatically.

## How it is used

1. Import the ZIP (`POST /admin/plugins/import`). This also installs it: migrations, seeders,
   permissions, categories, and loads it into the running process.
2. Enable it (`POST /admin/plugins/ecommerce/enable`).
3. Grant the `plugin.ecommerce.*` permissions to the roles that need them.
4. Enable it for a business (`POST /me/businesses/{id}/plugins/ecommerce`); the business category
   must be under Product > E-commerce.

## Deals (core API 1.6)

Orders are not part of the plugin. Core owns them in shared `orders` and `order_items` tables with
an `order_type` column (`deal` for orders placed from a deal; `direct` is reserved for ordering a
product outside a deal, not built yet), status flow pending, confirmed, shipped, delivered,
cancelled, and the customer (`/me/orders`) and business (`/me/businesses/{id}/orders`) endpoints. The plugin only backs them with products and stock through the deal commerce
provider it registers (`backend/deal_commerce.py`):

- `find_products`: name, description, selling price and active flag, so a deal for a business is
  built from its products (`{product_id, deal_price, quantity}` items, deal price at most the
  selling price, a product once per deal) and re-checked on submit and at order time.
- `currency`: the business's plugin currency setting, stamped on the order.
- `reserve_stock` / `release_stock`: take or return stock for an order inside core's transaction,
  under stock row locks, writing an `order_created` or `order_cancelled` movement that carries the
  core order id (no foreign key). Insufficient stock rejects the order and rolls everything back.

The deal item `quantity` caps the units sold; core counts it from non-cancelled order lines, so a
cancel frees it. Not built: notifying the business owner of a new order, `min_joiners`, payments.

## Known limits

- Only the business owner (or `business.view_any` staff) can call its routes, so there is no
  customer-facing storefront. Customers order through deals.
- Models have no foreign keys to `businesses` or `users`; those exist only in the migration.
- Images are URLs or paths supplied by the client; there is no upload.
- No payments, shipping, tax, discounts, returns or refunds.
- The only migration has no downgrade; uninstall drops the plugin tables instead.
- No plugin-level tests and no frontend or admin assets.

## Enhancement backlog (proposed, in suggested order)

1. Verify what exists: enable it, run the endpoints from the Postman collection against a business,
   and add plugin tests under the plugin's `tests/` folder (committed per the project rules).
2. Customer-facing ordering. Needs the framework opt-in for non-owner, business-keyed routes (a
   product decision noted in `docs/plugins.md`), then public product listing and customer-placed
   orders with a customer identity on the order.
3. Product model: variants and attributes, product image upload through core storage, soft delete
   or archive, bulk import and export.
4. Orders: payment status and payment provider hook, shipping fields and tracking, returns and
   refunds, order notifications through the core notification module.
5. Pricing: discounts and coupons, tax, per-product currency if multi-currency is needed.
6. Inventory: stock reservation for pending orders, low-stock notifications, stock count audits.
7. Reporting: sales and inventory summaries per business and period.
8. Admin and mobile assets through the manifest `frontend` and `admin_panel` metadata, once those
   apps exist.

Each enhancement ships as a new version: new migration file, version bump, repackage, upgrade
endpoint, restart.
