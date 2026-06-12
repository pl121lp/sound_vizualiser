# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

This repository is in the planning/specification stage. There is currently no source code, build system, or test suite — only `project_spec_draft.md`, a working draft of the system specification.

The immediate task requested for this repo is to collaborate on refining `project_spec_draft.md` into a finalized `project_spec_final.md` (determining feature scope/iteration order and cross-platform architecture details), not to write implementation code, unless the user has since moved past this stage.

## Intended architecture (per spec draft)

The system is a real-time audio visualizer split into two decoupled components:

- **Backend (analysis engine)**: portable C++ engine that performs audio analysis (time-domain stats, FFT/frequency-domain analysis, etc.) on chunks of audio samples.
- **Frontend (visualization)**: a separate, swappable rendering layer (initially Python or a platform-specific framework) that consumes analysis output through a clean interface, allowing the frontend to be replaced independently of the backend.

Key design considerations called out in the spec that should inform any implementation work:
- Visualization spans time-domain (waveform, amplitude, RMS, zero-crossing rate), frequency-domain (FFT magnitude spectrum, spectrogram, band energy), and higher-level analysis (BPM detection, stereo characteristics).
- Real-time processing uses chunked buffers (e.g., 256–2048 samples) and ring buffers for smooth scrolling; buffer size trades off latency vs. resolution.
- FFT processing should apply windowing (Hann/Hamming) and smoothing.
- Configurable parameters include window size, update rate, audio input source/sample rate/channels (inferred from file).
