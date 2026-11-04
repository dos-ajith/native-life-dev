# WebSocket foundation

Phase 1 infrastructure only: a versioned endpoint, JWT handshake, connection
manager and a publisher that sync services can call. No business events are
published yet.

> **Single Uvicorn process only.** The connection manager keeps connections in
> memory, so `--workers N` (or several instances) would split users across
> processes and events would silently miss them.

## Endpoint

`/api/v1/ws` (`ws://` / `wss://`). Defined in `app/api/v1/realtime/routes.py`.

## Authentication handshake

The JWT is never sent in the URL (query strings end up in access logs). It is
sent as the first frame after the connection is accepted:

```
client -> {"type": "auth", "token": "<access JWT>"}
server -> {"type": "auth.ok"}
```

The token is the same access token the REST API uses. It is validated by the
same code as HTTP requests: `parse_token_claims` (`app/core/jwt.py`), then
`TokenAuthenticationService` (`app/services/token_authentication_service.py`:
`active_tokens` allow-list + user lookup) and `ensure_active_user`.

| Close code | Meaning |
|---|---|
| 4401 | No/invalid auth frame, auth timeout, bad/expired/revoked token, or token expired while connected |
| 4403 | Account is not active |
| 4408 | Connection idle too long (no frame from the client) |
| 4429 | Too many connections for this user |
| 1008 | Malformed message after authentication |
| 1001 | Server shutting down |

## Lifecycle

1. Server accepts the socket and waits up to `WS_AUTH_TIMEOUT_SECONDS` for the auth frame.
2. Token is validated on a worker thread with a short-lived DB session (no DB connection is held for the life of the socket).
3. The connection is registered in `ConnectionManager` (`user_id -> set of connections`; several devices per user, capped by `WS_MAX_CONNECTIONS_PER_USER`).
4. `auth.ok` is sent and the server loops reading client frames.
5. On disconnect, send failure, send timeout, token expiry or shutdown, the connection is unregistered. Unregistering is idempotent.

The socket is closed with 4401 when the token's `exp` is reached. There is no
refresh in this phase; the client re-authenticates by reconnecting with a new
token.

## Heartbeat

The client sends `{"type": "ping"}` roughly every `WS_PING_INTERVAL_SECONDS`;
the server answers `{"type": "pong"}`. A client silent for twice that interval
is closed with 4408. Unknown message types are ignored.

## Event envelope

Every server-to-client event uses `RealtimeEvent` (`app/realtime/events.py`):

```json
{
  "type": "event.name",
  "id": "9f1c3a52-6a4e-4f0e-9d2e-6b0d3f9b7c11",
  "occurred_at": "2026-10-05T10:00:00+05:30",
  "data": {}
}
```

`id` is unique per event so clients can de-duplicate. Events are hints, not
state: the database stays the source of truth and clients refetch over REST on
reconnect.

## Publishing from a service (Phase 2+)

Services are synchronous and run in worker threads; sockets live on the asyncio
loop. `RealtimePublisher` bridges the two with `asyncio.run_coroutine_threadsafe`
and never raises or blocks the request:

```python
from app.realtime.events import RealtimeEvent
from app.realtime.publisher import get_realtime_publisher

get_realtime_publisher().publish_to_user(
    recipient_id, RealtimeEvent(type="notification.created", data={...})
)
```

Call it only after the database commit (in this codebase repositories commit
before returning, so "after the repository call" is correct). Failures are
logged, a dead or slow client (`WS_SEND_TIMEOUT_SECONDS`) is dropped, and a user
with no connection is a no-op. The lifespan in `app/main.py` binds the running
loop to the publisher at startup and closes all sockets at shutdown.

## Logout

`AuthService.logout` deactivates the `jti`, commits, then calls
`RealtimePublisher.disconnect_token(jti)`. Every socket authenticated with that
token is closed with 4401 ("Token revoked"); other sessions of the same user
stay connected. Cleanup is best-effort: a failure is logged and never fails the
logout, and nothing is closed if revocation itself fails. A revoked token cannot
reconnect because the handshake checks the `active_tokens` allow-list.

## Events published today

