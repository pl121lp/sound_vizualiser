# Phase 1a — Plumbing Skeleton: Design

Status: approved
Date: 2026-06-12
Parent spec: `project_spec_final.md` (section 5, Phase 1a)

## Goal

Validate the end-to-end interface and data flow between the C++ analysis
engine and the Python frontend, with **no DSP yet**. The frontend renders the
raw waveform only.

## Repo layout

```
engine/
  CMakeLists.txt
  include/sound_viz/feature_frame.h   # FeatureFrame, EngineConfig structs
  include/sound_viz/engine.h          # C API (extern "C")
  src/ring_buffer.h
  src/ring_buffer.cpp
  src/engine.cpp                      # create/destroy/push/get_latest_features
  bindings/python_bindings.cpp        # pybind11 module
frontend/
  requirements.txt
  .venv/                              # gitignored
  main.py                             # WAV harness + pyqtgraph render loop
```

## C API & data contracts

### EngineConfig

Minimal for 1a; extended in later phases (update rate, FFT window type, band
splits in 1b–1d) without breaking this shape.

```c
typedef struct {
    uint32_t window_size;   // N, e.g. 1024 — size of the analysis window
    uint32_t sample_rate;   // from WAV header; echoed back in FeatureFrame
} EngineConfig;
```

### FeatureFrame

The full v1 struct from `project_spec_final.md` section 3 is defined now, so
the C API shape doesn't change across phases 1a–1d. In 1a, only the
time-domain waveform fields are populated:

```c
typedef struct {
    uint64_t frame_index;
    uint32_t sample_rate;
    uint32_t channels;

    // Time-domain
    const float* waveform;     // populated in 1a: latest N samples, mono
    uint32_t waveform_len;     // == window_size (N)
    float rms;                 // 0 in 1a (added in 1c)
    float zero_crossing_rate;  // 0 in 1a (added in 1c)
    float peak;                // 0 in 1a (added in 1c)

    // Frequency-domain
    const float* spectrum;     // nullptr in 1a (added in 1b)
    uint32_t spectrum_len;     // 0 in 1a
    float band_energy_low;     // 0 in 1a (added in 1c)
    float band_energy_mid;     // 0 in 1a (added in 1c)
    float band_energy_high;    // 0 in 1a (added in 1c)
    float spectral_centroid;   // 0 in 1a (added in 1c)
} FeatureFrame;
```

### Functions

```c
EngineHandle create_engine(EngineConfig config);
void push_samples(EngineHandle engine, const float* samples, uint32_t n_frames, uint32_t n_channels);
FeatureFrame get_latest_features(EngineHandle engine);
void destroy_engine(EngineHandle engine);
```

## Engine internals

- **Ring buffer** stores mono `float` samples. Multi-channel input passed to
  `push_samples` (interleaved) is mixed down to mono by averaging channels at
  push time.
- Ring buffer capacity is at least `window_size` samples.
- `get_latest_features` returns the most recent `window_size` samples as
  `waveform`. Until the buffer has received `window_size` samples in total,
  the snapshot is zero-padded at the start so `waveform_len` is always `N`.
- `frame_index` is a counter incremented once per `get_latest_features` call.
- `channels` in the returned `FeatureFrame` reflects the `n_channels`
  argument from the most recent `push_samples` call.
- Memory ownership: the engine owns the buffer behind `waveform`; it remains
  valid until the next `push_samples` or `get_latest_features` call, per the
  spec's memory-ownership rule.

## pybind11 binding

- A thin `PyEngine` class wraps `create_engine` / `push_samples` /
  `get_latest_features` / `destroy_engine`.
- `push_samples(np.ndarray)`: accepts a numpy `float32` array (interleaved if
  multi-channel) and passes a pointer + shape info directly into
  `push_samples`.
- `get_latest_features()`: copies `waveform` (and, in later phases,
  `spectrum`) into fresh numpy arrays before returning a Python dict/object —
  so the caller never holds engine-owned pointers, satisfying the
  memory-ownership contract.

## Python harness (`frontend/main.py`)

- CLI argument: path to a WAV file, read via `soundfile`.
- Creates the engine with `window_size=1024` and `sample_rate` taken from the
  WAV file's header.
- A `QTimer` reads and pushes chunks (e.g. 1024 frames) at an interval derived
  from `chunk_size / sample_rate`, so the visualization scrolls at roughly
  real-time pace. No audio playback in 1a — out of scope per the parent spec.
- Each tick: push the next chunk → call `get_latest_features()` → update a
  single `pyqtgraph` `PlotWidget` curve with the returned waveform snapshot.

## Build & environment

- `engine/CMakeLists.txt` uses CMake `FetchContent` to pull in pybind11 at
  build time (no system-wide pybind11 install required), and builds the
  Python extension module into `engine/build/`.
- `frontend/.venv` + `requirements.txt` cover `pyqtgraph`, `PyQt5`,
  `soundfile`, and `numpy`.

## Validation for 1a

No formal unit tests yet — Catch2/GoogleTest C++ unit tests arrive in 1c once
there's DSP to validate against known signals. Validation for 1a is manual
end-to-end: build the engine module, run the harness against a sample WAV
file, and confirm the waveform renders and scrolls smoothly with no crashes.

## Out of scope for 1a (deferred to later phases)

- FFT / spectrum (1b)
- RMS, zero-crossing rate, peak, band energy, spectral centroid, C++ unit
  tests (1c)
- Configurable window size / update rate / FFT window type / band splits via
  config struct and CLI args (1d)
