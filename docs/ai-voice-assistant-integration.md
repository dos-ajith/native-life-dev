# Native Assistant — Mobile Integration Guide

How to integrate the Native Assistant (text chat, voice mode and talking avatar) into the mobile app. REST details are also in Swagger (`/docs`, group **2.6 Backend Tools · AI**) and in the Postman collection (folder **AI**).

## Prompt for your AI coding assistant

Copy this into your assistant together with this file:

```text
Implement the Native Assistant screen in the mobile app using the API described in
docs/ai-voice-assistant-integration.md.

Requirements:
1. Opening screen: call GET /ai/welcome and show the greeting, intro, hint and the
   suggestion chips. Tapping a chip sends its `prompt` to POST /ai/ask.
2. Text chat: send the user's text to POST /ai/ask and render `answer` plus the
   `posts` cards.
3. Voice mode: record audio, send it to POST /ai/voice/transcribe, send the returned
   text to POST /ai/ask, then send the `answer` to POST /ai/voice/speak and play the
   returned audio.
4. Avatar: load GET /ai/avatars, let the user pick one, send its id as `avatar_id` to
   /ai/voice/speak, and animate the avatar's mouth from the audio level while the
   reply plays.
5. Use the standard response envelope and handle every error in the error table.
6. Never hardcode the base URL or tokens. The access token comes from the existing
   login flow.
```

## Overview

```text
 mic ──record──▶ POST /ai/voice/transcribe ──text──▶ POST /ai/ask ──answer──▶ POST /ai/voice/speak ──audio──▶ speaker
                                                                                                          │
                                                                              avatar mouth follows the audio level
```

The voice endpoints only convert between speech and text. All assistant logic stays in `POST /ai/ask`, so text and voice answers are identical.

## Conventions

| Item | Value |
|------|-------|
| Base URL | `{base_url}/api/v1` (local: `http://127.0.0.1:8000/api/v1`) |
| Auth | `Authorization: Bearer <access_token>` on every call. The token comes from `POST /auth/login`. Refresh it with the existing refresh flow on a 401. |
| Success (JSON endpoints) | `{"success": true, "message": "...", "data": ...}` |
| Error | `{"success": false, "message": "...", "errors": []}` |

`POST /ai/voice/speak` is the exception: on success it returns raw audio bytes, not JSON. Errors from it still use the JSON error format.

## Endpoints

### 1. `GET /ai/welcome`

Opening content for the assistant screen.

```json
{
  "success": true,
  "message": "Assistant welcome retrieved",
  "data": {
    "greeting": "Hi Arjun! 👋",
    "intro": "I'm your Native Assistant.",
    "hint": "Ask me anything about Kadakampalli — from local businesses and events to places, notices, daily services and more.",
    "place_name": "Kadakampalli",
    "suggestions_title": "Here are some things you can ask",
    "suggestions": [
      {
        "id": "updates",
        "title": "New Updates",
        "subtitle": "Get information",
        "prompt": "What's new in Kadakampalli?"
      }
    ]
  }
}
```

Render each suggestion as a chip. On tap, send its `prompt` to `/ai/ask`.

### 2. `POST /ai/ask`

Ask the assistant a question.

Request (JSON):

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `prompt` | string | yes | Not blank, at most 2000 characters. |
| `latitude` | number | no | -90 to 90. Send together with `longitude`, or neither. |
| `longitude` | number | no | -180 to 180. |
| `radius_km` | number | no | Greater than 0, at most 50. Needs `latitude` and `longitude`. |

```json
{ "prompt": "Which local businesses are there in Kadakampalli?", "latitude": 12.97, "longitude": 77.59, "radius_km": 10 }
```

Response `data`:

```json
{
  "answer": "Here are a few businesses near you…",
  "posts": [
    {
      "post_id": "6f1c…",
      "slug": "fresh-bakery-opening",
      "title": "Fresh Bakery opens this Friday",
      "summary": "First 50 customers get…",
      "author_name": "Fresh Bakery",
      "image_url": "https://…",
      "tags": ["food", "business"],
      "location_name": "Kadakampalli",
      "distance_km": 1.2,
      "source": "Native Life"
    }
  ]
}
```

- `answer` is plain text. Show it in the chat bubble, and send exactly this text to `/ai/voice/speak` in voice mode.
- `posts` may be empty. Render each item as a card that opens the post by `post_id`/`slug`. `image_url`, `summary`, `location_name` and `distance_km` can be `null`.
- Requests can take several seconds. Show a "Thinking…" state and keep the send button disabled until the call finishes.

### 3. `GET /ai/avatars`

The assistant characters the user can choose from.

```json
{
  "success": true,
  "message": "Assistant avatars retrieved",
  "data": [
    { "id": "arjun", "name": "Arjun", "gender": "male" },
    { "id": "anjali", "name": "Anjali", "gender": "female" }
  ]
}
```

- Each avatar has its own voice on the server. The app only sends the `id`.
- The artwork lives in the app, keyed by `id`. The list may change, so always load it from the API and fall back to a default picture for an unknown `id`.
- Remember the user's choice locally. The default is `arjun`.

### 4. `POST /ai/voice/transcribe`

