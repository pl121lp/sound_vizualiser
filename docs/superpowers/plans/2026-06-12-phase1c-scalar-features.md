# Phase 1c — Scalar Features Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Populate `FeatureFrame`'s scalar fields (RMS, zero-crossing rate, peak, band energy low/mid/high, spectral centroid), cover the new DSP functions with Catch2 unit tests, and display the values in the frontend with a VU/peak meter (peak-hold) and bar meters.

**Architecture:** A new `engine/src/features.{h,cpp}` module holds pure DSP functions (no engine state). `engine.cpp` calls them in `get_latest_features` to populate the existing-but-unused `FeatureFrame` fields. The Python binding already passes these fields through unchanged. The frontend gets a row of `BarMeter` widgets (new reusable class in `main.py`) plus peak-hold logic driven from `frame["peak"]`.

**Tech Stack:** C++17, CMake, Catch2 v3 (system package `libcatch2-dev`, found via `find_package`), pocketfft (existing), Python/pyqtgraph (existing).

---

## Task 1: `features.h`/`features.cpp` — RMS, peak, zero-crossing rate

**Files:**
- Create: `engine/src/features.h`
- Create: `engine/src/features.cpp`
- Create: `engine/tests/dsp_features_test.cpp`
- Modify: `engine/CMakeLists.txt`

- [ ] **Step 1: Create `engine/src/features.h`**

```cpp
#pragma once

#include <cstddef>
#include <cstdint>

namespace sound_viz {

// Root-mean-square of `samples[0..n)`.
float compute_rms(const float* samples, size_t n);

// Fraction of adjacent-sample sign changes in `samples[0..n)`, in [0, 1].
// Returns 0 for n < 2.
float compute_zero_crossing_rate(const float* samples, size_t n);

// Maximum absolute value in `samples[0..n)`. Returns 0 for n == 0.
float compute_peak(const float* samples, size_t n);

struct BandEnergy {
    float low;
    float mid;
    float high;
};

// Sums squared magnitudes from `spectrum` (spectrum_len == window_size/2 + 1)
// into low/mid/high bands, split at 250 Hz and 4000 Hz. Bin i corresponds to
// frequency i * sample_rate / window_size.
BandEnergy compute_band_energy(const float* spectrum, size_t spectrum_len,
                                uint32_t sample_rate, uint32_t window_size);

// Magnitude-weighted mean frequency of `spectrum`. Returns 0 if the spectrum
// has zero total energy.
float compute_spectral_centroid(const float* spectrum, size_t spectrum_len,
                                  uint32_t sample_rate, uint32_t window_size);

} // namespace sound_viz
```

- [ ] **Step 2: Create `engine/src/features.cpp`**

```cpp
#include "features.h"

#include <cmath>

namespace sound_viz {

namespace {
constexpr float kBandLowMidHz = 250.0f;
constexpr float kBandMidHighHz = 4000.0f;
}

float compute_rms(const float* samples, size_t n) {
    if (n == 0) {
        return 0.0f;
    }
    double sum_sq = 0.0;
    for (size_t i = 0; i < n; ++i) {
        double s = static_cast<double>(samples[i]);
        sum_sq += s * s;
    }
    return static_cast<float>(std::sqrt(sum_sq / static_cast<double>(n)));
}

float compute_zero_crossing_rate(const float* samples, size_t n) {
    if (n < 2) {
        return 0.0f;
    }
    size_t crossings = 0;
    for (size_t i = 1; i < n; ++i) {
        bool prev_neg = samples[i - 1] < 0.0f;
        bool curr_neg = samples[i] < 0.0f;
        if (prev_neg != curr_neg) {
            ++crossings;
        }
    }
    return static_cast<float>(crossings) / static_cast<float>(n - 1);
}

float compute_peak(const float* samples, size_t n) {
    float peak = 0.0f;
    for (size_t i = 0; i < n; ++i) {
        float a = std::fabs(samples[i]);
        if (a > peak) {
            peak = a;
        }
    }
    return peak;
}

BandEnergy compute_band_energy(const float* spectrum, size_t spectrum_len,
                                uint32_t sample_rate, uint32_t window_size) {
    BandEnergy result{0.0f, 0.0f, 0.0f};
    for (size_t i = 0; i < spectrum_len; ++i) {
        float freq = static_cast<float>(i) * static_cast<float>(sample_rate) /
                      static_cast<float>(window_size);
        float energy = spectrum[i] * spectrum[i];
        if (freq < kBandLowMidHz) {
            result.low += energy;
        } else if (freq < kBandMidHighHz) {
            result.mid += energy;
        } else {
            result.high += energy;
        }
    }
    return result;
}

float compute_spectral_centroid(const float* spectrum, size_t spectrum_len,
                                  uint32_t sample_rate, uint32_t window_size) {
    double weighted_sum = 0.0;
    double total = 0.0;
    for (size_t i = 0; i < spectrum_len; ++i) {
        float freq = static_cast<float>(i) * static_cast<float>(sample_rate) /
                      static_cast<float>(window_size);
        double mag = static_cast<double>(spectrum[i]);
        weighted_sum += freq * mag;
        total += mag;
    }
    if (total <= 0.0) {
        return 0.0f;
    }
    return static_cast<float>(weighted_sum / total);
}

} // namespace sound_viz
```

