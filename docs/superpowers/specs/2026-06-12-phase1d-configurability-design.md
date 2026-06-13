# Phase 1d — Configurability: Design

## Goal

Per `project_spec_final.md` Phase 1d, expose analysis window size, update
rate, FFT window type, and band split points via `EngineConfig` and the
frontend CLI args, so these can be tuned without recompiling.

## 1. `EngineConfig` struct (`engine/include/sound_viz/feature_frame.h`)

Add a new enum and four new fields:

```cpp
typedef enum {
    WINDOW_HANN = 0,
    WINDOW_HAMMING = 1,
} FftWindowType;

typedef struct {
    uint32_t window_size;       // existing
    uint32_t sample_rate;       // existing
    float update_rate_hz;       // advisory; echoed back, not used internally
    FftWindowType fft_window_type;
    float band_split_low_hz;    // replaces hardcoded 250.0f
    float band_split_high_hz;   // replaces hardcoded 4000.0f
} EngineConfig;
```

`update_rate_hz` is informational only — the engine does not gate
recomputation on it. `get_latest_features()` continues to recompute every
call, as today. The field exists so the frontend's chosen rate can be
threaded through `EngineConfig` (satisfying "expose ... via the config
struct") even though the engine doesn't act on it.

## 2. Window module (`engine/src/window.h` / `.cpp`)

Add `hamming_window`, matching the existing `hann_window` signature and
style:

```cpp
// Fills `out` (size n) with Hamming window coefficients.
void hamming_window(float* out, size_t n);
```

```cpp
void hamming_window(float* out, size_t n) {
    if (n == 1) {
        out[0] = 1.0f;
        return;
    }
    const float two_pi = 6.283185307179586f;
    for (size_t i = 0; i < n; ++i) {
        out[i] = 0.54f - 0.46f * std::cos(two_pi * static_cast<float>(i) / static_cast<float>(n - 1));
    }
}
```

## 3. Engine wiring (`engine/src/engine.cpp`)

- Rename `hann_coeffs` to `window_coeffs` (both the member variable and any
  local references) for clarity now that it can hold either window's
  coefficients.
- In the `EngineImpl` constructor, select which function fills
  `window_coeffs` based on `config.fft_window_type`:

```cpp
switch (config.fft_window_type) {
    case WINDOW_HAMMING:
        sound_viz::hamming_window(window_coeffs.data(), window_coeffs.size());
        break;
    case WINDOW_HANN:
    default:
        sound_viz::hann_window(window_coeffs.data(), window_coeffs.size());
        break;
}
```

- In `get_latest_features`, pass `config.band_split_low_hz` and
  `config.band_split_high_hz` through to `compute_band_energy` (see below).

## 4. `dsp_features` band split points (`engine/src/dsp_features.h` / `.cpp`)

- Remove the file-local constants `kBandLowMidHz` / `kBandMidHighHz`.
- Change `compute_band_energy`'s signature to take the split points as
  parameters:

```cpp
BandEnergy compute_band_energy(const float* spectrum, size_t spectrum_len,
                                uint32_t sample_rate, uint32_t window_size,
                                float low_split_hz, float high_split_hz);
```

- `compute_spectral_centroid` is unchanged (it has no band-boundary logic).
- `engine.cpp` calls:

```cpp
sound_viz::BandEnergy band_energy = sound_viz::compute_band_energy(
    impl->spectrum_out.data(), impl->spectrum_out.size(),
    impl->config.sample_rate, impl->config.window_size,
    impl->config.band_split_low_hz, impl->config.band_split_high_hz);
```

## 5. Python bindings (`engine/bindings/python_bindings.cpp`)

`PyEngine`'s constructor gains new keyword args with defaults matching
current (Phase 1c) behavior, so existing call sites
(`Engine(window_size=..., sample_rate=...)`) keep working unchanged:

```cpp
PyEngine(uint32_t window_size, uint32_t sample_rate,
         float update_rate_hz = 0.0f,
         const std::string& fft_window_type = "hann",
         float band_split_low_hz = 250.0f,
         float band_split_high_hz = 4000.0f) {
    EngineConfig config{};
    config.window_size = window_size;
    config.sample_rate = sample_rate;
    config.update_rate_hz = update_rate_hz;
    config.band_split_low_hz = band_split_low_hz;
    config.band_split_high_hz = band_split_high_hz;

    if (fft_window_type == "hann") {
        config.fft_window_type = WINDOW_HANN;
    } else if (fft_window_type == "hamming") {
        config.fft_window_type = WINDOW_HAMMING;
    } else {
        throw py::value_error("fft_window_type must be 'hann' or 'hamming'");
    }

    handle_ = create_engine(config);
}
```

`PYBIND11_MODULE` registration adds the new constructor args with defaults:

```cpp
.def(py::init<uint32_t, uint32_t, float, const std::string&, float, float>(),
     py::arg("window_size"), py::arg("sample_rate"),
     py::arg("update_rate_hz") = 0.0f,
     py::arg("fft_window_type") = "hann",
     py::arg("band_split_low_hz") = 250.0f,
     py::arg("band_split_high_hz") = 4000.0f)
```

Window type is passed as a string ("hann"/"hamming") at the Python boundary
for ergonomics, converted to `FftWindowType` inside the constructor.

## 6. Frontend CLI args (`frontend/main.py`)

New `argparse` arguments:

```python
parser.add_argument("--window-size", type=int, default=1024, help="Analysis window size (samples)")
parser.add_argument("--update-rate", type=float, default=30.0, help="Target UI update rate (Hz)")
parser.add_argument("--fft-window", choices=["hann", "hamming"], default="hann", help="FFT window function")
parser.add_argument("--band-split-low", type=float, default=250.0, help="Low/mid band split frequency (Hz)")
parser.add_argument("--band-split-high", type=float, default=4000.0, help="Mid/high band split frequency (Hz)")
```

These are passed into `args` and through to `WaveformWindow(wav_path, args)`
(the constructor signature gains an `args` parameter).

### Module-level constants become per-instance

`WINDOW_SIZE` and `SPECTRUM_LEN` are currently module-level constants used by
`WaveformWindow.__init__` and `on_tick`. They become instance attributes
derived from `args.window_size`:

```python
self.window_size = args.window_size
self.spectrum_len = self.window_size // 2 + 1
```

All current uses of `WINDOW_SIZE`/`SPECTRUM_LEN` within `WaveformWindow`
become `self.window_size`/`self.spectrum_len`. `CHUNK_FRAMES` is removed as a
module constant (see below).

### `--update-rate` drives chunk size and timer interval

`CHUNK_FRAMES` becomes derived per-instance from `--update-rate` and the
file's sample rate:

```python
self.chunk_frames = max(1, round(sample_rate / args.update_rate))
interval_ms = int(1000 * self.chunk_frames / sample_rate)
```

This replaces the current hardcoded `CHUNK_FRAMES = 1024` module constant.
`on_tick` uses `self.chunk_frames` in place of `CHUNK_FRAMES`.

### Engine construction

```python
self.engine = sound_viz_py.Engine(
    window_size=self.window_size,
    sample_rate=sample_rate,
    update_rate_hz=args.update_rate,
    fft_window_type=args.fft_window,
    band_split_low_hz=args.band_split_low,
    band_split_high_hz=args.band_split_high,
)
```

## 7. Testing

- `engine/tests/dsp_features_test.cpp`: add a Catch2 test case that calls
  `compute_band_energy` with custom split points (e.g. 500 Hz / 2000 Hz) on
  a synthetic spectrum and confirms the result classifies energy into the
  expected band given the *new* split points (distinct from the
  default-split test already present from Phase 1c). Update all existing
  calls to `compute_band_energy` in this file to pass the default
  250.0f/4000.0f split points explicitly (signature changed).
- `engine/tests/window_test.cpp`: add `test_hamming_window_endpoints_and_peak`,
  analogous to the existing Hann test:
  ```cpp
  void test_hamming_window_endpoints_and_peak() {
      float w[5];
      hamming_window(w, 5);
      assert(std::abs(w[0] - 0.08f) < 1e-6f);
      assert(std::abs(w[4] - 0.08f) < 1e-6f);
      assert(std::abs(w[2] - 1.0f) < 1e-6f); // center sample
  }
  ```
- `engine/tests/engine_test.cpp`: update `EngineConfig` initialization to set
  the four new fields to defaults matching current (Phase 1c) behavior
  (`update_rate_hz = 0.0f`, `fft_window_type = WINDOW_HANN`,
  `band_split_low_hz = 250.0f`, `band_split_high_hz = 4000.0f`) so existing
  assertions keep passing unchanged. Add one additional test constructing an
  engine with `WINDOW_HAMMING` and custom band split points (e.g. 500/2000),
  pushing a known signal, and asserting the resulting `FeatureFrame` has
  sane (non-NaN, non-zero where expected) values — confirming the
  alternate-window/custom-split path doesn't crash and produces plausible
  output.
- Manual frontend smoke test: run
  `./frontend/run.sh main.py fixtures/test_tone.wav --fft-window hamming --band-split-low 500 --band-split-high 2000 --update-rate 15`
  against a fixture WAV and confirm it runs without error and meters respond
  at the expected ~15 Hz rate.

## Out of scope (deferred to later phases)

- Engine-side gating of recomputation based on `update_rate_hz` (explicitly
  decided to be advisory-only for 1d).
- Additional FFT window types beyond Hann/Hamming (e.g. Blackman) — can be
  added later by extending `FftWindowType` and the string mapping in the
  Python binding.
- Runtime reconfiguration (changing config on a live `Engine` instance) —
  config is fixed at construction time, as today.
