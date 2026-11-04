# SSO and Sign-In Setup Guide

How to set up and manually test Google Sign-In, phone OTP and email
verification for local development. The rules for each method (session model,
`registration_required`, account linking) are in the **Authentication** section
of the [README](../README.md#authentication). This guide does not repeat them.

## Developer consoles

| Console | URL | Why Native Life uses it |
|---|---|---|
| Google OAuth Playground | https://developers.google.com/oauthplayground | Get a real Google ID token to paste into Postman when testing `/auth/google/*` |
| Google Cloud Console | https://console.cloud.google.com/ | Create and manage the OAuth client IDs (Android, iOS, web), set authorized redirect URIs, configure the consent screen and its test users |
| Google Cloud Platform | https://cloud.google.com/ | Reference for Google Cloud services and documentation |
| Twilio Console | https://console.twilio.com/ | Account SID, API keys, sender number and verified caller IDs for phone OTP when `SMS_PROVIDER=twilio` |

## Environment variables

These names come from `app/core/config.py` and `.env.example`. Put real values
in `.env` only. Never put them in `.env.example`, Postman or this file.

**Google**

| Variable | Notes |
|---|---|
| `GOOGLE_CLIENT_IDS` | JSON array of every OAuth client ID that issues ID tokens the API should accept, e.g. `["<web-client-id>.apps.googleusercontent.com"]`. `[]` disables Google sign-in (endpoints return 503). |

The backend only verifies ID tokens, so it needs no Google client secret and
has no redirect URI of its own. A client secret is needed only in the OAuth
Playground (see below), and it stays there.

**Twilio / phone OTP**

| Variable | Notes |
|---|---|
| `SMS_PROVIDER` | `disabled` (default, phone endpoints return 503), `console` (code is written to the server log; refused when `APP_ENV=production`), or `twilio` |
| `TWILIO_ACCOUNT_SID` | Twilio Console > Account info |
| `TWILIO_API_KEY_SID` | Twilio Console > Account > API keys & tokens |
| `TWILIO_API_KEY_SECRET` | Shown once, when the API key is created |
| `TWILIO_FROM_NUMBER` | Twilio sender number or sender ID |
| `TWILIO_REQUEST_TIMEOUT_SECONDS` | Defaults to `10` |
| `PHONE_OTP_MAX_SENDS_PER_PHONE_PER_HOUR`, `PHONE_OTP_MAX_SENDS_PER_IP_PER_HOUR` | Rate limits |

With `SMS_PROVIDER=twilio`, the app refuses to start unless all four
`TWILIO_*` credential variables are set.

**Shared by all methods**

| Variable | Notes |
|---|---|
| `OTP_LENGTH`, `OTP_EXPIRE_MINUTES`, `OTP_MAX_ATTEMPTS`, `OTP_RESEND_COOLDOWN_SECONDS` | Used by both email and phone OTP |
| `REGISTRATION_TOKEN_EXPIRE_MINUTES` | Lifetime of the `registration_token` returned to new Google/phone users |
| `REFRESH_TOKEN_EXPIRE_DAYS`, `ACCESS_TOKEN_EXPIRE_MINUTES` | Session lifetimes |
| `MANDRILL_ENABLED`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_USE_TLS`, `MAIL_FROM_EMAIL` | Delivery of the email verification code. `SMTP_USE_TLS=true` means STARTTLS. |

For local email testing, any SMTP sandbox inbox (e.g. Mailtrap) works. Some
networks block the usual SMTP ports. If a connection is refused or times out,
try port `2525`.

## Google Sign-In flow

```
App (Google SDK) --ID token--> POST /auth/google/sign-in
    API verifies the token's signature, expiry and audience against GOOGLE_CLIENT_IDS
    and requires email_verified = true
    |
    |-- Google `sub` already linked  --> status: authenticated (tokens + user)
    |-- email already used by an account --> 409 account_exists_sign_in_to_link
    |       user signs in with their existing method, then POST /auth/google/link
    '-- new user --> status: registration_required (registration_token, email, names)
            POST /auth/google/register {registration_token, first_name, last_name, accept_terms: true}
            --> 201, status: authenticated
```

Error codes in `errors[0].code`: `google_token_invalid`, `google_unavailable`,
`google_email_not_verified`, `account_exists_sign_in_to_link`,
`google_identity_in_use`, `google_already_linked`.

### Getting a test ID token from the OAuth Playground

The Playground's default credentials issue tokens for Google's own client, and
the API rejects those because the audience doesn't match. Use your own web
client instead:

1. In Google Cloud Console > APIs & Services > Credentials, open (or create) a
   **Web application** OAuth client. Add
   `https://developers.google.com/oauthplayground` as an authorized redirect URI.
2. Add that client ID to `GOOGLE_CLIENT_IDS` in `.env` and restart the API.
3. If the consent screen is in Testing mode, add your Google account as a test
   user.
4. In the Playground, open the settings (gear icon), tick **Use your own OAuth
   credentials** and enter the web client ID and secret.
5. Authorize the scopes `openid email profile`, then **Exchange authorization
   code for tokens**.
6. Copy `id_token` (not `access_token`) into the Postman collection variable
   `google_id_token`. It expires after about 1 hour.

*Requires verification:* the steps above are the standard Playground setup and
are not recorded anywhere in this repository. Check that they match how the
Native Life Google Cloud project is configured.

## Email verification vs phone OTP

| | Email verification | Phone OTP | Google email |
|---|---|---|---|
| Proves | User owns the email given at `POST /users/register` | User owns the phone number | Google has verified the email |
| Code sent by | SMTP (or Mandrill) | `SMS_PROVIDER` (Twilio or console) | Nobody; there is no code |
| Endpoints | `/auth/verify-email`, `/auth/resend-email-verification` | `/auth/phone/request-otp`, `/auth/phone/verify-otp` | `/auth/google/sign-in` |
| Result | Marks the email verified; the user then signs in with `/auth/login` | Signs in, or returns `registration_required` | Signs in, or returns `registration_required` |

- Email + password users can't log in until their email is verified (`/auth/login`
  returns "Please verify your email before logging in").
