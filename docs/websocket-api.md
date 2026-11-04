# Native Life WebSocket API

Real-time updates for notifications, follow requests and role-upgrade requests. REST APIs are in [Swagger](/docs).

## Quick Start

### Step 1 — Connect

```text
ws://127.0.0.1:8000/api/v1/ws
```

Production:

```text
wss://<production-domain>/api/v1/ws
```

Open a WebSocket connection using the authenticated user's session. Do **not** put the JWT in the URL.

### Step 2 — Authenticate

Send this immediately after the connection opens (use the `access_token` from `POST /api/v1/auth/login`):

```json
{
  "type": "auth",
  "token": "<JWT>"
}
```

You receive:

```json
{
  "type": "auth.ok"
}
```

Wait for `auth.ok` before treating the connection as ready. No auth message within 10 seconds closes the socket.

### Step 3 — Listen for events

| Event | What it means | Frontend action |
|---|---|---|
| `notification.created` | New notification | Update notification list/badge |
| `notification.read` | Notification state changed | Update notification state |
| `follow_request.created` | New follow request | Update follow requests |
| `follow_request.accepted` | Follow request accepted | Update relationship |
| `follow_request.removed` | Follow request removed | Remove/update request |
| `role_upgrade_request.created` | New account role verification request | Update admin pending requests |
| `role_upgrade_request.approved` | Account role verified | Refresh `account_role` (now `verified`) |
| `role_upgrade_request.rejected` | Verification rejected | Refresh `account_role` (the requested role is removed; the user is an Individual User again) |
| `community.message.created` | New message in a community you belong to | Append to that community's chat |
| `community.message.deleted` | A community chat message was deleted | Remove it from that chat |
| `community.post.created` | A post was published in a community you belong to | Fetch the post and add it to the timeline |
| `community.poll.created` | The owner created a poll in a community you belong to | Fetch the poll and add it to the timeline |
| `community.read` | You opened a community on another device | Set that community's unread badge to 0 |
| `direct_message.created` | A one-to-one message was sent to you (or by you on another device) | Append to that chat, or bump the unread badge |
| `direct_message.read` | The other person read your messages | Show "read" ticks on your sent messages |
| `direct_message.typing` | The other person is typing to you | Show "typing…" for about 5 seconds |
| `presence.changed` | Someone you chat with went online or offline | Update "online" / "last seen" |

### Keep the connection alive

Send `{"type":"ping"}` about every 25 seconds. The server answers `{"type":"pong"}`. A connection that sends nothing for about 50 seconds is closed.

## Basic Frontend Flow

```text
Login
  ↓
Get JWT
  ↓
Connect WebSocket
  ↓
Send auth message
  ↓
Receive auth.ok
  ↓
Listen for events
  ↓
Update UI
```

```text
WebSocket disconnects
  ↓
Reconnect
  ↓
Authenticate again
  ↓
Fetch latest data from REST API
```

## Frontend Example

```javascript
const socket = new WebSocket("ws://127.0.0.1:8000/api/v1/ws");
let pingTimer;

socket.onopen = () => {
  socket.send(JSON.stringify({ type: "auth", token: JWT }));
};

socket.onmessage = (event) => {
  const message = JSON.parse(event.data);

  switch (message.type) {

    case "auth.ok":
      // WebSocket ready: start pings, then fetch latest REST data
      pingTimer = setInterval(
        () => socket.send(JSON.stringify({ type: "ping" })), 25000);
      break;

    case "pong":
      break;

    case "notification.created":
      // Update notifications
      break;

    case "notification.read":
      // Update notification state
      break;

    case "follow_request.created":
      // Update follow requests
      break;

    case "follow_request.accepted":
      // Update relationship
      break;

    case "follow_request.removed":
      // Remove/update request
      break;

    case "role_upgrade_request.created":
      // Update pending role requests
      break;

    case "role_upgrade_request.approved":
      // Update role/request state
      break;

    case "role_upgrade_request.rejected":
      // Update role/request state
      break;
  }
};

socket.onclose = (closeEvent) => {
  clearInterval(pingTimer);
  // closeEvent.code tells you why (see Close Codes). Usually: reconnect, auth again,
  // then fetch latest data from REST.
};
```