- [ ] **Step 3: Create `engine/tests/dsp_features_test.cpp`**

```cpp
#include <catch2/catch_approx.hpp>
#include <catch2/catch_test_macros.hpp>

#include "fft.h"
#include "features.h"
#include "window.h"

#include <cmath>
#include <vector>

using namespace sound_viz;
using Catch::Approx;

namespace {

// Generates a Hann-windowed pure sine and its magnitude spectrum.
std::vector<float> sine_spectrum(double freq, double sample_rate, size_t n) {
    const double pi = 3.14159265358979323846;

    std::vector<float> signal(n);
    for (size_t i = 0; i < n; ++i) {
        signal[i] = static_cast<float>(std::sin(2.0 * pi * freq * static_cast<double>(i) / sample_rate));
    }

    std::vector<float> window(n);
    hann_window(window.data(), n);

    std::vector<float> windowed(n);
    apply_window(signal.data(), window.data(), windowed.data(), n);

    std::vector<float> spectrum(n / 2 + 1);
    real_fft_magnitude(windowed.data(), n, spectrum.data());
    return spectrum;
}

} // namespace

TEST_CASE("compute_rms of an alternating +-1 signal is 1.0", "[features]") {
    float samples[] = {1.0f, -1.0f, 1.0f, -1.0f};
    REQUIRE(compute_rms(samples, 4) == Approx(1.0f));
}

TEST_CASE("compute_rms of silence is 0", "[features]") {
    float samples[] = {0.0f, 0.0f, 0.0f};
    REQUIRE(compute_rms(samples, 3) == Approx(0.0f));
}

TEST_CASE("compute_peak finds the maximum absolute value", "[features]") {
    float samples[] = {0.2f, -0.9f, 0.5f};
    REQUIRE(compute_peak(samples, 3) == Approx(0.9f));
}

TEST_CASE("compute_zero_crossing_rate counts sign changes", "[features]") {
    float samples[] = {1.0f, -1.0f, 1.0f, -1.0f, 1.0f};
    REQUIRE(compute_zero_crossing_rate(samples, 5) == Approx(1.0f));
}

TEST_CASE("compute_zero_crossing_rate of a constant signal is 0", "[features]") {
    float samples[] = {1.0f, 1.0f, 1.0f, 1.0f};
    REQUIRE(compute_zero_crossing_rate(samples, 4) == Approx(0.0f));
}

TEST_CASE("compute_spectral_centroid matches a pure tone's frequency", "[features]") {
    const size_t n = 1024;
    const double sample_rate = 44100.0;
    const double freq = 1000.0;

    std::vector<float> spectrum = sine_spectrum(freq, sample_rate, n);

    float centroid = compute_spectral_centroid(spectrum.data(), spectrum.size(),
                                                 static_cast<uint32_t>(sample_rate),
                                                 static_cast<uint32_t>(n));
    REQUIRE(centroid == Approx(static_cast<float>(freq)).margin(100.0f));
}

TEST_CASE("compute_spectral_centroid of silence is 0", "[features]") {
    const size_t spectrum_len = 513;
    std::vector<float> spectrum(spectrum_len, 0.0f);

    float centroid = compute_spectral_centroid(spectrum.data(), spectrum.size(), 44100, 1024);
    REQUIRE(centroid == Approx(0.0f));
}

TEST_CASE("compute_band_energy puts a 1kHz tone in the mid band", "[features]") {
    const size_t n = 1024;
    const double sample_rate = 44100.0;
    const double freq = 1000.0;

    std::vector<float> spectrum = sine_spectrum(freq, sample_rate, n);

    BandEnergy energy = compute_band_energy(spectrum.data(), spectrum.size(),
                                             static_cast<uint32_t>(sample_rate),
                                             static_cast<uint32_t>(n));
    REQUIRE(energy.mid > energy.low);
    REQUIRE(energy.mid > energy.high);
}

TEST_CASE("compute_band_energy puts a 100Hz tone in the low band", "[features]") {
    const size_t n = 1024;
    const double sample_rate = 44100.0;
    const double freq = 100.0;

    std::vector<float> spectrum = sine_spectrum(freq, sample_rate, n);

    BandEnergy energy = compute_band_energy(spectrum.data(), spectrum.size(),
                                             static_cast<uint32_t>(sample_rate),
                                             static_cast<uint32_t>(n));
    REQUIRE(energy.low > energy.mid);
    REQUIRE(energy.low > energy.high);
}
```

