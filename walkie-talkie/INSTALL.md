# Installation Guide

Step-by-step setup for the Grot Walkie-Talkie desktop app across all supported platforms.

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Python backend setup](#2-python-backend-setup)
3. [Rust and Tauri prerequisites](#3-rust-and-tauri-prerequisites)
4. [Node.js setup](#4-nodejs-setup)
5. [Install dependencies](#5-install-dependencies)
6. [Configure API keys](#6-configure-api-keys)
7. [Run in development mode](#7-run-in-development-mode)
8. [Build the sidecar binary](#8-build-the-sidecar-binary)
9. [Build a distributable package](#9-build-a-distributable-package)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Prerequisites

| Tool | Minimum version | Install |
|---|---|---|
| Python | 3.11 | [python.org](https://www.python.org/downloads/) or Homebrew (`brew install python@3.13`) |
| Rust | stable | [rustup.rs](https://rustup.rs) |
| Node.js | 20 | [nodejs.org](https://nodejs.org) or Homebrew (`brew install node`) |
| Tauri CLI | 2.x | `cargo install tauri-cli --version "^2"` |

### macOS additional requirement

Xcode Command Line Tools (provides `clang`, `ld`, `webkit2gtk` etc.):

```bash
xcode-select --install
```

### Windows additional requirement

[Microsoft C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
and [WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/)
(ships with Windows 11; download separately for Windows 10).

### Linux additional requirement

```bash
# Ubuntu / Debian
sudo apt update && sudo apt install -y \
    libwebkit2gtk-4.1-dev build-essential curl wget file \
    libssl-dev libayatana-appindicator3-dev librsvg2-dev \
    libgtk-3-dev libglib2.0-dev
```

---

## 2. Python backend setup

From the **repository root** (not the `walkie-talkie/` subdirectory):

```bash
# Create and activate a virtual environment
python3.13 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install the package with voice-chat extras
pip install -e ".[voice]"
```

Verify the install:

```bash
walkie-grotkie --version
walkie-grotkie serve --help
```

---

## 3. Rust and Tauri prerequisites

```bash
# Install Rust via rustup (if not already installed)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source "$HOME/.cargo/env"

# Verify Rust
rustc --version  # should print rustc 1.7x.x

# Install Tauri CLI
cargo install tauri-cli --version "^2"

# Verify Tauri CLI
cargo tauri --version  # should print tauri-cli 2.x.x
```

---

## 4. Node.js setup

```bash
# Using Homebrew (macOS)
brew install node

# Using nvm (any platform)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.0/install.sh | bash
nvm install --lts
nvm use --lts

# Verify
node --version  # should print v20.x.x or later
npm --version
```

---

## 5. Install dependencies

From the `walkie-talkie/` directory:

```bash
cd walkie-talkie
npm install
```

---

## 6. Configure API keys

The voice-chat backend requires an OpenAI API key for Whisper (STT), GPT-4o
(LLM), and TTS.

```bash
# Option A: Export directly in your shell
export OPENAI_API_KEY="sk-your-key-here"

# Option B: Add to the project .env file (from the repo root)
echo 'OPENAI_API_KEY=sk-your-key-here' >> ../.env
```

Get an API key at [platform.openai.com/api-keys](https://platform.openai.com/api-keys).

---

## 7. Run in development mode

Open two terminals.

**Terminal 1 — Python WebSocket server:**

```bash
cd /path/to/walkie-grotkie
source .venv/bin/activate
export OPENAI_API_KEY="sk-..."
walkie-grotkie serve --port 8765
```

**Terminal 2 — Tauri app:**

```bash
cd /path/to/walkie-grotkie/walkie-talkie
cargo tauri dev
```

Tauri will build the Rust shell, start the Vite dev server, and open the
walkie-talkie window. Changes to React source files hot-reload automatically.

### Development mode without a real iDotMatrix device

If you don't have a device but still want to test the UI + voice pipeline:

```bash
walkie-grotkie serve --port 8765 --no-cache
```

The server will fail to find a BLE device and send an error message to the
UI, but you can still exercise the UI layout and WebSocket protocol.

---

## 8. Build the sidecar binary

The sidecar is a standalone `grot-server` binary (built with PyInstaller) that
Tauri bundles alongside the app for distribution.

```bash
cd walkie-talkie
./build-sidecar.sh
```

This produces `walkie-talkie/src-tauri/binaries/grot-server-<target-triple>`.

Prerequisites: `rustc` on PATH (for target triple detection), Python venv activated.

---

## 9. Build a distributable package

```bash
# From the walkie-talkie/ directory
cargo tauri build
```

Output locations:

| Platform | Format | Location |
|---|---|---|
| macOS | `.dmg`, `.app` | `src-tauri/target/release/bundle/dmg/` |
| Windows | `.msi`, `.exe` | `src-tauri/target/release/bundle/msi/` |
| Linux | `.AppImage`, `.deb` | `src-tauri/target/release/bundle/appimage/` |

The built bundle includes the `grot-server` sidecar — no Python installation
is required on the end user's machine.

---

## 10. Troubleshooting

### Microphone permission denied in the app

- **macOS:** System Settings → Privacy & Security → Microphone → enable for the app.
- **Windows:** Settings → Privacy → Microphone → allow desktop apps.
- **Linux:** Ensure PulseAudio/PipeWire is running and the user is in the `audio` group.

### BLE device not found

- Confirm the iDotMatrix device is powered on and within 5–10 metres.
- The device must be named with the `IDM-` prefix.
- On Linux, ensure the user is in the `bluetooth` group and BlueZ is running.
- Pass the device address directly to skip scanning:
  `walkie-grotkie serve --device-addr AA:BB:CC:DD:EE:FF`

### WebView2 not found (Windows)

Download and install [Microsoft Edge WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/).

### cargo tauri build fails with linker error (Linux)

```bash
sudo apt install libwebkit2gtk-4.1-dev libssl-dev libayatana-appindicator3-dev librsvg2-dev
```

### PyInstaller binary fails to start

Run the binary directly with `--help` and check the error output:

```bash
./walkie-talkie/src-tauri/binaries/grot-server-* --help
```

Common causes: missing shared libraries (`ldd ./grot-server`), or the
virtual environment used to build it had a different Python version than the
system Python.

### Port 8765 already in use

```bash
# Find the process
lsof -i :8765

# Or start the server on a different port and update the frontend constant
walkie-grotkie serve --port 9000
# Then change WS_URL in walkie-talkie/src/App.tsx to "ws://localhost:9000"
```
