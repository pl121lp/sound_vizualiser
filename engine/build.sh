#!/usr/bin/env bash
# Configure, build, and run the unit tests for the sound_viz_engine C++ library.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${SCRIPT_DIR}/build"
BUILD_TYPE="${BUILD_TYPE:-Release}"
VENV_PYTHON="${SCRIPT_DIR}/../frontend/.venv/bin/python"

CMAKE_EXTRA_ARGS=()
if [ -x "${VENV_PYTHON}" ]; then
    PYBIND11_DIR="$("${VENV_PYTHON}" -m pybind11 --cmakedir 2>/dev/null || true)"
    if [ -n "${PYBIND11_DIR}" ]; then
        CMAKE_EXTRA_ARGS+=("-Dpybind11_DIR=${PYBIND11_DIR}")
    fi
fi

cmake -S "${SCRIPT_DIR}" -B "${BUILD_DIR}" -DCMAKE_BUILD_TYPE="${BUILD_TYPE}" "${CMAKE_EXTRA_ARGS[@]}"
cmake --build "${BUILD_DIR}" -j"$(nproc)"

ctest --test-dir "${BUILD_DIR}" --output-on-failure
