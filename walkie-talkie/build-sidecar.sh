#!/usr/bin/env bash
# build-sidecar.sh — Build the grot-server Python sidecar for Tauri packaging.
#
# Usage:
#   cd walkie-talkie
#   ./build-sidecar.sh
#
# The script:
#   1. Installs PyInstaller into the project venv if not already present.
#   2. Builds a standalone grot-server binary via PyInstaller.
#   3. Copies it to src-tauri/binaries/ with the target-triple suffix that
#      Tauri requires (e.g. grot-server-aarch64-apple-darwin).
#
# Prerequisites:
#   - The project venv (.venv/) must exist and have the walkie_grotkie
#     package installed (pip install -e ".[voice]").
#   - rustc must be on PATH so we can query the current target triple.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BINARIES_DIR="${SCRIPT_DIR}/src-tauri/binaries"

# ── Activate venv ─────────────────────────────────────────────────────────
VENV="${PROJECT_ROOT}/.venv"
if [[ ! -f "${VENV}/bin/activate" ]]; then
    echo "ERROR: Virtual environment not found at ${VENV}." >&2
    echo "Run: python -m venv .venv && source .venv/bin/activate && pip install -e '.[voice]'" >&2
    exit 1
fi
# shellcheck source=/dev/null
source "${VENV}/bin/activate"

# ── Detect target triple ───────────────────────────────────────────────────
if ! command -v rustc &>/dev/null; then
    echo "ERROR: rustc not found. Install Rust from https://rustup.rs" >&2
    exit 1
fi
TARGET_TRIPLE="$(rustc -vV | grep '^host:' | cut -d' ' -f2)"
echo "Building sidecar for target: ${TARGET_TRIPLE}"

# ── Install PyInstaller ────────────────────────────────────────────────────
if ! python -c "import PyInstaller" &>/dev/null; then
    echo "Installing PyInstaller..."
    pip install pyinstaller
fi

# ── Build the binary ───────────────────────────────────────────────────────
cd "${PROJECT_ROOT}"

pyinstaller \
    --onefile \
    --name grot-server \
    --hidden-import walkie_grotkie \
    --hidden-import walkie_grotkie.ws_server \
    --hidden-import walkie_grotkie.animations \
    --hidden-import walkie_grotkie.openai_chat \
    --hidden-import walkie_grotkie.service \
    --hidden-import walkie_grotkie.chat_commands \
    --hidden-import walkie_grotkie.prompts \
    --hidden-import walkie_grotkie.protocol \
    --hidden-import walkie_grotkie.chat \
    --hidden-import walkie_grotkie.ble \
    --hidden-import walkie_grotkie.preprocess \
    --hidden-import walkie_grotkie.device_cache \
    --collect-all walkie_grotkie \
    --distpath "${SCRIPT_DIR}/dist-sidecar" \
    --workpath "${SCRIPT_DIR}/build-sidecar-work" \
    --specpath "${SCRIPT_DIR}" \
    src/walkie_grotkie/ws_server.py

# ── Copy to Tauri binaries dir with target-triple suffix ──────────────────
mkdir -p "${BINARIES_DIR}"
DEST="${BINARIES_DIR}/grot-server-${TARGET_TRIPLE}"
cp "${SCRIPT_DIR}/dist-sidecar/grot-server" "${DEST}"
echo "Sidecar binary written to: ${DEST}"

# ── Smoke test ────────────────────────────────────────────────────────────
echo "Smoke-testing binary..."
if "${DEST}" --help 2>&1 | grep -q "serve"; then
    echo "Smoke test passed."
else
    echo "WARNING: Smoke test may have failed — verify the binary manually."
fi
