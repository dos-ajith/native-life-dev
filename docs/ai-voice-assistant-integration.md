# Native Assistant — Mobile Integration Guide

How to integrate the Native Assistant (text chat, voice mode and talking avatar) into the React Native mobile app. The API is plain HTTPS + JSON plus a streamed audio URL, so it works from any client; the [React Native notes](#react-native-notes) cover the app-side audio parts. This guide is served at `/ai-docs`. REST details are also in Swagger (`/docs`, group **2.6 Backend Tools · AI**) and in the Postman collection (folder **AI**).

## Prompt for your AI coding assistant

Copy everything in the block into your AI coding assistant, and attach this file. Replace the `<…>` placeholders first.

```text
You are implementing the "Native Assistant" screen in our React Native app
(<Expo or bare React Native>, <TypeScript or JavaScript>). The backend API is fully described in the attached file
docs/ai-voice-assistant-integration.md. Treat that file as the source of truth for every
endpoint, field, limit and error. Do not invent fields or endpoints that are not in it.

Context
- Base URL and the access token already exist in the app (<where: e.g. ApiClient /
  AuthRepository>). Reuse them. Never hardcode the base URL, tokens or keys.
- Every JSON response uses {"success", "message", "data"} on success and
  {"success": false, "message", "errors"} on failure. Always show the server's `message`
  to the user on errors.
- The assistant already knows the signed-in user's name on the server. The app never
  sends it.

Build these parts, in this order:

1. Welcome: on open, call GET /ai/welcome. Show greeting, intro and hint, then one chip
   per suggestion (title + subtitle). Tapping a chip sends its `prompt` as a question.

2. Text chat: a message list plus an input with a Send button.
   - POST /ai/ask with {"mode": "chat", "prompt": text}. Add "latitude"/"longitude"
     only when the user enabled "use my location" and permission is granted.
   - Render `answer` as plain text and each item in `posts` as a card (title, summary,
     image, location, distance) that opens the post by `post_id` / `slug`. Any of
     image_url, summary, location_name, distance_km may be null.
   - Show a "Thinking…" bubble and disable Send while a request is running.

3. Deal flow inside chat: when the response has `next_step`, render it under the answer.
   - If `next_step.options` is not empty: one button per option showing `label`; on tap,
     send that option's `prompt` as the next question and remove the buttons.
   - If `next_step.input` is "datetime" and there are no options: show a date-time
     picker; on confirm, send "Starts at YYYY-MM-DD HH:MM" when `field` is "starts_at",
     "Ends at YYYY-MM-DD HH:MM" when it is "valid_until".
   - The user can always type a free answer instead.
   - When `created` is present, show a card "Draft deal created: <title>" with a button
     that opens the user's deals screen.

4. Live (voice) mode, with a "Speak replies" toggle that is on by default:
   - Mic button: tap to start recording (ask for microphone permission first), tap again
     to stop. Auto-stop after 30 seconds. Record AAC/m4a, mono, 16 kHz, about 64 kbps so
     the upload stays small (see "React Native notes" in the file for libraries).
   - Read the recorded file as base64 and POST /ai/ask with {"mode": "live",
     "audio_base64": <base64>, "avatar_id": <selected avatar id>}.
   - Show `transcript` as the user's message, then `answer` and `posts` exactly like chat.
   - Start playback of `audio_url` immediately with a streaming React Native player
     (expo-audio, react-native-track-player or react-native-video). Do not download it
     first and do not add an Authorization header: the signed token in the URL is the
     credential. Do not cache or replay the URL; it expires after about 5 minutes.
   - Do not assume the audio format; it is audio/mpeg (mp3) in production and may be
     audio/wav or audio/mpeg in development. Let the player detect it from the response.
   - Typed questions while "Speak replies" is on also use {"mode": "live", "prompt": ...}.
     When it is off, always use "mode": "chat".
   - If the audio fails to load or play, keep the text answer and continue silently.

5. Avatar:
   - Load GET /ai/avatars, show a picker (name + gender), remember the choice locally,
     default "arjun". Artwork is bundled in the app, keyed by `id`, with a fallback image
     for unknown ids.
   - States: idle (blink every few seconds, slight sway), listening, thinking, speaking.
   - While the reply plays, drive the mouth from the audio level if the chosen player
     exposes it (see "Lip sync in React Native" in the file): sample 30-60 times per
     second, map to mouth openness 0..1, apply a curve (level^0.6), open fast and close
     slower. If it does not, use the looping talk animation fallback described there.
     Use react-native-reanimated for the animation.

6. Concurrency and UX:
   - Only one turn at a time: disable mic and Send while a request runs.
   - The user can stop playback at any time.
   - Never call /ai/ask in a loop, on every keystroke, or auto-replay audio.

7. Errors (see the Errors table in the file):
   - 401 on /ai/ask: refresh the token once and retry, otherwise go to login.
   - 401 on audio_url: skip the audio, keep the text.
   - 404 avatar: reload /ai/avatars and reset the selection.
   - 422: show `message`. For "AI features are disabled in your settings", add a link
     to the AI settings screen. For "No speech was detected in the audio", ask the user
     to try again closer to the microphone.
   - 429 / 502 / 503 / 504: show `message` with a Retry button; in live mode offer to
     switch to typing.

Deliverables
- The screen, its state management, and an API layer with typed models for every
  request and response field in the file.
- Unit tests for the API models and for the turn state machine
  (idle -> listening -> thinking -> speaking -> idle, plus error paths).
- A short note listing anything in the file you could not implement and why.

Before writing code, list the files you will create or change and ask me to confirm.
```

## Overview

```text
 chat:  text ──▶ POST /ai/ask {mode: "chat", prompt} ──▶ answer + posts
 live:  mic ──record──▶ POST /ai/ask {mode: "live", audio_base64} ──▶ transcript + answer + posts + audio_url
                                                                                    │
                                              player ──GET audio_url (streamed)──▶ speaker, avatar mouth follows the level
```

Both modes use the same assistant logic. Live mode adds speech-to-text before it, asks the assistant for a short spoken-style answer, and hands back a link instead of audio. The audio is generated only when the player opens the link, and it starts playing after the first chunk arrives (under a second), not after the whole clip is ready.

## Conventions

| Item | Value |
|------|-------|
| Base URL | `{base_url}/api/v1` (local: `http://127.0.0.1:8000/api/v1`) |
| Auth | `Authorization: Bearer <access_token>` on every call. The token comes from `POST /auth/login`. Refresh it with the existing refresh flow on a 401. |
| Success (JSON endpoints) | `{"success": true, "message": "...", "data": ...}` |
| Error | `{"success": false, "message": "...", "errors": []}` |

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
| `mode` | string | no | `chat` (default) returns text only. `live` returns a short, speakable answer plus an `audio_url`. |
| `prompt` | string | one of | Not blank, at most 2000 characters. Send exactly one of `prompt` or `audio_base64`. |
| `audio_base64` | string | one of | Live mode only. Base64 of the recorded clip (wav, webm, ogg, m4a, mp3 or flac; the format is detected from the audio), at most 5 MB decoded by default (server setting). |
| `language` | string | no | Live mode. Optional ISO code such as `en` for transcription. Omit to auto-detect. |
| `avatar_id` | string | no | Live mode. Voice for the reply, from `/ai/avatars`. Defaults to `arjun`. An unknown id returns 404. |
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
  ],
  "created": null,
  "next_step": null,
  "transcript": null,
  "audio_url": null
}
```

Live mode request and the extra response fields:

```json
{ "mode": "live", "audio_base64": "GkXfo59ChoEBQveBAULygQRC84EIQoKE…", "avatar_id": "anjali" }
```

```json
{
  "answer": "Here are a few businesses near you…",
  "posts": [],
  "transcript": "Which local businesses are there?",
  "audio_url": "https://api.example.com/api/v1/ai/speech?token=eyJhbGciOi…"
}
```

- `answer` is plain text. Show it in the chat bubble.
- `transcript` is set only when live mode received audio. Show it as the user's message.
- `audio_url` is set only in live mode. Give it straight to the platform audio player (ExoPlayer / AVPlayer / `just_audio`); no `Authorization` header is needed because the signed token in the URL is the credential. It streams `audio/mpeg` (mp3) in production; development servers may send `audio/wav` or `audio/mpeg` depending on their configuration, so let the player detect the format and never assume one. The link expires after 5 minutes by default (server setting), so play it right away and do not cache it.
- Speech is limited to 1000 characters by default (server setting). A longer `answer` is spoken up to the last full sentence within the limit; the text `answer` is always complete.
- `posts` may be empty. Render each item as a card that opens the post by `post_id`/`slug`. `image_url`, `summary`, `location_name` and `distance_km` can be `null`.
- Requests can take several seconds. Show a "Thinking…" state and keep the send button disabled until the call finishes.
- The assistant knows the signed-in user's name (it reads it on the server). The app never sends it.

#### Deal creation inside the chat (`created`, `next_step`)

Users allowed to create deals can say things like "I want to sell my bicycle". The assistant then asks for the details one at a time and creates a **draft** deal.

- `next_step` (object or `null`) is present while a deal draft is in progress:

  ```json
  {
    "flow": "deal",
    "field": "starts_at",
    "input": "datetime",
    "options": []
  }
  ```

  - `input` is `text`, `datetime`, `choice` or `confirm`. `field` is the draft field being asked for (`null` on `confirm`).
  - `options` is a list of `{id, label, prompt}`. Render each `label` as a button. On tap, send its `prompt` to `/ai/ask` as the next message and remove the buttons.
  - For `input: "datetime"` with no options, show a date-time picker and send `Starts at YYYY-MM-DD HH:MM` (field `starts_at`) or `Ends at YYYY-MM-DD HH:MM` (field `valid_until`).
  - Typing a free answer always works too.
- `created` (object or `null`) is set once the draft exists: `{kind, id, title, status}`. Show a confirmation card with a button to the user's deals screen. The deal is never published from chat; cover images and submit still happen in the deals screens.

### 3. `GET /ai/speech?token=…`

The `audio_url` from a live-mode answer. Streams the spoken reply (`audio/wav` or `audio/mpeg`, see `Content-Type`) as the speech provider produces it. No bearer header; an invalid or expired token returns 401 `The speech link is invalid or has expired`. You never build this URL yourself.

### 4. `GET /ai/avatars`

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

## Voice turn, step by step

1. User taps the mic. Ask for microphone permission if needed. Show **Listening**.
2. User taps again (or releases). Stop recording. Keep recordings short (one question); stop automatically after about 30 seconds.
3. Base64-encode the clip and `POST /ai/ask` with `mode: "live"`, `audio_base64` and the chosen `avatar_id`. Show **Thinking**.
4. Show `transcript` as the user's message, then the `answer` and `posts`.
5. If "speak replies" is on, start the player on `audio_url` immediately. Show **Speaking** once playback starts.
6. Return to idle.

Typed questions while "speak replies" is on can also use live mode: send `prompt` instead of `audio_base64` and you get an `audio_url` back. With it off, use `mode: "chat"` so no speech is generated.

Disable the mic and send buttons while a request is running, so turns can't overlap. Let the user stop playback at any time.

## Avatar

The avatar is drawn by the app. The server sends no animation data.

- **States:** idle, listening, thinking, speaking.
- **Lip sync:** while the reply audio plays, read the audio output level about 30 to 60 times a second and map it to how open the mouth is (0 = closed, 1 = fully open).
  - Smooth the value: open quickly, close a little slower, so the mouth doesn't flicker.
  - Real speech sits around 0.3 to 0.7 on a typical scale, so apply a curve (for example raise the level to the power 0.6) to make normal speech clearly visible.
- **Idle:** blink every few seconds and add a slight head sway.
- **Characters:** the demo draws two illustrated Indian characters in SVG (Arjun and Anjali, each with their own look and outfit). Any final artwork should provide a mouth that can open and close with a single 0 to 1 value, or mouth states such as closed, half open and open.

A working reference implementation (audio level, smoothing, lip sync, blinking) is in `tools/api-tester/app.html`. See `playWithLipSync` and `buildAvatar`. It runs in the browser, so use it as a guide and not as code to copy.

## React Native notes

The API needs nothing platform-specific. These are the app-side pieces, with libraries that are known to work; equivalents are fine.

| Need | Expo | Bare React Native |
|------|------|-------------------|
| Record m4a | `expo-audio` (`useAudioRecorder` with an AAC/m4a preset) | a recorder that outputs AAC/m4a, e.g. `react-native-nitro-sound` |
| File → base64 | `expo-file-system` | `react-native-fs` (`readFile(path, 'base64')`) |
| Stream `audio_url` | `expo-audio` player | `react-native-track-player` or `react-native-video` (audio only) |
| Mic permission | `expo-audio` permission request | `react-native-permissions` |
| Avatar animation | `react-native-reanimated` (+ `react-native-svg` for SVG artwork) | same |

Recording settings: mono, 16 kHz sample rate, about 64 kbps AAC. Speech recognition does not need more, and a 30-second clip stays around 250 KB, which keeps the upload fast on mobile data.

Base64 without an extra library also works: `fetch(fileUri)` → `blob()` → `FileReader.readAsDataURL`, then take the part after the comma.

```ts
const response = await api.post('/ai/ask', {
  mode: 'live',
  audio_base64: base64Clip,
  avatar_id: selectedAvatarId,
});
const { answer, transcript, posts, audio_url } = response.data.data;
showTurn({ transcript, answer, posts });
if (speakReplies && audio_url) {
  await player.replace({ uri: audio_url });
  player.play();
}
```

Pass `audio_url` to the player exactly as returned. Do not add headers and do not save it.

### Lip sync in React Native

Most React Native players do not expose the live output level, which the browser reference (`playWithLipSync`) reads from the Web Audio API. Options, best first:

1. **Player with sample access.** If your `expo-audio` version offers an audio sample listener for the player, compute the peak of each sample buffer and feed it into the same smoothing as the reference. Playback stays streamed.
2. **`react-native-audio-api`** (a Web Audio API implementation for React Native with `AnalyserNode`). It mirrors `playWithLipSync` almost line for line, but it decodes the whole clip before playing, so speech starts after the full download (about 1 to 2 seconds later) instead of streaming.
3. **Fallback.** While the player reports playing, loop a simple talk animation (mouth open/close at a natural, slightly random pace) and close the mouth when playback ends. Less accurate, no audio processing, always works.

Start with option 3 to ship, then upgrade to 1 or 2.

## Errors

| HTTP | When | What to do |
|------|------|------------|
| 401 | Missing, invalid or expired token | Refresh the token, retry once, otherwise send the user to login. For `audio_url` (`The speech link is invalid or has expired`), just skip the audio; the text is already shown. |
| 404 | `avatar_id` unknown (`Assistant avatar not found`) | Reload `/ai/avatars` and reset the selection. |
| 422 | Validation failed: missing or both `prompt` and `audio_base64`, `audio_base64` in chat mode, invalid base64, empty, oversized or unsupported audio, no speech in the clip, or AI turned off in settings | Show the `message` from the response. For "AI features are disabled in your settings", offer a link to the AI settings. |
| 429 | Provider is busy (`AI is busy right now, please try again in a moment`) | Show the message and let the user retry. |
| 502 | Provider returned something unusable | Show a generic error and offer retry. |
| 503 | AI provider unavailable or not configured (`AI provider is currently unavailable`) | Show a generic error, and fall back to text-only if speech failed. |
| 504 | Provider timed out | Offer retry. |

Rules:

- If a live-mode call fails with a provider error (502/503/504), retry once, or fall back to typing with `mode: "chat"`.
- If `audio_url` fails to play, keep the text answer. Voice is an extra, not a requirement.
- If `/ai/ask` returns "No speech was detected in the audio", tell the user to try again, closer to the microphone.
- Always show the server's `message`. Do not rely on the status code alone.

## Limits and cost

- Request limits: 5 MB audio and 1000 characters of speech by default. These are server settings and can change.
- Speech is billed per use by the provider, and only when `audio_url` is opened. Use `mode: "live"` only when the user wants to hear the reply, and do not auto-replay.
- Do not call `/ai/ask` in a loop or on every keystroke.

## Testing checklist

- [ ] Welcome screen renders greeting, hint and suggestion chips.
- [ ] A suggestion chip sends its prompt and shows the answer and post cards.
- [ ] Text question with and without location.
- [ ] Voice question: record → live `/ai/ask` → text shown at once → `audio_url` streams → avatar lip sync.
- [ ] Each of the 2 avatars plays its own voice.
- [ ] Live mode on a real iOS device and a real Android device (simulators often lack a working microphone).
- [ ] Microphone permission denied.
- [ ] Empty recording, very long recording and background noise only.
- [ ] Network drop during a live-mode call.
- [ ] Expired token refreshes without losing the user's turn.
- [ ] User with AI disabled in settings sees the message and no crash.
- [ ] Playing an `audio_url` after 5 minutes fails cleanly and leaves the text.
- [ ] Turning "speak replies" off leaves text chat working.
- [ ] "What is my name?" answers with the signed-in user's name.
- [ ] Deal flow: "I want to sell my bicycle" shows option buttons and a date picker, and ends with the created card.

## Open items

- The 3D/2D artwork for the final avatars is not delivered yet. The app should load avatars by `id` so it can be swapped without an app change.
- The text answer is returned in one piece; only the audio is streamed.