Ignore unknown event types and unknown fields, so new events never break older app versions.

## Event Format

Every event has the same envelope. The event-specific payload is in `data`.

```json
{
  "type": "notification.created",
  "id": "9f1c3a52-6a4e-4f0e-9d2e-6b0d3f9b7c11",
  "occurred_at": "2026-10-05T11:57:50.233528+05:30",
  "data": {}
}
```

| Field | Type | Description |
|---|---|---|
| `type` | string | Event name |
| `id` | string | Unique event id. Use it to ignore duplicates |
| `occurred_at` | string | ISO-8601 timestamp |
| `data` | object | Event-specific payload |

`auth.ok` and `pong` are plain `{"type": ...}` messages, not events.

---

## Notifications

### `notification.created`

**When:** A new notification is created.

**Who receives it:** The notification recipient.

**Frontend action:** Add the notification and set the badge to `unread_count`.

```json
{
  "type": "notification.created",
  "id": "...",
  "occurred_at": "...",
  "data": {
    "notification": {
      "id": "...",
      "type": "user_followed",
      "message": "Someone started following you",
      "entity_type": "user",
      "entity_id": "...",
      "is_read": false,
      "created_at": "05-10-2026 11:34 AM"
    },
    "unread_count": 2
  }
}
```

`created_at` uses the same display format as the REST notification list (not ISO). `message` is ready to display. Use `entity_type` and `entity_id` to open the related screen.

<details>
<summary>Notification types</summary>

| `type` | `entity_type` | `entity_id` |
|---|---|---|
| `user_followed` | `user` | follower's user id |
| `follow_requested` | `user` | requester's user id |
| `follow_request_accepted` | `user` | accepter's user id |
| `post_liked` | `post` | post id |
| `post_commented` | `post` | post id |
| `role_upgrade_requested` | `role_upgrade_request` | request id |
| `role_upgrade_approved` | `role_upgrade_request` | request id |
| `role_upgrade_rejected` | `role_upgrade_request` | request id |
| `category_approved` | `category` | category id |
| `category_rejected` | `category` | category id |

Not sent if the user turned that notification type off in their notification settings, or if they caused the action themselves.

</details>

### `notification.read`

**When:** A notification (or all of them) was marked as read, via `PATCH /api/v1/me/notifications/{id}/read` or `POST /api/v1/me/notifications/read-all`.

**Who receives it:** The notification owner, on all of their devices.

**Frontend action:** Mark the notification(s) as read and set the badge to `unread_count`.

One notification:

```json
{
  "type": "notification.read",
  "id": "...",
  "occurred_at": "...",
  "data": {
    "notification_id": "...",
    "is_read": true,
    "unread_count": 1
  }
}
```

All notifications (`data.all_read` is present instead of `notification_id`):

```json
{
  "type": "notification.read",
  "id": "...",
  "occurred_at": "...",
  "data": {
    "all_read": true,
    "unread_count": 0
  }
}
```

---

## Follow Requests

A follow request exists only when the target's profile is **private**. Following a public profile sends only `notification.created`.

```text
User A sends follow request
        ↓
Backend
        ↓
User B WebSocket
        ↓
follow_request.created
        ↓
User B updates UI
```

### `follow_request.created`

**When:** Someone sends a follow request to a private user (`POST /api/v1/users/{id}/follow`).

**Who receives it:** The user who was asked (the target).

**Frontend action:** Add `data.user` to the incoming follow requests.

```json
{
  "type": "follow_request.created",
  "id": "...",
  "occurred_at": "...",
  "data": {
    "user": {
      "id": "...",
      "first_name": "Asha",
      "last_name": "Rao",
      "profile_image_url": null
    }
  }
}
```

`data.user` is the person who sent the request.

### `follow_request.accepted`

**When:** The target accepts the request (`POST /api/v1/users/{id}/follow/accept`), or the target switches to a public profile and pending requests are accepted automatically.

**Who receives it:** The person who sent the request.

**Frontend action:** Change "Requested" to "Following" for `data.user`.

```json
{
  "type": "follow_request.accepted",
  "id": "...",
  "occurred_at": "...",
  "data": {
    "user": {
      "id": "...",
      "first_name": "Bala",
      "last_name": "Menon",
      "profile_image_url": null
    }
  }
}
```