- Accounts created through `/auth/google/register` get `email_verified_at` set
  straight away, because Google already verified the address.
- A phone number typed during email registration stays unverified and never
  grants sign-in. Only numbers verified through phone OTP do.

## Postman

Collection: `postman/native-life-api.postman_collection.json`. `base_url`
defaults to `http://127.0.0.1:8000/api/v1`.

| Folder / request | Method and path | Uses | Saves automatically |
|---|---|---|---|
| Mobile / Register / Register | `POST /users/register` (form-data) | | |
| Auth / Verify Email | `POST /auth/verify-email` | | |
| Auth / Resend Email Verification | `POST /auth/resend-email-verification` | | |
| Auth / Login | `POST /auth/login` | | `access_token`, `refresh_token` |
| Auth / Refresh Token | `POST /auth/refresh` | `refresh_token` | `access_token`, `refresh_token` |
| Auth / Me | `GET /auth/me` | `access_token` | |
| Auth / Logout | `POST /auth/logout` | `access_token` | clears `access_token` |
| Auth / Phone / Request Phone OTP | `POST /auth/phone/request-otp` | `phone` | |
| Auth / Phone / Verify Phone OTP | `POST /auth/phone/verify-otp` | `phone` | tokens, or `registration_token` |
| Auth / Phone / Register With Phone | `POST /auth/phone/register` | `registration_token` | `access_token`, `refresh_token` |
| Auth / Google / Google Sign-In | `POST /auth/google/sign-in` | `google_id_token` | tokens, or `registration_token` |
| Auth / Google / Register With Google | `POST /auth/google/register` | `registration_token` | `access_token`, `refresh_token` |
| Auth / Google / Link Google | `POST /auth/google/link` | `access_token`, `google_id_token` | |

To test phone OTP without Twilio, set `SMS_PROVIDER=console` and read the code
from the server log. Twilio trial accounts can only text numbers verified in
the Twilio Console.
