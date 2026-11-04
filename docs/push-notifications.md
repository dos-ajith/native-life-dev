# Push notifications — setup

The API sends a push (Firebase Cloud Messaging) every time it creates an in-app notification for a user who has `push_enabled` on. Push is **off until you finish steps 1–4**; everything else keeps working without it.

## What you do (once, ~15 min)

1. **Firebase project** — open https://console.firebase.google.com, create a project (or reuse one). Copy the **Project ID** (Project settings → General).
2. **Service account key** — Project settings → *Service accounts* → *Generate new private key*. Save the file as `secrets/firebase-service-account.json` inside this repo folder. The `secrets/` folder is gitignored; never commit or share this file.
3. **`.env`** — add:
   ```
   PUSH_PROVIDER=fcm
   FCM_PROJECT_ID=<your project id>
   FCM_SERVICE_ACCOUNT_FILE=secrets/firebase-service-account.json
   ```
4. **Database + restart** — run `alembic upgrade head`, then restart the API. If a value is missing the API refuses to start and names it.
5. **Apps (give these to the mobile developer)**
   - Android: Firebase → *Add app* → Android (use the real package name) → download `google-services.json`.
   - iOS: *Add app* → iOS → download `GoogleService-Info.plist`. Then Apple Developer → Keys → create an **APNs Auth Key (.p8)** and upload it in Firebase → Project settings → *Cloud Messaging* → Apple app configuration. Without this, iPhones get nothing.

## What the mobile developer does

- Ask the user for notification permission and get the FCM token.
- After login and whenever the token changes: `POST /api/v1/me/devices` with `{"token": "...", "platform": "android" | "ios" | "web"}`. Safe to call on every app start.
- On logout: `DELETE /api/v1/me/devices` with `{"token": "..."}` so the phone stops receiving that user's pushes.
- Each push carries a title and body, plus `data`: `notification_id`, `type`, `entity_type`, `entity_id`. Use them to open the right screen on tap.
- Web clients: call `GET /api/v1/me/devices/web-config` to get the Firebase web config and VAPID key instead of hardcoding them. Set the `FCM_WEB_*` values in `.env` (placeholders are in `.env.example`) from Firebase > Project settings > General > Web app, and Cloud Messaging > Web Push certificates. These are public values, not secrets.
- All requests are in Postman under **0.3 Notifications**.

## Check it works

1. Log in on a phone with a registered token.
2. From another account do something that notifies that user (for example follow them).
3. The phone should get a push. If not, check the API log for lines from `app.push`.

## Good to know

- Users switch push on or off with the existing `push_enabled` notification setting (default on).
- Invalid or expired tokens are deleted automatically when Firebase reports them.
- Sending happens in the background after the notification is saved, so a slow Firebase never slows a request, and a push failure never breaks the action.
- Web push also needs a Firebase web app, a VAPID key and a `firebase-messaging-sw.js` served by the **web client**, not this API. The 404 for that file in the API log is normal.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| API won't start: `PUSH_PROVIDER=fcm requires ...` | `FCM_PROJECT_ID` or `FCM_SERVICE_ACCOUNT_FILE` missing in `.env` |
| Log: `FCM rejected ... HTTP 403` | Service account is from a different Firebase project, or the Firebase Cloud Messaging API is disabled for it |
| Android works, iPhone doesn't | APNs key not uploaded in Firebase (step 5) |
| Nothing logged, no push | User has `push_enabled` off, or no token registered (`device_tokens` table is empty) |