`data.user` is the person who accepted.

### `follow_request.removed`

**When:** A pending request is gone: the target declined it, the sender cancelled it (`DELETE /api/v1/users/{id}/follow`), or the target accepted it.

**Who receives it:** The target (the user whose incoming requests changed), on all of their devices. Never the sender.

**Frontend action:** Remove `data.user_id` from the incoming follow requests. Safe to run twice (the device that acted also receives it).

```json
{
  "type": "follow_request.removed",
  "id": "...",
  "occurred_at": "...",
  "data": {
    "user_id": "..."
  }
}
```

`data.user_id` is the sender of the request.

> There is **no** "declined" event. A sender is never told that their request was declined.

---

## Role Upgrade Requests

### `role_upgrade_request.created`

```text
User submits role upgrade
        ↓
Backend
        ↓
Admin WebSocket
        ↓
role_upgrade_request.created
```

**When:** A verification request is created: when a user selects an account role that requires verification (`PUT /api/v1/users/me/account-role`), resubmits verification (`POST /api/v1/users/me/account-role/verification`), or uses the legacy `POST /api/v1/upgrade-requests`.

**Who receives it:** Reviewers: Super Admins and other active users holding `role_upgrade_request.approve`, plus Native Admins (`role_upgrade_request.review_promoter`) for Promoter requests only. Not the user who submitted it.

**Frontend action:** Add the request to the admin pending list (or refetch it).

```json
{
  "type": "role_upgrade_request.created",
  "id": "...",
  "occurred_at": "...",
  "data": {
    "request_id": "...",
    "user": {
      "id": "...",
      "first_name": "Asha",
      "last_name": "Rao",
      "profile_image_url": null
    },
    "role": {
      "id": "...",
      "name": "Promoter",
      "slug": "promoter"
    }
  }
}
```

### `role_upgrade_request.approved`

```text
Admin approves
        ↓
Backend
        ↓
Requester WebSocket
        ↓
role_upgrade_request.approved
```

**When:** A reviewer approves the request (`POST /api/v1/admin/upgrade-requests/{id}/approve`). The role was already assigned when the user selected it; approval only marks that assignment verified.

**Who receives it:** The user who made the request (all their devices). No one else.

**Frontend action:** Mark the request approved and refresh `GET /api/v1/auth/me`; `account_role.verification_status` is now `verified`.

```json
{
  "type": "role_upgrade_request.approved",
  "id": "...",
  "occurred_at": "...",
  "data": {
    "request_id": "...",
    "status": "approved",
    "role": {
      "id": "...",
      "name": "Promoter",
      "slug": "promoter"
    }
  }
}
```

### `role_upgrade_request.rejected`

```text
Admin rejects
        ↓
Backend
        ↓
Requester WebSocket
        ↓
role_upgrade_request.rejected
```

**When:** A reviewer rejects the request (`POST /api/v1/admin/upgrade-requests/{id}/reject`).

**Who receives it:** The user who made the request (all their devices). No one else.

**Frontend action:** Mark the request rejected. The reviewer's note is not in the event; fetch the request with `GET /api/v1/upgrade-requests/{id}` if you need to show it.

```json
{
  "type": "role_upgrade_request.rejected",
  "id": "...",
  "occurred_at": "...",
  "data": {
    "request_id": "...",
    "status": "rejected"
  }
}
```

> Approve and reject also create a normal notification, so the requester gets `notification.created` first and then the role event.

## Community Chat

Members chat with each other inside a community. Messages are sent and loaded over REST (`POST` and `GET /api/v1/communities/{id}/messages`); the WebSocket only pushes new activity to everyone who is currently connected.

### `community.message.created`

**When:** A member sends a message with `POST /api/v1/communities/{id}/messages`.

**Who receives it:** Every active member of that community who has a connection open, including the sender's other devices. Removed or blocked members stop receiving events.

**Replies:** `reply_to` is `null` for a normal message. For a reply it holds a short preview of the message being answered (`id`, `sender_name`, `content` cut to 100 characters). Show the preview inside the reply bubble, and when the user taps it scroll to the message with that `id`. If the original was deleted, `reply_to` is `null`.

