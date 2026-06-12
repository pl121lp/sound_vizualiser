# Sound Visualizer — Project Specification

## 1. Purpose & context

A real-time audio visualizer intended to be integrated into an existing C++ audio streaming pipeline application, for personal use and possibly as the basis of a future product.

The system is split into two decoupled parts:

- **Analysis Engine** — a portable C++ library that performs all signal-processing work (time-domain stats, FFT/frequency-domain analysis, etc.).
- **Visualization Frontend** — consumes the engine's output and renders it. Starts as a Python application for fast iteration, but the engine's interface is designed so other frontends (native desktop, mobile) can bind to it later without changes to the engine itself.

Target platform for initial development: **Linux**. The Analysis Engine itself must remain platform-independent (standard C++17 + a portable header-only FFT library, no Linux-specific APIs), since future targets include Windows and mobile (Android/iOS) via JNI/Dart-FFI/Swift bindings — which rules out a native desktop GUI toolkit (e.g. SDL2/ImGui) as the long-term frontend.

## 2. Architecture

```
┌──────────────────────────────┐      ┌──────────────────────────┐
│   Analysis Engine (C++)      │      │  Visualization Frontend  │
│   - portable C++17 library   │◄────►│  (Python + pyqtgraph)    │
│   - ring buffer              │  C   │  - test harness (WAV)    │
│   - windowing + FFT          │  API │  - render loop           │
│   - feature extraction       │      │  - UI controls           │
└──────────────────────────────┘      └──────────────────────────┘
```

- **Analysis Engine**: CMake-built C++ library with zero GUI/platform dependencies. Owns a ring buffer, applies windowing, runs FFT, computes features.
- **C API boundary** (`extern "C"`): a small, stable interface that all frontends bind to — present-day Python (via pybind11) and, later, the production pipeline's callback/shared-buffer integration plus mobile bindings (JNI / Dart FFI / Swift interop).
  - `create_engine(config) -> EngineHandle`
  - `push_samples(engine, ptr, n_frames, n_channels)`
  - `get_latest_features(engine) -> FeatureFrame`
  - `destroy_engine(engine)`
- **Frontend (PoC)**: Python process that reads a WAV file, feeds chunks into the engine via the binding, pulls `FeatureFrame`s, and renders them with **pyqtgraph** (chosen over matplotlib for real-time/OpenGL-accelerated plotting).

### Why this split

The C API is the long-term contract. Because the heavy computation (FFT, feature extraction) lives in C++ and the data crossing the boundary is small (a few hundred floats per frame), any frontend — Python now, native pipeline integration or mobile UI later — can consume it without the engine needing to change. Python is used for the PoC purely to iterate quickly on visualization styles; if a specific visualization later proves too slow in Python, only that visualization needs a native rewrite.

## 3. Interface contract: `FeatureFrame`

```c
typedef struct {
    uint64_t frame_index;
    uint32_t sample_rate;
    uint32_t channels;

    // Time-domain
    const float* waveform;     // snapshot of latest analysis window, for plotting
    uint32_t waveform_len;
    float rms;
    float zero_crossing_rate;
    float peak;                // max abs sample in window, for VU/peak meter (peak-hold logic lives in frontend)

    // Frequency-domain
    const float* spectrum;     // FFT magnitude bins
    uint32_t spectrum_len;
    float band_energy_low;
    float band_energy_mid;
    float band_energy_high;
    float spectral_centroid;   // weighted mean frequency of spectrum, for brightness-driven effects
} FeatureFrame;
```

### Sizing

Three sizes are independent but related:

- **Push chunk size** — number of samples per `push_samples()` call, driven by the caller (e.g. small blocks like 256 samples, matching whatever block size the pipeline delivers).
- **Analysis window size N** (configurable, e.g. 1024 samples) — the most recent N samples from the ring buffer. This window is used for *both* the waveform snapshot and as input to the FFT, so the waveform and spectrum always represent the same time slice. `waveform_len == N`.
- **Spectrum length** — `spectrum_len == N/2 + 1` (standard real-valued FFT output, e.g. 513 bins for N=1024). The frontend may group/downsample these bins for display (e.g. onto a log scale).
- **Update rate** — how often a new `FeatureFrame` is computed/fetched, independent of push chunk size.

### Config struct (passed to `create_engine`)

Covers: analysis window size N, update rate, FFT window type (Hann/Hamming), number of/definition of frequency bands for band-energy split.

### Memory ownership

The engine owns the buffers behind `waveform`/`spectrum` pointers; they are valid until the next `push_samples`/`get_latest_features` call. The Python binding copies these into numpy arrays for safe use by the frontend.

### Deferred fields

BPM detection and stereo-specific analysis are **not** part of the v1 `FeatureFrame`. They will be added as additional optional fields or an extension struct in Phase 3, once the core loop is validated — this keeps the v1 contract minimal and avoids breaking changes later.

