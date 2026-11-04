# E-commerce plugin

Product catalog and inventory for product businesses (`plugins/product/ecommerce`), v1.2.2.

- Manifest: `plugin.toml` (key `ecommerce`, tables `plg_ecommerce_*`, API prefix `/api/v1/plugins/ecommerce`).
- Backend: `backend/` (models, schemas, repositories, services, routes, `plugin.py`).
- Migrations: `migrations/NNNN_name.py` (`upgrade(op)`), tracked in `plg_ecommerce_migrations`.
- Seeders: `seeders/NNNN_name.py` (`seed(connection)`), idempotent.
- Explore (mobile): `GET /explore/products`, `GET /explore/products/{id}` and `GET /explore/categories` list active, in-stock products from businesses near the caller's native places; buying uses the core direct-order endpoint `POST /api/v1/businesses/{business_id}/orders`.
- Product images are uploaded (JPEG, PNG, WebP up to 5 MB, validated by content) into the core media directory (`UPLOAD_DIR`) under `plugins/ecommerce/<business_id>/`.
- Postman: `postman/ecommerce.postman_collection.json`.

Install: import the ZIP with `POST /api/v1/admin/plugins/import`, enable it, enable it for a business and grant the `plugin.ecommerce.*` permissions. Upgrade an installed 1.0.0 with `POST /api/v1/admin/plugins/upgrade`.
