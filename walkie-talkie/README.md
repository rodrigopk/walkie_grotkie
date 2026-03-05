# Grot Walkie-Talkie

A desktop voice-chat interface for the iDotMatrix LED matrix chatbot. Press and hold the big button to talk to Grot; the LED display shows transcriptions, responses, and status messages in real time.

Built with **Tauri 2** (native window shell) + **React + Vite + TypeScript** (UI) + the **Python voice-chat backend** from the parent project (WebSocket sidecar).

```
┌───────────────────────────────────────┐
│  Tauri 2 Desktop App                  │
│  ┌───────────────────────────────┐    │
│  │  React Webview                │    │
│  │  LED Display  │  PTT Button   │    │
│  │  WebSocket Client             │    │
│  │  Web Audio Recorder           │    │
│  └───────────────────────────────┘    │
│  Sidecar: grot-server (Python)        │
└───────────────────────────────────────┘
         │ WebSocket ws://localhost:8765
┌────────▼──────────────────────────────┐
│  Python Backend                       │
│  OpenAI Whisper + GPT-4o + TTS        │
│  BLE / iDotMatrix animation control   │
└───────────────────────────────────────┘
```

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Node.js | 20+ | Install via [nvm](https://github.com/nvm-sh/nvm) or [Homebrew](https://brew.sh) |
| Rust / Cargo | stable | Install via [rustup](https://rustup.rs) |
| Python | 3.11+ | Required for the backend sidecar |
| Tauri CLI | 2.x | `cargo install tauri-cli --version "^2"` |

See [INSTALL.md](INSTALL.md) for step-by-step setup.

## Quick start (development)

```bash
# 1. Install Node dependencies
cd walkie-talkie
npm install

# 2. Set your OpenAI API key
export OPENAI_API_KEY="sk-..."

# 3. Start the Python WebSocket server in one terminal
cd ..
source .venv/bin/activate
idotmatrix-upload serve --port 8765

# 4. In another terminal, launch the Tauri app
cd walkie-talkie
cargo tauri dev
```

The Python server handles BLE scanning and connecting automatically. Make sure
your iDotMatrix device is powered on and within Bluetooth range.

## Run tests

```bash
# Frontend (React / TypeScript)
npm test

# Python backend
cd ..
pytest tests/test_ws_server.py -v
```

## Build for distribution

```bash
# 1. Build the Python sidecar binary
./build-sidecar.sh

# 2. Build and package the Tauri app
cargo tauri build
```

Output: `.dmg` on macOS, `.msi` on Windows, `.AppImage` on Linux — in
`src-tauri/target/release/bundle/`.

See [INSTALL.md](INSTALL.md) for more detail, including cross-compilation and
code signing.

## Architecture

See [AGENTS.md](AGENTS.md) for the full WebSocket protocol reference, file
layout, and development conventions.

For the underlying voice-chat pipeline, iDotMatrix BLE protocol, and
animation system, see the [parent project README](../README.md).