- [ ] **Step 4: Update `engine/CMakeLists.txt`**

Add `features.cpp` to the library sources, find Catch2, and register the new test:

```cmake
add_library(sound_viz_engine STATIC
    src/ring_buffer.cpp
    src/window.cpp
    src/fft.cpp
    src/features.cpp
    src/engine.cpp
)
```

After the existing `add_test(NAME engine_test ...)` block, add:

```cmake
find_package(Catch2 3 REQUIRED)

add_executable(dsp_features_test tests/dsp_features_test.cpp)
target_include_directories(dsp_features_test PRIVATE src)
target_link_libraries(dsp_features_test PRIVATE sound_viz_engine Catch2::Catch2WithMain)
add_test(NAME dsp_features_test COMMAND dsp_features_test)
```

- [ ] **Step 5: Build and run the new tests**

Run: `./engine/build.sh`

Expected: build succeeds, and `ctest` output includes a passing `dsp_features_test` (all 8 Catch2 assertions pass) alongside the existing tests.

- [ ] **Step 6: Commit**

```bash
git add engine/src/features.h engine/src/features.cpp engine/tests/dsp_features_test.cpp engine/CMakeLists.txt
git commit -m "Add DSP feature functions (RMS, ZCR, peak, band energy, centroid) with Catch2 tests"
```

---

## Task 2: Wire features into `engine.cpp` and `engine_test.cpp`

**Files:**
- Modify: `engine/src/engine.cpp`
- Modify: `engine/tests/engine_test.cpp`

- [ ] **Step 1: Update `engine/src/engine.cpp`**

Add the include at the top:

```cpp
#include "sound_viz/engine.h"
#include "ring_buffer.h"
#include "window.h"
#include "fft.h"
#include "features.h"

#include <vector>
```

In `get_latest_features`, after the existing FFT call and before `FeatureFrame frame{};`, no change needed there — instead, after `frame.spectrum_len = ...;` and before `return frame;`, add:

