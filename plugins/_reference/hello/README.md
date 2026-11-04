# Hello reference plugin

Proves the plugin framework end to end. It has no business features, no models and no
migrations.

- Version 1.1.0, business type `service`.
- Declares one category, `business-service-reference` ("Reference Services") under
  Business > Service, bound to businesses with `include_descendants = true`.
- Endpoints:
  - `GET /api/v1/plugins/hello/greeting`
  - `GET /api/v1/plugins/hello/businesses/{business_id}/greeting` (needs the plugin enabled for
    that business)
- Permission: `plugin.hello.greeting.view` (created by `apply`; Super Admin has it implicitly).
- Capability: menu item `business_greeting` pointing at the business greeting.
- Postman: `postman/hello.postman_collection.json`

Apply and run locally:

```bash
python -m app.plugins.cli apply --key hello
uvicorn app.main:app --reload
```

Then, as Super Admin, `POST /api/v1/admin/plugins/hello/enable`, and as a business owner
`POST /api/v1/me/businesses/{business_id}/plugins/hello`.

Tests: `pytest plugins/_reference/hello/tests`
