# AGENTS.md — Grot Walkie-Talkie Development Guide

## Project Overview

Tauri 2 desktop app that provides a walkie-talkie UI for the Grot iDotMatrix
voice-chat system. The user presses and holds the big button to speak; an LED
display shows status, transcriptions, and Grot's responses.

Architecture: Tauri window (React webview) ↔ WebSocket ↔ Python sidecar
(BLE + OpenAI voice pipeline).

---

## Architecture

```
Tauri App (walkie-talkie/)
  React Webview (src/)
    App.tsx               — top-level state, wires hooks to components
    components/
      WalkieTalkie.tsx    — device shell/frame
      LEDDisplay.tsx      — scrolling status/chat display
      PushToTalkButton.tsx— press-and-hold PTT button
    hooks/
      useWebSocket.ts     — WebSocket connection with auto-reconnect
      useAudioRecorder.ts — Web Audio API recording + WAV encoding
    utils/
      audio.ts            — playAudioFromBase64() for TTS playback
    types/
      protocol.ts         — ClientMessage / ServerMessage TypeScript types
    styles/
      walkie-talkie.css   — retro device styling

  Rust shell (src-tauri/)
    src/lib.rs            — Tauri setup, sidecar spawn, log forwarding
    src/main.rs           — entry point
    tauri.conf.json       — window config, sidecar config
    capabilities/
      default.json        — shell spawn permissions
    binaries/
      grot-server         — dev shell script (wraps Python server)
      grot-server-*       — prod PyInstaller binary (created by build-sidecar.sh)

  build-sidecar.sh        — PyInstaller build script

Python backend (../src/idotmatrix_upload/)
  ws_server.py            — GrotWebSocketServer, WebSocket API
  cli.py                  — `idotmatrix-upload serve` command
```

---

## WebSocket Protocol

All messages are JSON with a `type` discriminant field. The TypeScript types
live in `src/types/protocol.ts`; the Python implementation is in
`../src/idotmatrix_upload/ws_server.py`.

### Client → Server

| Message | Fields | Description |
|---|---|---|
| `voice_audio` | `data: string` | Base64-encoded 16kHz mono WAV from the microphone |
| `command` | `text: string` | Slash command, e.g. `"/animation dancing"`, `"/help"`, `"/exit"` |
| `connect_device` | `address?: string` | Request (re)connection to BLE device. Optional address skips scan |
| `disconnect` | — | Graceful session end |

### Server → Client

| Message | Fields | Description |
|---|---|---|
| `ready` | — | Server is connected to the BLE device and ready for input |
| `status` | `text: string` | Informational line for the LED display (green) |
| `transcription` | `text: string` | User's transcribed speech (cyan) |
| `chat_token` | `text: string` | Streaming LLM token from Grot |
| `chat_done` | `text: string` | Grot's full response (amber), mood tag stripped |
| `voice_audio` | `data: string` | Base64-encoded WAV — Grot's TTS audio |
| `animation` | `state: string` | iDotMatrix animation state, e.g. `"talking"`, `"idle"` |
| `error` | `text: string` | Error message for the LED display (red) |

### Example session flow

```
Client connects
  S→C: {"type":"status","text":"Loading animations..."}
  S→C: {"type":"status","text":"Connecting to iDotMatrix device..."}
  S→C: {"type":"status","text":"Connected to IDM-1234."}
  S→C: {"type":"ready"}
  S→C: {"type":"chat_token","text":"Hey! "}
  S→C: {"type":"chat_token","text":"What's up?"}
  S→C: {"type":"chat_done","text":"Hey! What's up?"}
  S→C: {"type":"voice_audio","data":"<base64 WAV>"}

User holds button, speaks, releases:
  C→S: {"type":"voice_audio","data":"<base64 WAV>"}
  S→C: {"type":"animation","state":"thinking"}
  S→C: {"type":"status","text":"Transcribing..."}
  S→C: {"type":"transcription","text":"Tell me a joke!"}
  S→C: {"type":"status","text":"Grot is thinking..."}
  S→C: {"type":"chat_token","text":"Why do "}
  S→C: {"type":"chat_token","text":"LED matrices never get lonely?"}
  S→C: {"type":"chat_done","text":"Why do LED matrices never get lonely? ..."}
  S→C: {"type":"animation","state":"talking"}
  S→C: {"type":"voice_audio","data":"<base64 WAV>"}
  S→C: {"type":"animation","state":"idle"}

User sends command:
  C→S: {"type":"command","text":"/animation dancing"}
  S→C: {"type":"status","text":"Playing animation: dancing"}
  S→C: {"type":"animation","state":"dancing"}
  S→C: {"type":"animation","state":"idle"}

User disconnects:
  C→S: {"type":"disconnect"}
  S→C: {"type":"status","text":"Goodbye!"}
```

---

## File Layout

