# CLAUDE.md

## Project

Walkie-Grotkie — CLI tool for uploading GIF animations to iDotMatrix
LED matrix devices over BLE.

## Stack

- Python 3.11+, bleak (BLE), Pillow (images), click (CLI)
- Testing: pytest + pytest-asyncio

## Commands

- Install deps: `pip install -e ".[dev]"`
- Run tests: `pytest -v`
- Run the tool: `walkie-grotkie <gif_path>`

## Code layout

- `src/walkie_grotkie/` — production code
- `tests/` — test suite
- `docs/plans/` — design docs (not committed)

## Conventions

- Async everywhere (BLE is async by nature)
- Little-endian for all wire integers
- `protocol.py` is pure (no I/O) — keep it that way
- Type annotations on all public functions
- Fail fast on invalid input; clean error messages with actionable advice
