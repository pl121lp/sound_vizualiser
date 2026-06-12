# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

Implementation is underway per `project_spec_final.md`. The repo has two main parts:

- `engine/`: C++ analysis engine (CMake build, pybind11 bindings, unit tests via ctest).
- `frontend/`: Python visualization layer that consumes the engine through the pybind11 bindings.

## Build, setup, and run scripts

- `engine/build.sh`: Configures and builds the C++ engine with CMake, then runs the unit tests via ctest. If the frontend venv exists, it auto-detects pybind11's cmake dir so the Python bindings module gets built too. Run this after any change to `engine/` C++ source.
  ```
  ./engine/build.sh
  ```
  Set `BUILD_TYPE=Debug ./engine/build.sh` for a debug build.

- `frontend/setup_venv.sh`: Creates `frontend/.venv` and installs `frontend/requirements.txt`. Run this once before building the engine (so pybind11 is available) and before running the frontend.
  ```
  ./frontend/setup_venv.sh
  ```

- `frontend/run.sh`: Runs any command with the frontend venv's Python, without needing to activate it. Use this to run `main.py` or any other frontend script/module.
  ```
  ./frontend/run.sh main.py fixtures/test_tone.wav
  ./frontend/run.sh -m pip list
  ```

Typical first-time setup: `./frontend/setup_venv.sh` then `./engine/build.sh` (so the venv exists and pybind11 module gets built), then `./frontend/run.sh main.py <file>` to run the visualizer.

## Intended architecture (per spec draft)

The system is a real-time audio visualizer split into two decoupled components:

- **Backend (analysis engine)**: portable C++ engine that performs audio analysis (time-domain stats, FFT/frequency-domain analysis, etc.) on chunks of audio samples.
- **Frontend (visualization)**: a separate, swappable rendering layer (initially Python or a platform-specific framework) that consumes analysis output through a clean interface, allowing the frontend to be replaced independently of the backend.

Key design considerations called out in the spec that should inform any implementation work:
- Visualization spans time-domain (waveform, amplitude, RMS, zero-crossing rate), frequency-domain (FFT magnitude spectrum, spectrogram, band energy), and higher-level analysis (BPM detection, stereo characteristics).
- Real-time processing uses chunked buffers (e.g., 256–2048 samples) and ring buffers for smooth scrolling; buffer size trades off latency vs. resolution.
- FFT processing should apply windowing (Hann/Hamming) and smoothing.
- Configurable parameters include window size, update rate, audio input source/sample rate/channels (inferred from file).