| Event | Recipient | Trigger |
|---|---|---|
| `notification.created` | notification recipient (all devices) | `NotificationService._create_if_enabled`, after the notification is persisted |
| `notification.read` | the user (all devices) | `mark_notification_read` (only if it was unread) and `mark_all_notifications_read` (only if rows changed) |
| `follow_request.created` | the target of the request | `UserFollowService._request`, after the request row, activity log and notification |
| `follow_request.accepted` | the requester | `accept` and each request actually accepted in `accept_all_pending` |
| `follow_request.removed` | the target (all their devices) | `decline`, and the requester cancelling via `unfollow` |
| `role_upgrade_request.created` | the reviewers resolved by `NotificationService.notify_role_upgrade_requested` (Super Admins and active users holding `role_upgrade_request.approve`; for Promoter requests also holders of `role_upgrade_request.review_promoter`, i.e. Native Admins), excluding the requester | `RoleUpgradeRequestService.announce_submitted` (account role selection, verification resubmission, legacy submit), after the commit and the notification |
| `role_upgrade_request.approved` | the requesting user (all devices) | `approve`, after the status save and the notification |
| `role_upgrade_request.rejected` | the requesting user (all devices) | `reject`, after the status save and the notification |

```json
{"type": "notification.created", "id": "...", "occurred_at": "...",
 "data": {"notification": {"id": "...", "type": "user_followed", "message": "...",
          "entity_type": "user", "entity_id": "...", "is_read": false, "created_at": "..."},
          "unread_count": 1}}

{"type": "notification.read", "id": "...", "occurred_at": "...",
 "data": {"notification_id": "...", "is_read": true, "unread_count": 0}}

{"type": "notification.read", "id": "...", "occurred_at": "...",
 "data": {"all_read": true, "unread_count": 0}}
```

Follow-request payloads (recipients are derived from the request relationship,
never from client input):

```json
{"type": "follow_request.created",  "data": {"user": {"id": "...", "first_name": "...", "last_name": "...", "profile_image_url": null}}}
{"type": "follow_request.accepted", "data": {"user": {"id": "...", "first_name": "...", "last_name": "...", "profile_image_url": null}}}
{"type": "follow_request.removed",  "data": {"user_id": "<requester whose pending request no longer exists>"}}
```

Role-upgrade payloads (the requested role is the existing `RoleSummary`; no email,
documents, reviewer identity or `review_note` is included, clients refetch the
request over REST for details):

```json
{"type": "role_upgrade_request.created",  "data": {"request_id": "...", "user": {"id": "...", "first_name": "...", "last_name": "...", "profile_image_url": null}, "role": {"id": "...", "name": "Promoter", "slug": "promoter"}}}
{"type": "role_upgrade_request.approved", "data": {"request_id": "...", "status": "approved", "role": {"id": "...", "name": "Promoter", "slug": "promoter"}}}
{"type": "role_upgrade_request.rejected", "data": {"request_id": "...", "status": "rejected"}}
```

The reviewer set is resolved once, by `notify_role_upgrade_requested` (which now
returns it), and reused for the event, so the two cannot drift. A reviewer who
muted `system_updates` gets no notification but still gets the event. Known
limitation: `RoleUpgradeRequestService.approve` still commits the role
assignment and the status change separately; the event is published only after
the status save, so a failure in between produces no event.

`created.user` is the requester and `accepted.user` is the person who accepted.
A decline is never sent to the requester (the product intentionally does not
tell them); `removed` only keeps the target's own devices in sync. These events
are separate from `notification.created`, which is still sent by
`NotificationService` for the notification centre.

`notification` is the same `NotificationRead` the REST API returns (so
`created_at` uses the app's display format). `unread_count` is one indexed
`COUNT` run only when the recipient has an active socket; offline users cost no
extra queries. Events are never queued: offline users read the notification
over REST after reconnecting.

## Configuration

| Setting | Default | Purpose |
|---|---|---|
| `WS_AUTH_TIMEOUT_SECONDS` | 10 | Time allowed to send the auth frame |
| `WS_SEND_TIMEOUT_SECONDS` | 5 | Per-send timeout before a connection is dropped |
| `WS_PING_INTERVAL_SECONDS` | 25 | Expected client ping interval (idle limit is 2x) |
| `WS_MAX_CONNECTIONS_PER_USER` | 5 | Concurrent sockets per user |

## Why no Redis yet

One process needs no shared bus, and the app has no Redis today. When the API
runs on more than one process, swap the delivery behind `RealtimePublisher` for
a pub/sub fan-out (Redis, or Postgres `LISTEN/NOTIFY`); the endpoint, envelope
and handshake do not change.
