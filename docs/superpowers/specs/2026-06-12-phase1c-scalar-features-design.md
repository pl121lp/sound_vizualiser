# Phase 1c — Scalar Features: Design

## Goal

Per `project_spec_final.md` Phase 1c, populate the remaining scalar fields of
`FeatureFrame` (RMS, zero-crossing rate, peak amplitude, band energy
low/mid/high, spectral centroid), display them in the frontend as numeric
readouts/bars, drive a VU/peak meter with peak-hold from `peak`, and add C++
unit tests validating the new DSP functions against known signals.

## 1. Engine: new `features.h` / `features.cpp` module

A new pure-DSP module alongside `window.h`/`fft.h` — free functions, no
engine state, independently testable.

```cpp
// engine/src/features.h
#pragma once
#include <cstddef>
#include <cstdint>

namespace sound_viz {

float compute_rms(const float* samples, size_t n);
float compute_zero_crossing_rate(const float* samples, size_t n);
float compute_peak(const float* samples, size_t n);

struct BandEnergy {
    float low;
    float mid;
    float high;
};

// spectrum: magnitude bins, spectrum_len == window_size/2 + 1.
// Band split points are hardcoded at 250 Hz and 4000 Hz for 1c
// (becomes configurable via EngineConfig in 1d).
BandEnergy compute_band_energy(const float* spectrum, size_t spectrum_len,
                                uint32_t sample_rate, uint32_t window_size);

float compute_spectral_centroid(const float* spectrum, size_t spectrum_len,
                                  uint32_t sample_rate, uint32_t window_size);

} // namespace sound_viz
```

- `compute_rms`, `compute_zero_crossing_rate`, `compute_peak` operate on the
  **unwindowed** latest-N waveform snapshot (the same buffer exposed as
  `frame.waveform`), since these are time-domain readouts of that window.
- `compute_band_energy` and `compute_spectral_centroid` operate on
  `spectrum_out` (Hann-windowed + FFT magnitude). Bin index `i` maps to
  frequency `i * sample_rate / window_size`.
- Band split constants (250 Hz, 4000 Hz) live as named constants in
  `features.cpp`. Phase 1d will thread them through `EngineConfig`.

### Spectral centroid edge case

If total spectral energy is zero (e.g. silence), `compute_spectral_centroid`
returns `0.0f` rather than `0/0`.

## 2. Wiring into `engine.cpp`

In `get_latest_features`, after the existing window+FFT step, compute the
five new values from `waveform_out` and `spectrum_out` and populate:

- `frame.rms`
- `frame.zero_crossing_rate`
- `frame.peak`
- `frame.band_energy_low` / `band_energy_mid` / `band_energy_high`
- `frame.spectral_centroid`

No changes to the `FeatureFrame` struct (fields already exist, declared "0 in
1a/1b, added in 1c") or to `bindings/python_bindings.cpp` (already copies
these fields into the returned `py::dict`).

## 3. Catch2 + new test target

- Add Catch2 v3 via CMake `FetchContent` (`Catch2::Catch2WithMain`), fetched
  only for the test build.
- New `engine/tests/dsp_features_test.cpp` using Catch2 `TEST_CASE`/`REQUIRE`:
  - **RMS**: known sine of amplitude `A` over a whole number of periods →
    RMS ≈ `A / sqrt(2)`.
  - **Peak**: array with a known max-abs value → exact match.
  - **Zero-crossing rate**: a signal with a known, exact number of sign
    changes → ZCR matches `crossings / (n - 1)`.
  - **Spectral centroid**: pure sine at frequency `f` (with Hann window
    applied, matching how the engine computes it) → centroid within one bin
    width of `f`.
  - **Band energy**: pure sine in the "mid" band (e.g. 1000 Hz) → `mid` energy
    is strictly greater than `low` and `high`.
- Existing tests (`ring_buffer_test`, `window_test`, `fft_test`,
  `engine_test`) remain on the existing hand-rolled assert+printf pattern —
  unchanged. Only the new DSP feature tests use Catch2.
- `CMakeLists.txt`: add `features.cpp` to the `sound_viz_engine` library
  sources, add the `FetchContent` block for Catch2, and register the new
  `dsp_features_test` executable/test.

## 4. Frontend: feature panel

Add a row of compact meters below the existing waveform/spectrum plots in
`main.py`.

### `BarMeter` widget

Small reusable class: a `pg.PlotWidget` containing one horizontal
`BarGraphItem`, with a `QLabel` above/beside it showing the live numeric
value. Constructor takes a title, a units formatter, and either a fixed
x-range or "auto-scale" mode.

- **RMS**, **Zero-crossing rate**: fixed range `[0, 1]`.
- **Peak**: fixed range `[0, 1]`, with the standard VU peak-hold behavior:
  - `self.peak_hold_value` tracks the current hold level.
  - On each tick: if `frame["peak"] > peak_hold_value`, snap
    `peak_hold_value = frame["peak"]` and reset a hold timer.
  - Otherwise, once the hold timer exceeds ~1 second, decay
    `peak_hold_value` toward `frame["peak"]` at a fixed rate (e.g. 1.0/sec).
  - The hold level is drawn as a vertical `pg.InfiniteLine` marker on top of
    the peak `BarMeter`.
- **Band energy low/mid/high**, **Spectral centroid**: "auto-scale" mode — the
  meter tracks a slowly-decaying running max of observed values and uses
  `1.2 * running_max` as the bar's x-axis range, so bars stay meaningfully
  scaled without per-frame jitter. Centroid's numeric label is formatted in Hz.

### Layout

A horizontal row of 7 `BarMeter`s (RMS, ZCR, Peak, Band Low, Band Mid, Band
High, Spectral Centroid) added to the existing `QVBoxLayout`, below the
spectrum plot.

## Out of scope (deferred to later phases)

- Configurable band split points / window size / update rate (Phase 1d).
- Smoothing/EMA on these values (Phase 3d).
- Onset/beat detection using successive `band_energy_*`/`spectrum` values
  (Phase 2f).
