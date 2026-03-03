# iDotMatrix Upload

CLI tool for uploading GIF animations to iDotMatrix LED matrix devices over
Bluetooth Low Energy (BLE).

## Installation

```bash
# Core tool (upload, generate, preprocess)
pip install -e .

# With chat feature (adds Anthropic SDK + Rich)
pip install -e ".[chat]"

# With dev dependencies (pytest)
pip install -e ".[dev]"

# Everything
pip install -e ".[chat,dev]"
```

## Quick start

### Upload a GIF

```bash
idotmatrix-upload upload path/to/animation.gif
```

### Interactive chat with Grot

Chat with an AI character that controls live animations on your iDotMatrix
device. Grot reacts to the conversation: thinking, talking, dancing, and more.

#### 1. Get an Anthropic API key

1. Go to <https://console.anthropic.com/settings/keys>
2. Create a new API key
3. Copy the key (starts with `sk-ant-...`)

#### 2. Configure the key

Copy the example environment file and add your key:

```bash
cp .env.example .env
```

Edit `.env` and replace the placeholder with your actual key:

```
ANTHROPIC_API_KEY=sk-ant-your-actual-key-here
```

Then load it into your shell:

```bash
source .env && export ANTHROPIC_API_KEY
```

Or pass it directly:

```bash
export ANTHROPIC_API_KEY="sk-ant-your-actual-key-here"
```

#### 3. Start chatting

```bash
idotmatrix-upload chat
```

Options:

| Flag | Description |
|---|---|
| `--device-addr ADDR` | BLE address (skip scan) |
| `--model NAME` | Anthropic model (default: claude-sonnet-4-20250514) |
| `--animations-dir DIR` | Path to animation GIFs (default: `grot_animations`) |
| `--no-cache` | Skip device address cache |
| `-v, --verbose` | Debug logging |

## Other commands

```bash
# Generate test GIFs
idotmatrix-upload generate --count 5

# Preprocess GIFs for the device
idotmatrix-upload preprocess path/to/gif.gif --size 64x64

# Assemble PNG frames into a GIF
idotmatrix-upload assemble-gif frames_dir/ -o output.gif --fps 20
```

## Development

```bash
pip install -e ".[chat,dev]"
pytest -v
```
