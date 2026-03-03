# AGENTS.md — iDotMatrix Upload Development Guide

## Project Overview

This project implements a CLI tool to upload GIF animations to iDotMatrix LED
matrix devices over Bluetooth Low Energy (BLE). The detailed implementation
plan lives in `docs/plans/upload_implementation.md`.

---

## Tech Stack

- **Language:** Python 3.11+
- **BLE:** [bleak](https://github.com/hbldh/bleak) (async, cross-platform)
- **Image processing:** [Pillow](https://python-pillow.org/)
- **CLI:** [click](https://click.palletsprojects.com/)
- **Testing:** pytest + pytest-asyncio
- **Package management:** pyproject.toml (PEP 621)

---

## Repository Layout

```
src/idotmatrix_upload/    # All production code lives here
  cli.py                  # Click CLI entry point
  ble.py                  # BLE scanning, connection, MTU negotiation
  protocol.py             # Packet framing, chunking, headers
  gif.py                  # GIF validation and preprocessing
  upload.py               # Upload orchestration (ties ble + protocol)
  generate.py             # GIF generation and frame assembly (assemble_gif_from_frames)
  sprite.py               # Sprite loading and frame rendering for animations
tests/                    # pytest test suite
docs/
  grot-animation-guide.md # Grot drawing & animation reference
  plans/                  # Design documents (not committed)
```

---

## Development Guidelines

### General

- Use `async`/`await` throughout — BLE operations are inherently asynchronous.
- Keep modules small and focused: one responsibility per file.
- All public functions must have type annotations.
- Follow the existing import style: stdlib → third-party → local, separated by
  blank lines.

### BLE Layer (`ble.py`)

- Always use `async with` or explicit `try/finally` to guarantee disconnection.
- Default to Write Without Response for data transfer (faster).
- Handle `BleakError` and `asyncio.TimeoutError` explicitly — never let BLE
  exceptions propagate raw to the CLI layer.
- When scanning, use a timeout (default 10 s) to avoid hanging indefinitely.

### Protocol Layer (`protocol.py`)

- All multi-byte integers are **little-endian** (`struct.pack("<...")`).
- The chunk size default is 4096 bytes but must be configurable.
- This module must be **pure** — no I/O, no BLE calls, no file access. It
  receives bytes and returns bytes. This makes it trivially testable.

### GIF Layer (`gif.py`)

- Validate early, fail fast. Check file existence, format, and resolution
  before touching BLE.
- Accept a target size parameter (default 32×32) so the tool works with
  different device models.
- Do not silently resize — only resize when the user passes `--resize`.

### Upload Orchestration (`upload.py`)

- Implement retry logic: up to 3 retries per chunk on ACK timeout.
- Emit progress updates that the CLI can display (callback or async generator).
- On unrecoverable failure, ensure the BLE connection is closed before raising.

### CLI (`cli.py`)

- Use Click for argument parsing.
- Exit codes: 0 = success, 1 = user error (bad file, wrong size), 2 = device
  error (connection failed, upload aborted).
- `--verbose` enables DEBUG-level logging via the `logging` module.

### Testing

- Unit tests go in `tests/` and mirror the `src/` structure
  (`test_protocol.py`, `test_gif.py`, etc.).
- Mock BLE interactions using a fake `BleakClient` — never require a real
  device for CI.
- Use `pytest-asyncio` for async test functions.
- Run tests with: `pytest -v`

### Error Messages

- Always include actionable context: what failed, why, and what the user can
  try. Example: `"Device 'iDotMatrix' not found. Make sure the device is
  powered on and within BLE range, then retry."`.
- Log the full traceback at DEBUG level; show a clean one-liner at INFO level.

---

## Animation & Drawing

For grot character manipulation, sprite-based frame generation, and animated
GIF assembly, see [`docs/grot-animation-guide.md`](docs/grot-animation-guide.md).

Key modules: `sprite.py` (Sprite class, `GROT_PNG` constant) and `generate.py`
(`assemble_gif_from_frames`). The guide covers the Python-first workflow as
well as the browser-based alternative using the pixel editor.

---

## Reference Material

- **Community reverse-engineered client:**
  <https://github.com/derkalle4/python3-idotmatrix-client>
  Consult this for the exact packet header format, characteristic UUIDs, and
  notification handling. The upload logic lives in the `upload` module of that
  repo.
- **Bleak documentation:**
  <https://bleak.readthedocs.io/en/latest/>
- **BLE GATT overview:**
  <https://www.bluetooth.com/specifications/gatt/>

---

## Workflow Checklist

When implementing a new feature or fixing a bug:

1. Read the relevant section of `docs/plans/upload_implementation.md`.
2. Write or update tests first (TDD preferred).
3. Implement the change in the appropriate module.
4. Run `pytest -v` and confirm all tests pass.
5. Keep commits small and focused — one logical change per commit.
