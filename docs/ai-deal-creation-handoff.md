# AI-assisted deal creation: handoff

Branch: `feature/deal-categories`. Nothing from this task is committed. Wait for manual verification before committing.

## Goal

The Native Assistant (`POST /api/v1/ai/ask`) creates a **draft** deal through a question-and-answer flow. Answers collected so far live in the DB temporarily. When the deal is created, the stored answers are deleted. The mechanism is reusable for future flows (posts, products for a business).

## How it works

1. A user with the `DEAL_CREATE` permission gets four extra assistant tools: `list_deal_categories`, `save_deal_details`, `create_deal_draft`, `discard_deal_details`.
2. The model asks for missing fields, then calls `save_deal_details` after each message that gives new details. Fields are merged into one `ai_drafts` row (user + kind).
3. On every later `/ai/ask`, the saved details and the missing-field list are appended to the user's message ("Saved deal details in progress ..."). No chat history is sent by the client.
4. When nothing is missing the model reads back a summary. After the user confirms it calls `create_deal_draft`, which builds `DealCreate`, calls `DealService.create`, and deletes the `ai_drafts` row.
5. Tool problems (validation errors, `AppError`) come back as `created=false, problems=[...]` so the model can ask the user to correct them.
6. The response has `data.created` (`{kind, id, title, status}`) only when a draft was created. It is never published; cover images and submit still happen through the deals endpoints.
7. Saved details expire after 24h (`AI_DRAFT_TTL`). Cancelling calls `discard_deal_details`.

## Files

Model, migration, schema docs
- `app/models/ai_draft.py` (`AIDraft`, `AIDraftKind`; `kind` is varchar(50), so a new kind needs no migration)
- `migrations/versions/f1a7c3d9e285_add_ai_drafts.py` (rewritten once locally before any commit; head after `e5b2c9d7a136`)
- `docs/schema.dbml` (`ai_drafts` table and FK)

Generic draft layer
- `app/repositories/ai_draft_repository.py`
- `app/services/ai_draft_service.py` (`AIDraftService[DetailsT]`: get, progress, save/merge, discard, clear)
- `app/schemas/ai_draft.py` (`AIDraftDetails`, `AIDraftProgressRead`, `AICreatedEntityRead`)
- `app/ai/tools/draft_tools.py` (`SaveDraftDetailsTool`, `DiscardDraftTool`, `CreateDraftResult`, `NoArgs`)
- `app/ai/draft_flows.py` (`AIDraftFlow`, `DRAFT_FLOWS`, `render_draft_progress`)

Deal flow (first plug-in)
- `app/schemas/ai_deal_draft.py` (`DealDraftDetails`, `AIDealItem`, `missing_fields()`)
- `app/services/ai_deal_creation_service.py` (`deal_drafts`, `AIDealCreationService.complete`)
- `app/ai/tools/deal_tools.py` (the four deal tools, `can_create_deals`)

Wiring and prompt
- `app/ai/service.py` (registers flow tools, appends progress, captures `created`, adds current date/time to instructions)
- `app/ai/policy.py` (deal-creation section; write exception for draft deals)
- `app/schemas/ai.py` (`AIAskResponse.created`)
- `app/core/activity_actions.py` (`AI_DRAFT_SAVED`, `AI_DRAFT_DISCARDED`), `app/core/messages.py` (`AIMessages.DEAL_CREATE_FORBIDDEN`, `DRAFT_EMPTY`)

Postman and tester
- `postman/native-life-api.postman_collection.json`: only the "Ask" description changed
- `tools/api-tester/app.html`: Clear button on the console panel, created-draft card with "Open my deals"

Tests (the `tests/` folder is gitignored)
- `tests/integration/test_ai_draft.py`
- `tests/unit/ai/test_deal_assistant_flow.py`, `tests/unit/ai/test_deal_draft_details.py`
- `ACTOR` in `tests/unit/ai/test_ai_policy.py` and `test_search_flow.py` now has `approved_roles=[]`

## Status

- Migration applied locally. `ruff check app migrations` and `mypy app` pass.
- `pytest tests/unit/ai tests/integration/test_ai_draft.py` passes (95 tests).
- Full `pytest` has 30 collection errors in unrelated files: they import `AuthenticatedUserRead` from `app/schemas/user.py`, which does not define it. Not caused by this task. The run of all collectable tests (`--continue-on-collection-errors`) was still in progress when this was written; re-run it.
- `ruff check .` also reports an E501 in `scripts/seed_popular_places.py` (pre-existing, not touched).
- Not tried against the real AI provider and not tried in the tester UI in a browser.

## Open decisions and next steps

1. **Business deals are not supported.** A deal with `business_id` needs items chosen from the business catalogue (`product_id`, via the plugin product provider), so the assistant only creates individual-seller deals and tells the user to use the app for business deals. Decide whether to add this (needs list-my-businesses and product-search tools).
2. **Manual check:** run `/ai/ask` as a user with `DEAL_CREATE` and a primary native place; confirm the flow, that the row appears in `ai_drafts` and disappears after creation, and that the draft shows under `GET /me/deals`.
3. **Prompt tuning:** the deal section in `app/ai/policy.py` is untested with a live model. Check that it asks one or two questions at a time and does not call `create_deal_draft` before confirmation.
4. **Future flows:** write a details model (subclass `AIDraftDetails` with `missing_fields()`), a creation service, tools built on `SaveDraftDetailsTool` and `DiscardDraftTool`, add a value to `AIDraftKind`, and append an `AIDraftFlow` to `DRAFT_FLOWS`. Add the matching section to the system prompt.
5. **Related fix from the same session:** `DealAccessPolicy.ensure_not_publisher` now also blocks the business owner from joining their own business's deal. It has no test yet.
6. Commit only after manual verification (project rule).