```cpp
    frame.rms = sound_viz::compute_rms(impl->waveform_out.data(), impl->waveform_out.size());
    frame.zero_crossing_rate = sound_viz::compute_zero_crossing_rate(
        impl->waveform_out.data(), impl->waveform_out.size());
    frame.peak = sound_viz::compute_peak(impl->waveform_out.data(), impl->waveform_out.size());

    sound_viz::BandEnergy band_energy = sound_viz::compute_band_energy(
        impl->spectrum_out.data(), impl->spectrum_out.size(),
        impl->config.sample_rate, impl->config.window_size);
    frame.band_energy_low = band_energy.low;
    frame.band_energy_mid = band_energy.mid;
    frame.band_energy_high = band_energy.high;

    frame.spectral_centroid = sound_viz::compute_spectral_centroid(
        impl->spectrum_out.data(), impl->spectrum_out.size(),
        impl->config.sample_rate, impl->config.window_size);
```

The full `get_latest_features` function should now read:

```cpp
FeatureFrame get_latest_features(EngineHandle engine) {
    EngineImpl* impl = engine;
    impl->ring_buffer.copy_latest(impl->waveform_out.data());

    sound_viz::apply_window(impl->waveform_out.data(), impl->hann_coeffs.data(),
                             impl->windowed_buf.data(), impl->windowed_buf.size());
    sound_viz::real_fft_magnitude(impl->windowed_buf.data(), impl->windowed_buf.size(),
                                   impl->spectrum_out.data());

    FeatureFrame frame{};
    frame.frame_index = impl->frame_counter++;
    frame.sample_rate = impl->config.sample_rate;
    frame.channels = impl->last_channels;
    frame.waveform = impl->waveform_out.data();
    frame.waveform_len = static_cast<uint32_t>(impl->waveform_out.size());
    frame.spectrum = impl->spectrum_out.data();
    frame.spectrum_len = static_cast<uint32_t>(impl->spectrum_out.size());

    frame.rms = sound_viz::compute_rms(impl->waveform_out.data(), impl->waveform_out.size());
    frame.zero_crossing_rate = sound_viz::compute_zero_crossing_rate(
        impl->waveform_out.data(), impl->waveform_out.size());
    frame.peak = sound_viz::compute_peak(impl->waveform_out.data(), impl->waveform_out.size());

    sound_viz::BandEnergy band_energy = sound_viz::compute_band_energy(
        impl->spectrum_out.data(), impl->spectrum_out.size(),
        impl->config.sample_rate, impl->config.window_size);
    frame.band_energy_low = band_energy.low;
    frame.band_energy_mid = band_energy.mid;
    frame.band_energy_high = band_energy.high;

    frame.spectral_centroid = sound_viz::compute_spectral_centroid(
        impl->spectrum_out.data(), impl->spectrum_out.size(),
        impl->config.sample_rate, impl->config.window_size);

    return frame;
}
```

- [ ] **Step 2: Update `engine/tests/engine_test.cpp`**

The existing assertion `assert(frame1.rms == 0.0f);` is now wrong: with `window_size = 4`, after pushing `{1.0f, 2.0f}` the waveform is `{0, 0, 1, 2}` (zero-padded front), so
`rms == sqrt((0^2 + 0^2 + 1^2 + 2^2) / 4) == sqrt(1.25)`.

Add `#include <cmath>` to the top of the file:

```cpp
#include "sound_viz/engine.h"

#include <cassert>
#include <cmath>
#include <cstdio>
```

Replace:

```cpp
    assert(frame1.rms == 0.0f);
    assert(frame1.frame_index == 0);
```

with:

```cpp
    assert(std::abs(frame1.rms - std::sqrt(1.25f)) < 1e-5f);
    assert(frame1.peak == 2.0f);
    assert(frame1.zero_crossing_rate == 0.0f);
    assert(frame1.frame_index == 0);
```

(The waveform `{0, 0, 1, 2}` has no sign changes between adjacent samples, since `0 < 0.0f` is false, so ZCR is 0; the peak is `2.0`.)

- [ ] **Step 3: Build and run all tests**

Run: `./engine/build.sh`

Expected: build succeeds, `ctest` shows all tests passing, including `engine_test` and `dsp_features_test`.

- [ ] **Step 4: Commit**

```bash
git add engine/src/engine.cpp engine/tests/engine_test.cpp
git commit -m "Compute RMS, ZCR, peak, band energy, and spectral centroid in get_latest_features"
```