**Frontend action:** If that community's chat is open, append the message (skip it if you already added it from the `POST` response, matching on `message.id`). Otherwise show an unread badge.

```json
{
  "type": "community.message.created",
  "id": "...",
  "occurred_at": "...",
  "data": {
    "message": {
      "id": "...",
      "community_id": "...",
      "sender": { "id": "...", "first_name": "Asha", "last_name": "K", "profile_image_url": null },
      "content": "See you at 6am",
      "reply_to": { "id": "...", "sender_name": "Ravi M", "content": "What time are we meeting?" },
      "created_at": "..."
    }
  }
}
```

### `community.message.deleted`

**When:** The sender or the community owner deletes a message (`DELETE /api/v1/communities/{id}/messages/{message_id}`).

**Who receives it:** Every active member with a connection open.

**Frontend action:** Remove the message with that id from the chat.

```json
{
  "type": "community.message.deleted",
  "id": "...",
  "occurred_at": "...",
  "data": {
    "community_id": "...",
    "message_id": "..."
  }
}
```

### `community.post.created`

**When:** A post is created with `status=published` inside a community, or a draft community post is published (`PATCH /api/v1/posts/{id}` with `status=published`). Later edits do not send it again, and drafts never do.

**Who receives it:** Every active member of that community who has a connection open, including the author's other devices.

**Frontend action:** The event only carries ids. Fetch the post with `GET /api/v1/posts/{post_id}` (or reload the top of the timeline) and add it to the community timeline. Show an unread badge if that community is not open.

```json
{
  "type": "community.post.created",
  "id": "...",
  "occurred_at": "...",
  "data": {
    "community_id": "...",
    "post_id": "...",
    "author_id": "..."
  }
}
```

### `community.poll.created`

**When:** The community owner creates a poll (`POST /api/v1/communities/{id}/polls`).

**Who receives it:** Every active member of that community who has a connection open, including the owner's other devices.

**Frontend action:** Fetch the poll with `GET /api/v1/communities/{community_id}/polls/{poll_id}` (or reload the top of the timeline) and add it to the community timeline. Show an unread badge if that community is not open.

```json
{
  "type": "community.poll.created",
  "id": "...",
  "occurred_at": "...",
  "data": {
    "community_id": "...",
    "poll_id": "...",
    "author_id": "..."
  }
}
```

### `community.read`

**When:** The user marks a community as read (`POST /api/v1/communities/{id}/read`), for example by opening it on another device.

**Who receives it:** Only that user's own connected devices.

**Frontend action:** Set the unread badge for `community_id` to 0.

```json
{
  "type": "community.read",
  "id": "...",
  "occurred_at": "...",
  "data": {
    "community_id": "...",
    "unread_count": 0
  }
}
```

### Unread badges

`GET /api/v1/communities/mine` (and every other community response) includes `unread_count`: the chat messages plus published posts from other members since the user last marked the community read. A new member starts at 0. Your own messages and posts, removed posts and posts from blocked authors are never counted. While a community is closed, add 1 for each `community.message.created` or `community.post.created` from someone else; call `POST /api/v1/communities/{id}/read` when the user opens it.

### Opening a community

Load `GET /api/v1/communities/{id}/timeline` once. It returns chat messages, posts and polls mixed in time order, newest first (each item has `type` `message`, `post` or `poll`). Scroll back with `before=<next_before>` while `has_more` is true. Then keep the screen up to date from `community.message.created`, `community.message.deleted`, `community.post.created` and `community.poll.created`.

> If the socket was disconnected, reload the latest timeline with `GET /api/v1/communities/{id}/timeline` after reconnecting.

---

## Direct Chat (one-to-one)

Messages are sent and loaded over REST (`POST` and `GET /api/v1/chats/{user_id}/messages`, inbox at `GET /api/v1/chats`). The WebSocket pushes live activity and carries typing.

Who may message whom is decided by the server on every send and typing event: the recipient must allow messages (`allow_messages`), must accept the sender (`who_can_message`: `everyone` or `connections`), and neither side may have blocked the other. A blocked or refused `POST` returns `403`; typing events that are not allowed are silently dropped.

### `direct_message.created`

**Who receives it:** The recipient and the sender's other devices.

