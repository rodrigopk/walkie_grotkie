# Walkie-Grotkie

CLI tool for uploading GIF animations to
[iDotMatrix](https://www.idotmatrix.com/) LED matrix devices over Bluetooth Low
Energy (BLE) — plus interactive text and voice chat with **Grot**, an animated
character that lives on the display and reacts to your conversation in real
time.

## Prerequisites

- **Python 3.11+**
- An **iDotMatrix** LED matrix device (32×32 or 64×64) within BLE range
- **macOS, Linux, or Windows** (any platform supported by
  [bleak](https://github.com/hbldh/bleak))

For voice chat you also need a working microphone and speakers/headphones.

## Installation

Clone the repo and install in editable mode:

```bash
git clone https://github.com/rodrigopk/walkie-grotkie.git
cd walkie-grotkie
```

Pick the extras you need:

```bash
# Core only (upload, generate, preprocess, assemble-gif)
pip install -e .

# Text chat with Grot (adds Anthropic SDK + Rich)
pip install -e ".[chat]"

# Voice chat with Grot (adds OpenAI SDK + sounddevice + pynput)
pip install -e ".[voice]"

# Development (pytest + pytest-asyncio)
pip install -e ".[dev]"

# Everything
pip install -e ".[chat,voice,dev]"
```

---

## Walkie-Talkie app

The `walkie-talkie/` directory contains a **Tauri 2** desktop app — the primary
way to interact with Grot. Press and hold the big button to speak; the LED
display shows transcriptions, responses, and status messages in real time.

Architecture: Tauri window (React webview) communicates with the Python
voice-chat pipeline over a local WebSocket. The Python server runs as a bundled
sidecar — no separate terminal or manual server startup needed.

### Quick start (development)

```bash
cd walkie-talkie
npm install
./build-sidecar.sh    # builds the Python sidecar binary (once, or after Python changes)
cargo tauri dev
```

On first launch, the app will prompt you for your OpenAI API key via the
Settings screen. The key is validated and stored locally — no environment
variables required.

### Build and install (macOS DMG)

Building a distributable `.dmg` requires Rust, Node.js, the Tauri CLI, and
Xcode Command Line Tools.

#### 1. Install build prerequisites

```bash
# Rust (if not already installed)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source "$HOME/.cargo/env"

# Tauri CLI
cargo install tauri-cli --version "^2"

# Xcode Command Line Tools
xcode-select --install
```

#### 2. Build the Python sidecar

From the `walkie-talkie/` directory:

```bash
cd walkie-talkie
./build-sidecar.sh
```

This produces `src-tauri/binaries/grot-server-<target-triple>` — the bundled
Python server that ships inside the app.

#### 3. Package the app

```bash
cargo tauri build
```

The `.dmg` and `.app` are written to:

```
walkie-talkie/src-tauri/target/release/bundle/dmg/
```

#### 4. Install

Open the `.dmg`, drag **Grot Walkie-Talkie** to `/Applications`, and launch it.
No Python or Node.js installation is required on the end user's machine — the
sidecar is self-contained.

See [`walkie-talkie/INSTALL.md`](walkie-talkie/INSTALL.md) for Windows/Linux
equivalents and troubleshooting.

---

## Text chat with Grot

Chat with an AI character powered by Claude that controls live animations on
your iDotMatrix device. Grot reacts to the conversation — thinking, talking,
dancing, sleeping, and more.

### 1. Get an Anthropic API key

1. Go to <https://console.anthropic.com/settings/keys>
2. Create a new API key
3. Copy the key (starts with `sk-ant-...`)

### 2. Set the key

Copy the example env file and fill in your key:

```bash
cp .env.example .env
# Edit .env and replace the placeholder:
#   ANTHROPIC_API_KEY=sk-ant-your-actual-key-here
source .env && export ANTHROPIC_API_KEY
```

Or export it directly in your shell:

```bash
export ANTHROPIC_API_KEY="sk-ant-your-actual-key-here"
```

### 3. Start chatting

```bash
walkie-grotkie chat
```

Example session:

```
🤖 Grot is ready! Type your message (or /help for commands).

You: Hey Grot, tell me a joke!
Grot: *excited* Why do LED matrices never get lonely?
      Because they always have a bright personality! 💡

You: Nice one! Can you dance?
Grot: *dancing* You bet I can! Watch the lights go!

You: /help
Available commands:
  /help        Show this help
  /animation   Show current animation state
  /exit        Quit the chat

You: /exit
```

### Chat options

| Flag | Default | Description |
|---|---|---|
| `--device-addr ADDR` | *(scan)* | BLE address (skip scan) |
| `--model NAME` | `claude-sonnet-4-20250514` | Anthropic model |
| `--animations-dir DIR` | `grot_animations` | Path to animation GIFs |
| `--temperature N` | `0.7` | Sampling temperature (0–2) |
| `--no-cache` | | Skip device address cache |
| `-d, --debug` | | Write debug logs to `grot-chat.log` |

---

## Voice chat with Grot (legacy CLI)

Talk to Grot with your voice from the terminal. Hold **Space** to speak,
release to send. Your speech is transcribed with Whisper, answered by GPT-4o,
and spoken back via OpenAI TTS — all while Grot's animations sync to the
conversation.

> **Tip:** For a nicer experience use the [Walkie-Talkie app](#walkie-talkie-app) above.

### 1. Get an OpenAI API key

1. Go to <https://platform.openai.com/api-keys>
2. Create a new API key
3. Copy the key (starts with `sk-...`)

### 2. Set the key

```bash
export OPENAI_API_KEY="sk-your-openai-key-here"
```

### 3. Start talking

```bash
walkie-grotkie voice-chat
```

Example session:

```
🎙️  Voice chat ready! Hold SPACE to speak, release to send.

[SPACE held]  Recording...
[SPACE released]  Transcribing...
You: "What's the weather like on your LED matrix?"
Grot (speaking): "It's always sunny here — 64 by 64 pixels of pure warmth!"

[SPACE held]  Recording...
[SPACE released]  Transcribing...
You: "Show me a dance!"
Grot (speaking): "Watch this!" *dancing*
```

### Voice chat options

| Flag | Default | Description |
|---|---|---|
| `--device-addr ADDR` | *(scan)* | BLE address (skip scan) |
| `--model NAME` | `gpt-4o` | OpenAI chat model |
| `--voice NAME` | `nova` | TTS voice (`alloy`, `ash`, `coral`, `echo`, `fable`, `nova`, `onyx`, `sage`, `shimmer`, `verse`) |
| `--animations-dir DIR` | `grot_animations` | Path to animation GIFs |
| `--temperature N` | `0.7` | Sampling temperature (0–2) |
| `--no-cache` | | Skip device address cache |
| `-d, --debug` | | Write debug logs to `grot-voice-chat.log` |

---

## Other commands

### Generate test GIFs

Create numbered spinning-digit GIFs for testing uploads:

```bash
walkie-grotkie generate --count 5 --output-dir ./test_gifs
```

### Preprocess GIFs

Validate and resize GIFs for the device without uploading:

```bash
walkie-grotkie preprocess animation.gif --size 64x64 --output-dir ./processed
```

### Assemble PNG frames into a GIF

Combine a directory of PNG frames into an animated GIF:

```bash
walkie-grotkie assemble-gif frames_dir/ -o output.gif --fps 20
```

Resize during assembly:

```bash
walkie-grotkie assemble-gif frames_dir/ -o output.gif --fps 12 --size 64x64
```

## Pixel art editor

The `pixel-art-editor/` directory contains a browser-based 64×64 pixel art
editor (React + Vite + TypeScript) for creating and editing Grot sprites and
animation frames. See
[`docs/grot-animation-guide.md`](docs/grot-animation-guide.md) for the full
animation workflow.

```bash
cd pixel-art-editor
npm install
npm run dev
```

## BLE tools

Standalone scripts in `tools/` for exploring and debugging iDotMatrix devices:

```bash
# Explore GATT services and characteristics
python tools/ble_explore.py [DEVICE_ADDR]

# Probe upload and OTA characteristics
python tools/ble_probe.py [DEVICE_ADDR]
```

---

## Upload script

Upload GIF animations directly to the device over BLE — the original core
feature of this tool.

```bash
walkie-grotkie upload path/to/animation.gif
```

Upload multiple GIFs in one go:

```bash
walkie-grotkie upload anim1.gif anim2.gif anim3.gif --delay 2.0
```

Skip the BLE scan by passing a known device address:

```bash
walkie-grotkie upload animation.gif --device-addr "AA:BB:CC:DD:EE:FF"
```

---

## Development

```bash
pip install -e ".[chat,voice,dev]"
pytest -v
```