---

## Task 3: Frontend — `BarMeter` widget and feature panel

**Files:**
- Modify: `frontend/main.py`

- [ ] **Step 1: Add the `BarMeter` class**

Insert this class above `WaveformWindow` in `frontend/main.py` (after the existing imports/constants):

```python
class BarMeter(QtWidgets.QWidget):
    """A horizontal bar gauge with a title label and a live numeric readout."""

    def __init__(self, title, value_format, x_range=(0.0, 1.0), auto_scale=False):
        super().__init__()
        self.value_format = value_format
        self.auto_scale = auto_scale
        self.running_max = 1e-6

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        self.label = QtWidgets.QLabel(f"{title}: {value_format.format(0.0)}")
        layout.addWidget(self.label)

        self.plot = pg.PlotWidget()
        self.plot.setMaximumHeight(40)
        self.plot.hideAxis("left")
        self.plot.hideAxis("bottom")
        self.plot.setMouseEnabled(x=False, y=False)
        self.plot.setYRange(-0.5, 0.5, padding=0)
        self.plot.setXRange(*x_range, padding=0)

        self.bar = pg.BarGraphItem(x0=[0.0], x1=[0.0], y0=[-0.3], y1=[0.3], brush="c")
        self.plot.addItem(self.bar)

        self.title = title
        layout.addWidget(self.plot)

    def update_value(self, value):
        if self.auto_scale:
            self.running_max = max(self.running_max * 0.98, value)
            upper = max(self.running_max * 1.2, 1e-6)
            self.plot.setXRange(0.0, upper, padding=0)

        self.bar.setOpts(x0=[0.0], x1=[value])
        self.label.setText(f"{self.title}: {self.value_format.format(value)}")
```

- [ ] **Step 2: Create the feature meters in `WaveformWindow.__init__`**

After the existing `self.spectrum_plot.addItem(self.spectrum_bars)` line, add:

```python
        self.rms_meter = BarMeter("RMS", "{:.3f}", x_range=(0.0, 1.0))
        self.zcr_meter = BarMeter("Zero-crossing rate", "{:.3f}", x_range=(0.0, 1.0))
        self.peak_meter = BarMeter("Peak", "{:.3f}", x_range=(0.0, 1.0))
        self.band_low_meter = BarMeter("Band energy (low)", "{:.2f}", auto_scale=True)
        self.band_mid_meter = BarMeter("Band energy (mid)", "{:.2f}", auto_scale=True)
        self.band_high_meter = BarMeter("Band energy (high)", "{:.2f}", auto_scale=True)
        self.centroid_meter = BarMeter("Spectral centroid (Hz)", "{:.0f}", auto_scale=True)

        self.peak_hold_line = pg.InfiniteLine(pos=0.0, angle=90, pen=pg.mkPen("r", width=2))
        self.peak_meter.plot.addItem(self.peak_hold_line)
        self.peak_hold_value = 0.0
        self.peak_hold_timer = 0.0
```

- [ ] **Step 3: Add the feature meters to the layout**

Replace:

```python
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        layout.addWidget(self.waveform_plot)
        layout.addWidget(self.spectrum_plot)
        self.setCentralWidget(container)
```

with:

```python
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        layout.addWidget(self.waveform_plot)
        layout.addWidget(self.spectrum_plot)

        meters_layout = QtWidgets.QHBoxLayout()
        for meter in (
            self.rms_meter,
            self.zcr_meter,
            self.peak_meter,
            self.band_low_meter,
            self.band_mid_meter,
            self.band_high_meter,
            self.centroid_meter,
        ):
            meters_layout.addWidget(meter)
        layout.addLayout(meters_layout)

        self.setCentralWidget(container)
```

- [ ] **Step 4: Manual check that the layout renders**

Run: `./frontend/run.sh main.py fixtures/test_tone.wav` (or whichever WAV fixture exists under `frontend/fixtures/`)