**Frontend action:** If that chat is open append the message (skip it if you already added it from the `POST` response, matching on `message.id`) and call `POST /api/v1/chats/{user_id}/read`. Otherwise raise the unread badge.

```json
{
  "type": "direct_message.created",
  "id": "...",
  "occurred_at": "...",
  "data": {
    "message": {
      "id": "...",
      "conversation_id": "...",
      "sender_id": "...",
      "content": "Hello!",
      "read_at": null,
      "created_at": "..."
    }
  }
}
```

### `direct_message.read`

**When:** The other person calls `POST /api/v1/chats/{user_id}/read`.

**Frontend action:** Mark your messages in that conversation as read.

```json
{
  "type": "direct_message.read",
  "id": "...",
  "occurred_at": "...",
  "data": { "conversation_id": "...", "reader_id": "..." }
}
```

### Typing indicator

Typing is the only thing the client sends over the socket besides `auth` and `ping`. It is never stored.

Send while the user types in a chat:

```json
{ "type": "typing", "user_id": "<the other person's id>", "is_typing": true }
```

- Send `is_typing: true` when the user starts typing, then repeat it at most every 3 seconds while they keep typing.
- Send `is_typing: false` when the input becomes empty, the message is sent, or the field loses focus.
- The server sends no reply. A malformed typing message closes the socket with `1008`.

The other person receives:

```json
{
  "type": "direct_message.typing",
  "id": "...",
  "occurred_at": "...",
  "data": { "user_id": "<who is typing>", "is_typing": true }
}
```

**Frontend action:** Show "typing…" in that chat. Hide it on `is_typing: false`, when that person's message arrives, or after about 5 seconds without another `true` (the sender's app may have been killed).

### Online and last seen

`GET /api/v1/chats/{user_id}/presence` and the `presence` field of every conversation in `GET /api/v1/chats` return `{ visible, is_online, last_seen_at }`. When `visible` is `false` the user hides it (their `activity_visibility` setting is `followers` and you do not follow them, or `private`), or one of you blocked the other; show nothing.

`presence.changed` carries the same object when someone you have chatted with connects or disconnects:

```json
{
  "type": "presence.changed",
  "id": "...",
  "occurred_at": "...",
  "data": { "user_id": "...", "visible": true, "is_online": false, "last_seen_at": "..." }
}
```

A user counts as online while at least one of their devices has an open socket, so keep the socket open while the app is in the foreground and close it when the app goes to the background.

### Push notifications for new messages