```
walkie-talkie/
  src/
    App.tsx                   — Root component, all state, hook wiring
    main.tsx                  — React entry point
    vite-env.d.ts             — Vite type reference
    components/
      WalkieTalkie.tsx        — Outer device frame
      LEDDisplay.tsx          — Scrolling text display
      PushToTalkButton.tsx    — Press-and-hold button with state variants
    hooks/
      useWebSocket.ts         — WS connection + reconnect + message parsing
      useAudioRecorder.ts     — getUserMedia + MediaRecorder + WAV encoding
    utils/
      audio.ts                — playAudioFromBase64()
    types/
      protocol.ts             — ClientMessage, ServerMessage, type guards
    styles/
      walkie-talkie.css       — All styling (CSS variables + component classes)
    __tests__/
      setup.ts                — jest-dom + jsdom API stubs
      LEDDisplay.test.tsx     — Component tests
      PushToTalkButton.test.tsx
      useWebSocket.test.ts    — Hook tests with mock WebSocket class
      useAudioRecorder.test.ts— Hook tests with mock MediaRecorder class
      protocol.test.ts        — Type guard and serialisation tests
  src-tauri/
    src/
      main.rs                 — Tauri entry point
      lib.rs                  — Sidecar spawn + log forwarding
    tauri.conf.json           — App config (window size, sidecar, CSP)
    Cargo.toml                — Rust dependencies
    build.rs                  — tauri-build
    capabilities/
      default.json            — Permission grants (shell spawn/kill)
    binaries/
      grot-server             — Dev wrapper script (activates venv, runs Python)
  build-sidecar.sh            — PyInstaller build + copy to binaries/
  package.json                — Node deps (react, tauri, vitest, etc.)
  vite.config.ts              — Vite (port 1420 for Tauri)
  vitest.config.ts            — Vitest (jsdom environment)
  tsconfig.json / tsconfig.app.json / tsconfig.node.json
  index.html
  INSTALL.md
  AGENTS.md (this file)
```

---

## Development Workflow

### Running locally

```bash
# Terminal 1: Python server
cd /path/to/repo
source .venv/bin/activate
export OPENAI_API_KEY="sk-..."
idotmatrix-upload serve --port 8765

# Terminal 2: Tauri app
cd walkie-talkie
cargo tauri dev
```

### Testing

```bash
# Frontend unit tests
npm test            # run once
npm run test:watch  # watch mode

# Python backend tests
cd ..
pytest tests/test_ws_server.py -v

# All Python tests
pytest -v
```

### Building the sidecar

```bash
cd walkie-talkie
./build-sidecar.sh
```

### Packaging

```bash
cd walkie-talkie
./build-sidecar.sh   # must run first
cargo tauri build
```

---

## Conventions

### React / TypeScript

- One component per file; file name matches the exported default.
- Use `data-testid` attributes on interactive elements for tests.
- Prefer `useCallback` for event handlers passed to child components.
- No `any` types; use the `protocol.ts` discriminated unions.
- CSS classes defined in `walkie-talkie.css` — no inline styles.

### CSS

- CSS custom properties (variables) defined on `:root` for all colours.
- Component class names follow the `device-*` / `led-*` / `ptt-*` prefixes.
- No CSS-in-JS, no CSS modules — a single flat stylesheet.

### Testing

- Mock browser APIs (`WebSocket`, `MediaRecorder`, `AudioContext`) with
  `class` syntax (not arrow functions) so `new MockX()` works.
- Add jsdom stubs for missing APIs to `src/__tests__/setup.ts`.
- Test behaviour (what the user sees/hears), not implementation details.

### Python (inherited from parent project)

- `ws_server.py` must remain pure-async; no blocking I/O on the event loop.
- All `_send*` helpers must silently swallow exceptions from broken connections.
- The `_processing` flag serialises voice pipeline runs — never clear it early.

---

## Common Tasks

### Add a new LED display line variant

1. Add the new variant to `DisplayVariant` in `LEDDisplay.tsx`.
2. Add a CSS class (e.g. `.led-warning`) in `walkie-talkie.css`.
3. Map the variant to the class in `VARIANT_CLASS` in `LEDDisplay.tsx`.
4. Add a test case in `LEDDisplay.test.tsx`.

### Add a new WebSocket message type

1. Add the TypeScript type to `src/types/protocol.ts` (client or server union).
2. Handle the new type in `App.tsx`'s `useEffect` switch statement.
3. Add a handler in `GrotWebSocketServer._handler()` in `ws_server.py`.
4. Add test cases to both `protocol.test.ts` and `test_ws_server.py`.

### Change the PTT button behaviour

Edit `PushToTalkButton.tsx` (visual) and `App.tsx` (logic). The `ButtonState`
type in `PushToTalkButton.tsx` drives both the label and CSS class — extend
it if you need a new visual state.

### Update the sidecar binary

After changing the Python server:

```bash
cd walkie-talkie
./build-sidecar.sh
cargo tauri build
```

### Adjust the window size

Edit `walkie-talkie/src-tauri/tauri.conf.json`:

```json
"windows": [{ "width": 400, "height": 700, "resizable": false }]
```

Then update `walkie-talkie.css` to match (`.device-body` width etc.).
