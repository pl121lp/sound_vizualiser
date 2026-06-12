#!/usr/bin/env bash
# Run a command using the frontend virtualenv's python.
# Usage: frontend/run.sh main.py fixtures/test_tone.wav
#        frontend/run.sh -m pip list
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/.venv"

if [ ! -x "${VENV_DIR}/bin/python" ]; then
    echo "Virtualenv not found at ${VENV_DIR}. Run frontend/setup_venv.sh first." >&2
    exit 1
fi

exec "${VENV_DIR}/bin/python" "$@"
