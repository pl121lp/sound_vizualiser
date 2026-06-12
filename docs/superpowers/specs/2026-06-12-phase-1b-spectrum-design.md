# Phase 1b — Spectrum: Design

Status: approved
Date: 2026-06-12
Parent spec: `project_spec_final.md` (section 5, Phase 1b)

## Goal

Add Hann windowing + FFT to the analysis engine, populate `spectrum` /
`spectrum_len` in `FeatureFrame`, and have the Python frontend render a
spectrum bar plot alongside the existing waveform view.

## Repo layout changes

```
engine/
  third_party/
    pocketfft/
      pocketfft_hdronly.h        # vendored, header-only FFT
  src/
    window.h / window.cpp        # Hann window generation + application
    fft.h / fft.cpp               # real FFT wrapper around pocketfft
    ring_buffer.h/.cpp             # unchanged
    engine.cpp                    # extended: windowing + FFT -> spectrum
  tests/
    engine_test.cpp               # extended with a sine-wave FFT sanity check
frontend/
  main.py                          # adds spectrum bar plot
```

## FFT library

- Vendor `pocketfft_hdronly.h` (single header, header-only C++17 port of
  pocketfft) into `engine/third_party/pocketfft/`. No build system changes
  beyond adding this directory to the include path — keeps the engine
  portable (no Linux-specific APIs) and avoids a network dependency at
  configure time.

## `window.h` / `window.cpp`

```c
namespace sound_viz {

// Fills `out` (size N) with Hann window coefficients.
void hann_window(float* out, size_t n);

// out[i] = in[i] * window[i], for i in [0, n)
void apply_window(const float* in, const float* window, float* out, size_t n);

} // namespace sound_viz
```

- `hann_window` coefficients are precomputed once at engine construction
  (window_size N is fixed for 1b/1c; becomes configurable in 1d without
  changing this module).

## `fft.h` / `fft.cpp`

```c
namespace sound_viz {

// Computes the magnitude spectrum of a real, windowed input of size n
// (N even). Writes n/2+1 magnitude values into `out`.
void real_fft_magnitude(const float* in, size_t n, float* out);

} // namespace sound_viz
```

- Wraps `pocketfft::r2c` for a real-to-complex FFT of size N, then writes
  `sqrt(re^2 + im^2)` for each of the N/2+1 output bins into `out`.

## Engine internals (`engine.cpp`)

`EngineImpl` gains two buffers, sized at construction (N fixed):

```c
std::vector<float> hann_coeffs;     // size N, precomputed in constructor
std::vector<float> windowed_buf;    // size N, scratch for windowed waveform
std::vector<float> spectrum_out;    // size N/2 + 1
```

`get_latest_features`, after copying the waveform snapshot into
`waveform_out`:

1. `apply_window(waveform_out, hann_coeffs, windowed_buf, N)`
2. `real_fft_magnitude(windowed_buf, N, spectrum_out)`
3. Set `frame.spectrum = spectrum_out.data()`, `frame.spectrum_len = N/2 + 1`

Memory ownership follows the existing rule: `spectrum_out` (like
`waveform_out`) is valid until the next `push_samples`/`get_latest_features`
call.

## `feature_frame.h` changes

Update comments only — the struct shape is unchanged from 1a (it was defined
in full up front per the phase 1a design):

```c
const float* spectrum;     // populated in 1b: N/2+1 magnitude bins
uint32_t spectrum_len;     // == window_size/2 + 1
```

## pybind11 binding (`python_bindings.cpp`)

`get_latest_features()` copies `frame.spectrum` into a fresh
`py::array_t<float>` of size `spectrum_len`, same pattern as `waveform`, and
adds `result["spectrum"]` to the returned dict.

## Frontend (`frontend/main.py`)

- Adds a second `pyqtgraph.PlotWidget` below the existing waveform plot,
  shown via a vertical layout (e.g. `QSplitter` or a simple `QVBoxLayout` in
  a container widget set as `centralWidget`).
- Spectrum plot uses a `pg.BarGraphItem` with one bar per bin
  (`spectrum_len == N/2+1 == 513` for N=1024), x = bin index, height =
  magnitude. Linear bin axis; no log-scale grouping or downsampling (deferred
  per the parent spec).
- Each tick: after `get_latest_features()`, update both the waveform curve
  and the spectrum bar heights from `frame["spectrum"]`.
- Y-axis range for the spectrum plot is left auto-scaling (pyqtgraph
  default) since magnitude scale depends on input amplitude and window size.

## CMake changes

- Add `engine/third_party/pocketfft` to `sound_viz_engine`'s include
  directories (private — only `fft.cpp` needs it).
- Add `src/window.cpp` and `src/fft.cpp` to the `sound_viz_engine` library
  sources.

## Testing

- Extend `engine_test.cpp`: push a pure sine wave at a known frequency
  (e.g. 1kHz at 44.1kHz sample rate, N=1024), call `get_latest_features`, and
  assert:
  - `spectrum_len == N/2 + 1`
  - `spectrum` is non-null
  - the magnitude peak bin index is close to the expected bin
    (`round(freq * N / sample_rate)`)
- Full rigorous DSP validation against known signals (RMS, centroid, etc.,
  possibly with Catch2/GoogleTest) remains deferred to 1c per the parent
  spec; this is a lightweight sanity check enabled by introducing the FFT
  now.

## Out of scope for 1b (deferred to later phases)

- RMS, zero-crossing rate, peak, band energy, spectral centroid (1c)
- Catch2/GoogleTest test framework adoption (1c)
- Configurable window size / update rate / FFT window type / band splits
  (1d)
- Log-scale grouping/downsampling of spectrum bins for display (optional,
  not committed to any phase)