Turns a recorded clip into text. Request is `multipart/form-data`:

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `audio` | file | yes | Not empty, at most 5 MB by default (server setting). |
| `language` | string | no | Optional ISO code such as `en`. Omit to auto-detect. |

- Give the file a correct extension in its filename (`clip.m4a`, `clip.webm`, `clip.wav`, `clip.mp3`, `clip.ogg`). The server detects the format from it.
- Keep recordings short (one question). Stop automatically after about 30 seconds or when the user releases the button.

Response `data`:

```json
{ "text": "What's new in Kadakampalli?" }
```

### 5. `POST /ai/voice/speak`

Speaks text in the chosen avatar's voice. Request (JSON):

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `text` | string | yes | Not blank, at most 1000 characters by default (server setting). |
| `avatar_id` | string | no | Defaults to `arjun`. An unknown id returns 404. |

```json
{ "text": "Here are a few businesses near you.", "avatar_id": "anjali" }
```

Response: raw audio bytes. Read the `Content-Type` header to decide how to play it (`audio/wav` or `audio/mpeg`). Do not assume one format.

- If the `answer` from `/ai/ask` is longer than the limit, split it by sentence and speak the first part, or skip speech and show only the text.
- Play from memory or a temporary file. Do not store the audio.

## Voice turn, step by step

1. User taps the mic. Ask for microphone permission if needed. Show **Listening**.
2. User taps again (or releases). Stop recording. Show **Transcribing**.
3. `POST /ai/voice/transcribe` with the clip. Show the returned text as the user's message.
4. `POST /ai/ask` with that text. Show **Thinking**.
5. Show the `answer` and `posts` in the chat.
6. If "speak replies" is on, `POST /ai/voice/speak` with the `answer` and the chosen `avatar_id`. Show **Speaking** and play the audio.
7. Return to idle.

Disable the mic and send buttons while any step is running, so turns can't overlap. Let the user stop playback at any time.

## Avatar

The avatar is drawn by the app. The server sends no animation data.

- **States:** idle, listening, thinking, speaking.
- **Lip sync:** while the reply audio plays, read the audio output level about 30 to 60 times a second and map it to how open the mouth is (0 = closed, 1 = fully open).
  - Smooth the value: open quickly, close a little slower, so the mouth doesn't flicker.
  - Real speech sits around 0.3 to 0.7 on a typical scale, so apply a curve (for example raise the level to the power 0.6) to make normal speech clearly visible.
- **Idle:** blink every few seconds and add a slight head sway.
- **Characters:** the demo draws two illustrated Indian characters in SVG (Arjun and Anjali, each with their own look and outfit). Any final artwork should provide a mouth that can open and close with a single 0 to 1 value, or mouth states such as closed, half open and open.

A working reference implementation (audio level, smoothing, lip sync, blinking) is in `tools/api-tester/app.html`. See `playWithLipSync` and `buildAvatar`. It runs in the browser, so use it as a guide and not as code to copy.

## Errors

| HTTP | When | What to do |
|------|------|------------|
| 401 | Missing, invalid or expired token | Refresh the token, retry once, otherwise send the user to login. |
| 404 | `avatar_id` unknown (`Assistant avatar not found`) | Reload `/ai/avatars` and reset the selection. |
| 422 | Validation failed: blank `prompt`, empty or oversized audio, text too long to speak, no speech in the clip, or AI turned off in settings | Show the `message` from the response. For "AI features are disabled in your settings", offer a link to the AI settings. |
| 429 | Provider is busy (`AI is busy right now, please try again in a moment`) | Show the message and let the user retry. |
| 502 | Provider returned something unusable | Show a generic error and offer retry. |
| 503 | AI provider unavailable or not configured (`AI provider is currently unavailable`) | Show a generic error, and fall back to text-only if speech failed. |
| 504 | Provider timed out | Offer retry. |

Rules:

- If `/ai/voice/speak` fails, still show the text answer. Voice is an extra, not a requirement.
- If `/ai/voice/transcribe` returns "No speech was detected in the audio", tell the user to try again, closer to the microphone.
- Always show the server's `message`. Do not rely on the status code alone.

## Limits and cost

- Request limits: 5 MB audio and 1000 characters of speech by default. These are server settings and can change.
- Voice calls are billed per use by the speech provider. Do not call `/ai/voice/speak` for text the user has not asked to hear, and do not auto-replay.
- Do not call the voice endpoints in a loop or on every keystroke.

## Testing checklist

- [ ] Welcome screen renders greeting, hint and suggestion chips.
- [ ] A suggestion chip sends its prompt and shows the answer and post cards.
- [ ] Text question with and without location.
- [ ] Voice question: record → transcribe → ask → speak → avatar lip sync.
- [ ] Each of the 2 avatars plays its own voice.
- [ ] Microphone permission denied.
- [ ] Empty recording, very long recording and background noise only.
- [ ] Network drop during each of the three voice calls.
- [ ] Expired token refreshes without losing the user's turn.
- [ ] User with AI disabled in settings sees the message and no crash.
- [ ] Both `audio/wav` and `audio/mpeg` replies play.
- [ ] Turning "speak replies" off leaves text chat working.

## Open items

- The 3D/2D artwork for the final avatars is not delivered yet. The app should load avatars by `id` so it can be swapped without an app change.
- Replies are returned in one piece, not streamed. Streaming is planned to reduce waiting time.