The Phase 3 stereo extension will also need to expose **per-channel waveform snapshots** (not just the mixed/mono `waveform`), since the vectorscope/Lissajous view plots left-channel amplitude against right-channel amplitude sample-by-sample. Onset/beat detection (spectral-flux based) can be computed in the frontend from successive `spectrum`/`band_energy_*` values without any engine change; only if it proves too slow in Python would it move into the engine as an extension field.

## 4. What gets visualized

Across the phases below, the system covers:

- **Time-domain**: waveform, amplitude (e.g. color effects at threshold), RMS, zero-crossing rate (noisiness indicator), peak/VU meter with peak-hold
- **Frequency-domain**: magnitude spectrum (FFT bins) with peak-hold markers, spectrogram (time + frequency), band energy (low/mid/high — simplified EQ-style view), spectral centroid (brightness indicator)
- **Advanced**: BPM detection (preceded by simpler spectral-flux onset/beat-flash), stereo-specific characteristics (correlation/width, vectorscope/Lissajous)
- **Visualization styles**: scrolling vs. static window, vertical bars for frequency bins, color gradients, circular/radial layouts, particle systems for dynamic effects

## 5. Iterative development plan

### Phase 1 — PoC (file-based, in-process library binding)

- **1a. Plumbing skeleton**: ring buffer, `push_samples`/`get_latest_features`, C API + pybind11 binding, WAV file harness. Frontend renders **raw waveform only** — validates the end-to-end interface and data flow before any DSP is added.
- **1b. Spectrum**: add Hann windowing + FFT (pocketfft or kissfft), populate `spectrum`/`spectrum_len`. Frontend adds the **spectrum bar plot**.
- **1c. Scalar features**: add RMS, zero-crossing rate, peak amplitude, band energy (low/mid/high), and spectral centroid, displayed as numeric readouts/bars. Peak amplitude drives a VU/peak meter with peak-hold (hold/decay logic in the frontend). Add C++ unit tests (Catch2 or GoogleTest) validating DSP functions against known signals (e.g. pure sine wave → expected RMS, spectrum peak, and centroid).
- **1d. Configurability**: expose analysis window size, update rate, FFT window type, and band split points via the config struct and harness CLI args.

### Phase 2 — Visualization breadth + interactivity

- **2a. Spectrogram**: scrolling time-frequency view.
- **2b. Radial/circular spectrum**: frequency bins mapped around a circle. Both 2a and 2b add peak-hold markers (decaying max-value indicators per bin), tracked entirely in the frontend from successive `spectrum` frames — no engine change needed.
- **2c. Color gradients / amplitude-threshold effects**, including a brightness-driven gradient using `spectral_centroid`.
- **2d. UI controls**: update-rate slider, visualization-mode selector/buttons.
- **2e. Live audio capture harness** (PortAudio or similar) as an alternative input source to WAV files.
- **2f. Onset/beat-flash effect**: spectral-flux onset detection computed in the frontend from successive `spectrum`/`band_energy_*` values, driving a simple flash/pulse effect. Acts as a stepping stone toward full BPM detection in 3a.

### Phase 3 — Advanced analysis

- **3a. BPM detection** — full tempo tracking, added via a new optional extension struct, without breaking the v1 `FeatureFrame`. Builds on the onset/beat-flash work from 2f.
- **3b. Stereo analysis** — channel correlation/width and vectorscope/Lissajous view; requires multi-channel handling in the engine, including per-channel waveform snapshots in the extension struct (see Deferred fields).
- **3c. Particle-system effects** in the frontend.
- **3d. Smoothing** — e.g. exponential moving average on spectrum bins/scalar features, for less jittery visuals.

### Phase 4 — Pipeline integration & mobile groundwork

- Wire the engine into the real pipeline: the pipeline's audio thread calls `push_samples` directly (replacing the WAV harness). Confirm/extend the C API for thread-safety (audio thread writes, UI/render thread reads).
- Begin evaluating mobile bindings (Android JNI / Dart FFI / Swift interop) against the same C API, with a native mobile UI replacing pyqtgraph.

## 6. Real-time considerations

- **Buffering**: ring buffer for incoming samples; analysis operates on a sliding N-sample window.
- **Latency vs. resolution**: smaller analysis windows → faster updates, noisier spectral estimates; larger windows → smoother spectra, more lag. Window size is configurable (Phase 1d).
- **Windowing**: Hann or Hamming window applied before FFT to reduce spectral leakage.
- **Smoothing**: optional EMA smoothing of features (Phase 3d) to reduce visual jitter.

## 7. Configurable parameters (consolidated)

- Analysis window size N (samples)
- Update rate (Hz)
- FFT window type (Hann/Hamming)
- Frequency band split points (for low/mid/high band energy)
- Audio input source (WAV file for PoC; live capture in Phase 2e; pipeline callback in Phase 4)
- Sample rate / channel count (inferred from input source)
- Visualization mode (selected in frontend, Phase 2d)