When a message is sent and the recipient has **no open WebSocket**, the server sends a push (title is the sender's name, body is the message text cut to 120 characters). The recipient's `push_enabled` and `messages` notification settings are respected. While the recipient is connected no push is sent, because they already get `direct_message.created`.

The push `data` payload:

```json
{
  "type": "direct_message",
  "sender_id": "...",
  "conversation_id": "...",
  "message_id": "..."
}
```

On tap, open the chat with `sender_id` and load `GET /api/v1/chats/{sender_id}/messages`. These pushes are not added to `GET /api/v1/me/notifications`.

---

## REST vs WebSocket

| REST | WebSocket |
|---|---|
| Get/create/update data | Receive real-time updates |
| Source of truth | Real-time notification |
| Used for initial page data | Used after data changes |
| Used after reconnect | Best-effort delivery |

> WebSocket does not replace REST.

```text
Open app
   ↓
GET REST data
   ↓
Open WebSocket
   ↓
Receive real-time changes
```

## Reconnection

If the WebSocket disconnects:

```text
1. Reconnect
2. Send auth again
3. Wait for auth.ok
4. Fetch latest REST data
5. Continue listening
```

- There is **no event replay** and **no offline queue**. Events missed while disconnected are not re-sent.
- Missed events are recovered through REST (for example `GET /api/v1/me/notifications`, `GET /api/v1/me/follow-requests`, `GET /api/v1/upgrade-requests`).
- Reconnect with a growing delay (1 s, 2 s, 4 s ... up to about 30 s).
- The JWT expires after 30 minutes by default and the socket then closes with `4401`. Get a new JWT (log in again) before reconnecting.

## Multiple Devices

```text
User
 ├── Mobile
 ├── Web
 └── Tablet

       ↓

All active connections receive the event
```

Each device gets the same event, including the device that caused it. Make handlers safe to run twice (marking as read, removing a request). Up to 5 connections per user.

---

## Security

- Authentication uses the same JWT as REST. It is sent in the first message, never in the URL.
- Logging out closes the sockets that use that token, and a logged-out token cannot connect again.
- The client cannot choose who receives events; the server decides.
- Events contain no email, phone, documents or internal data. User objects only have `id`, `first_name`, `last_name`, `profile_image_url`.

## Close Codes

When the server closes the connection, the close code says why.

| Code | Meaning | Frontend action |
|---|---|---|
| `4401` | Authentication/token problem: bad, expired or revoked token, no/invalid auth message, no auth message within 10 seconds, token expired while connected, or logged out | Authenticate again (get a new JWT if needed) |
| `4403` | User inactive | Stop connection |
| `4408` | Connection idle: nothing received for about 50 seconds | Reconnect/authenticate; send pings |
| `4429` | Connection limit reached (5 per user) | Close/retry according to app policy |
| `1008` | Policy violation: invalid message after authentication | Fix request/connection behavior |
| `1001` | Server going away: shutting down, or connection dropped after a failed send | Reconnect when appropriate |

Authentication failures arrive as a close code after the connection opens, not as an HTTP error.

## Manual Testing

Use any WebSocket client (browser devtools, Postman, `wscat`) plus a REST client. Paths are under `/api/v1`.

### Test connection

```text
Connect
 ↓
Send auth
 ↓
Receive auth.ok
```

Then send `{"type":"ping"}` and expect `{"type":"pong"}`. A bad token should close with `4401`.

### Test notification

Connect as user A. As user B, like A's post (`PUT /api/v1/posts/{post_id}/reactions`).

Expected on A:

```text
notification.created
```

Then `PATCH /api/v1/me/notifications/{id}/read` as A and expect `notification.read`.

### Test follow request

Make user B private (`PATCH /api/v1/me/settings/privacy` with `{"profile_visibility":"private"}`), connect A and B, then:

```text
A: POST /users/{B}/follow           → B gets follow_request.created
B: POST /users/{A}/follow/accept    → A gets follow_request.accepted, B gets follow_request.removed
```

For `follow_request.removed` alone: request again and decline (`.../follow/decline`) or cancel (`DELETE /users/{B}/follow`). The sender receives nothing on decline.

### Test role upgrade

```text
Select a verifiable role (PUT /users/me/account-role):
notification.created
role_upgrade_request.created        (received by reviewers)

Approve (POST /admin/upgrade-requests/{id}/approve):
notification.created
role_upgrade_request.approved       (received by the requester)

Reject (POST /admin/upgrade-requests/{id}/reject):
notification.created
role_upgrade_request.rejected       (received by the requester)
```

Selecting assigns the role and approving marks it verified for real, so reset the user in a development database afterwards (select Individual User again).

## Limitations

- Delivery is best-effort. There is no event replay, no offline queue and no sequence numbers; resync with REST after reconnecting.
- The connection manager is in memory, so the backend must run as a **single Uvicorn process**. Multiple workers or instances would miss events. There is no Redis.
- No token refresh: after the JWT expires, log in again before reconnecting.
- Role-upgrade approval saves the role assignment and the request status as two separate steps. If the server fails between them the role can be granted while the request still shows `pending`, and no event is sent.

<details>
<summary>Backend implementation notes</summary>

- Events are published by the service layer after the database change has been committed. A WebSocket failure never fails the REST request that caused it.
- `notification.created` is sent from `NotificationService` for every notification type. Follow and role events are separate and come from `UserFollowService` and `RoleUpgradeRequestService`, published after the matching notification.
- `role_upgrade_request.created` uses the same reviewer list the notification service resolves for the `role_upgrade_requested` notification. A reviewer who turned off `system_updates` notifications gets no notification but still gets the event.
- `unread_count` is read from the database when the event is built.
- Settings (environment variables): `WS_AUTH_TIMEOUT_SECONDS` (10), `WS_SEND_TIMEOUT_SECONDS` (5), `WS_PING_INTERVAL_SECONDS` (25, the idle limit is twice this), `WS_MAX_CONNECTIONS_PER_USER` (5).
- Architecture details: see `docs/websocket.md`.

</details>