Expected: window opens showing waveform plot, spectrum bars, and a row of 7 meters below — values won't update meaningfully yet (next task wires `on_tick`), but the widgets should render without errors. Close the window to exit.

- [ ] **Step 5: Commit**

```bash
git add frontend/main.py
git commit -m "Add BarMeter widget and scalar-feature meter row to frontend"
```

---

## Task 4: Frontend — wire `on_tick` to update meters and peak-hold

**Files:**
- Modify: `frontend/main.py`

- [ ] **Step 1: Store the tick interval for peak-hold timing**

In `__init__`, where `interval_ms` is computed, store it on `self`:

```python
        interval_ms = int(1000 * CHUNK_FRAMES / sample_rate)
        self.tick_interval_s = interval_ms / 1000.0
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.on_tick)
        self.timer.start(interval_ms)
```

- [ ] **Step 2: Update `on_tick` to refresh the meters**

Add near the top of the file, alongside the other module-level constants:

```python
PEAK_HOLD_SECONDS = 1.0
PEAK_DECAY_PER_SECOND = 1.0
```

Replace the body of `on_tick` from `frame = self.engine.get_latest_features()` onward:

```python
        frame = self.engine.get_latest_features()
        self.curve.setData(frame["waveform"])
        self.spectrum_bars.setOpts(height=frame["spectrum"])

        self.rms_meter.update_value(float(frame["rms"]))
        self.zcr_meter.update_value(float(frame["zero_crossing_rate"]))
        self.band_low_meter.update_value(float(frame["band_energy_low"]))
        self.band_mid_meter.update_value(float(frame["band_energy_mid"]))
        self.band_high_meter.update_value(float(frame["band_energy_high"]))
        self.centroid_meter.update_value(float(frame["spectral_centroid"]))

        peak = float(frame["peak"])
        self.peak_meter.update_value(peak)
        if peak >= self.peak_hold_value:
            self.peak_hold_value = peak
            self.peak_hold_timer = 0.0
        else:
            self.peak_hold_timer += self.tick_interval_s
            if self.peak_hold_timer > PEAK_HOLD_SECONDS:
                self.peak_hold_value = max(
                    peak, self.peak_hold_value - PEAK_DECAY_PER_SECOND * self.tick_interval_s
                )
        self.peak_hold_line.setValue(self.peak_hold_value)
```

- [ ] **Step 3: Manual run against a real WAV file**

Run: `./frontend/run.sh main.py fixtures/test_tone.wav`

Expected: the waveform and spectrum update as before; RMS/ZCR/Peak bars move with the audio (peak bar reflects current amplitude, red peak-hold line jumps to peaks and decays after ~1s); band-energy and centroid bars rescale smoothly. Close the window to exit.

- [ ] **Step 4: Update the window title to reflect Phase 1c**

Replace:

```python
    window.setWindowTitle("Sound Visualizer - Waveform + Spectrum (Phase 1b)")
```

with:

```python
    window.setWindowTitle("Sound Visualizer - Waveform + Spectrum + Features (Phase 1c)")
```

- [ ] **Step 5: Commit**

```bash
git add frontend/main.py
git commit -m "Drive scalar-feature meters and peak-hold from engine FeatureFrame"
```

---

## Task 5: Final full-suite verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full engine build + test suite**

Run: `./engine/build.sh`

Expected: all tests pass — `ring_buffer_test`, `window_test`, `fft_test`, `engine_test`, `dsp_features_test`.

- [ ] **Step 2: Run the frontend smoke test**

Run: `./frontend/run.sh scripts/smoke_test_harness.py` (check the script's existing CLI usage first — pass whatever WAV path it expects)

Expected: runs without errors and reports the new scalar fields are non-zero for non-silent audio (if the smoke test prints `FeatureFrame` fields; otherwise just confirm it runs cleanly with the new engine binary).

- [ ] **Step 3: Manual end-to-end run**

Run: `./frontend/run.sh main.py fixtures/test_tone.wav`

Expected: full UI (waveform, spectrum, 7 feature meters) renders and updates live; no exceptions in the terminal.
