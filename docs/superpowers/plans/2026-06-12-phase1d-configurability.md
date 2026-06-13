# Phase 1d Configurability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose analysis window size, update rate, FFT window type (Hann/Hamming), and frequency band split points through `EngineConfig`, the Python bindings, and the frontend CLI, per `project_spec_final.md` Phase 1d.

**Architecture:** Add four new fields (`update_rate_hz`, `fft_window_type`, `band_split_low_hz`, `band_split_high_hz`) plus a new `FftWindowType` enum to the `EngineConfig` C struct. Thread `fft_window_type` through engine construction (selects Hann vs. Hamming window coefficients) and `band_split_low_hz`/`band_split_high_hz` through `compute_band_energy`. Extend the pybind11 `Engine` constructor with matching keyword args (window type as a string). Add corresponding `argparse` flags in `frontend/main.py`, with `--update-rate` driving the per-instance chunk size / timer interval.

**Tech Stack:** C++17, CMake, Catch2 v3 (new dsp_features tests) + hand-rolled assert/printf (window/engine tests), pybind11, Python/PyQt5/pyqtgraph.

---

### Task 1: `EngineConfig` struct — new enum and fields

**Files:**
- Modify: `engine/include/sound_viz/feature_frame.h`

- [ ] **Step 1: Add `FftWindowType` enum and new `EngineConfig` fields**

Replace the current `EngineConfig` typedef:

```cpp
typedef struct {
    uint32_t window_size;   // N, e.g. 1024 — size of the analysis window
    uint32_t sample_rate;   // from WAV header; echoed back in FeatureFrame
} EngineConfig;
```

with:

```cpp
typedef enum {
    WINDOW_HANN = 0,
    WINDOW_HAMMING = 1,
} FftWindowType;

typedef struct {
    uint32_t window_size;       // N, e.g. 1024 — size of the analysis window
    uint32_t sample_rate;       // from WAV header; echoed back in FeatureFrame
    float update_rate_hz;       // advisory; echoed back, not used by the engine
    FftWindowType fft_window_type; // Hann or Hamming window applied before FFT
    float band_split_low_hz;    // low/mid band energy split point (Hz)
    float band_split_high_hz;   // mid/high band energy split point (Hz)
} EngineConfig;
```

This struct is declared inside `extern "C" { ... }` in the existing file —
keep the new enum and struct inside that same block, placed before
`EngineConfig` (C requires the enum to be declared before it's used as a
field type, and `typedef enum { ... } FftWindowType;` followed by
`typedef struct { ... FftWindowType fft_window_type; ... } EngineConfig;`
satisfies that).

- [ ] **Step 2: Build to confirm the header still compiles**

Run: `./engine/build.sh`
Expected: build succeeds (nothing references the new fields yet, so no
other errors). Test binaries that construct `EngineConfig{}` still
zero-initialize the new fields to `0` / `WINDOW_HANN` / `0.0f`, so existing
tests still pass at this point.

- [ ] **Step 3: Commit**

```bash
git add engine/include/sound_viz/feature_frame.h
git commit -m "Add FftWindowType enum and configurability fields to EngineConfig"
```

---

### Task 2: Hamming window function

**Files:**
- Modify: `engine/src/window.h`
- Modify: `engine/src/window.cpp`
- Modify: `engine/tests/window_test.cpp`

- [ ] **Step 1: Write the failing test**

In `engine/tests/window_test.cpp`, add a new test function after
`test_hann_window_endpoints_and_peak`:

```cpp
void test_hamming_window_endpoints_and_peak() {
    float w[5];
    hamming_window(w, 5);
    assert(std::abs(w[0] - 0.08f) < 1e-6f);
    assert(std::abs(w[4] - 0.08f) < 1e-6f);
    assert(std::abs(w[2] - 1.0f) < 1e-6f); // center sample
}
```

And call it from `main()`:

```cpp
int main() {
    test_hann_window_endpoints_and_peak();
    test_hamming_window_endpoints_and_peak();
    test_apply_window();
    printf("window_test: all tests passed\n");
    return 0;
}
```

- [ ] **Step 2: Run the test to verify it fails (compile error)**

Run: `./engine/build.sh`
Expected: build fails with an error that `hamming_window` is not declared
(used in `window_test.cpp` but not yet declared in `window.h`).

- [ ] **Step 3: Declare `hamming_window` in `window.h`**

In `engine/src/window.h`, add the declaration after `hann_window`:

```cpp
#pragma once

#include <cstddef>

namespace sound_viz {

// Fills `out` (size n) with Hann window coefficients.
void hann_window(float* out, size_t n);

// Fills `out` (size n) with Hamming window coefficients.
void hamming_window(float* out, size_t n);

// out[i] = in[i] * window[i], for i in [0, n)
void apply_window(const float* in, const float* window, float* out, size_t n);

} // namespace sound_viz
```

- [ ] **Step 4: Implement `hamming_window` in `window.cpp`**

In `engine/src/window.cpp`, add the implementation after `hann_window`:

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

- [ ] **Step 5: Run the test to verify it passes**

Run: `./engine/build.sh`
Expected: build succeeds and `window_test` prints
`window_test: all tests passed`. Verify in the ctest summary that all tests
still report 100% pass.

- [ ] **Step 6: Commit**

```bash
git add engine/src/window.h engine/src/window.cpp engine/tests/window_test.cpp
git commit -m "Add Hamming window function alongside Hann"
```

---

### Task 3: Configurable band split points in `dsp_features`

**Files:**
- Modify: `engine/src/dsp_features.h`
- Modify: `engine/src/dsp_features.cpp`
- Modify: `engine/tests/dsp_features_test.cpp`

- [ ] **Step 1: Update existing `compute_band_energy` calls and add a new test for custom split points**

In `engine/tests/dsp_features_test.cpp`, update the two existing
`compute_band_energy` calls to pass the current default split points
explicitly (250.0f / 4000.0f), since the signature is about to change.

Change:

```cpp
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

to:

```cpp
    BandEnergy energy = compute_band_energy(spectrum.data(), spectrum.size(),
                                             static_cast<uint32_t>(sample_rate),
                                             static_cast<uint32_t>(n), 250.0f, 4000.0f);
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
                                             static_cast<uint32_t>(n), 250.0f, 4000.0f);
    REQUIRE(energy.low > energy.mid);
    REQUIRE(energy.low > energy.high);
}

TEST_CASE("compute_band_energy respects custom split points", "[features]") {
    const size_t n = 1024;
    const double sample_rate = 44100.0;
    const double freq = 1000.0;

    std::vector<float> spectrum = sine_spectrum(freq, sample_rate, n);

    // With the default 250/4000 Hz split, 1 kHz falls in "mid". With a
    // 2000 Hz low/mid split, 1 kHz now falls in "low".
    BandEnergy energy = compute_band_energy(spectrum.data(), spectrum.size(),
                                             static_cast<uint32_t>(sample_rate),
                                             static_cast<uint32_t>(n), 2000.0f, 8000.0f);
    REQUIRE(energy.low > energy.mid);
    REQUIRE(energy.low > energy.high);
}
```

- [ ] **Step 2: Run the test to verify it fails (compile error)**

Run: `./engine/build.sh`
Expected: build fails — `compute_band_energy` is called with 6 arguments
but declared with 4.

- [ ] **Step 3: Update `compute_band_energy` declaration in `dsp_features.h`**

In `engine/src/dsp_features.h`, replace:

```cpp
// Sums squared magnitudes from `spectrum` (spectrum_len == window_size/2 + 1)
// into low/mid/high bands, split at 250 Hz and 4000 Hz. Bin i corresponds to
// frequency i * sample_rate / window_size.
BandEnergy compute_band_energy(const float* spectrum, size_t spectrum_len,
                                uint32_t sample_rate, uint32_t window_size);
```

with:

```cpp
// Sums squared magnitudes from `spectrum` (spectrum_len == window_size/2 + 1)
// into low/mid/high bands, split at `low_split_hz` and `high_split_hz`.
// Bin i corresponds to frequency i * sample_rate / window_size.
BandEnergy compute_band_energy(const float* spectrum, size_t spectrum_len,
                                uint32_t sample_rate, uint32_t window_size,
                                float low_split_hz, float high_split_hz);
```

- [ ] **Step 4: Update `compute_band_energy` implementation in `dsp_features.cpp`**

Remove the now-unused constants and update the function. Replace:

```cpp
namespace {
constexpr float kBandLowMidHz = 250.0f;
constexpr float kBandMidHighHz = 4000.0f;
}
```

(delete this whole anonymous namespace block), and replace:

```cpp
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
```

with:

```cpp
BandEnergy compute_band_energy(const float* spectrum, size_t spectrum_len,
                                uint32_t sample_rate, uint32_t window_size,
                                float low_split_hz, float high_split_hz) {
    BandEnergy result{0.0f, 0.0f, 0.0f};
    for (size_t i = 0; i < spectrum_len; ++i) {
        float freq = static_cast<float>(i) * static_cast<float>(sample_rate) /
                      static_cast<float>(window_size);
        float energy = spectrum[i] * spectrum[i];
        if (freq < low_split_hz) {
            result.low += energy;
        } else if (freq < high_split_hz) {
            result.mid += energy;
        } else {
            result.high += energy;
        }
    }
    return result;
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `./engine/build.sh`
Expected: build fails again at this point because `engine.cpp` still calls
`compute_band_energy` with the old 4-argument signature — this is expected
and will be fixed in Task 4. For now, build just `dsp_features_test`
directly to confirm the dsp_features changes themselves are correct:

```bash
cmake --build engine/build --target dsp_features_test
./engine/build/dsp_features_test
```

Expected: all `[features]` test cases pass, including the new
"compute_band_energy respects custom split points" case.

- [ ] **Step 6: Commit**

```bash
git add engine/src/dsp_features.h engine/src/dsp_features.cpp engine/tests/dsp_features_test.cpp
git commit -m "Make band energy split points configurable in compute_band_energy"
```

---

### Task 4: Wire window type and band splits into the engine

**Files:**
- Modify: `engine/src/engine.cpp`
- Modify: `engine/tests/engine_test.cpp`

- [ ] **Step 1: Update `engine_test.cpp` to set the new `EngineConfig` fields explicitly**

In `engine/tests/engine_test.cpp`, change the config setup at the top of
`main()`:

```cpp
    EngineConfig config{};
    config.window_size = 4;
    config.sample_rate = 44100;
```

to:

```cpp
    EngineConfig config{};
    config.window_size = 4;
    config.sample_rate = 44100;
    config.update_rate_hz = 0.0f;
    config.fft_window_type = WINDOW_HANN;
    config.band_split_low_hz = 250.0f;
    config.band_split_high_hz = 4000.0f;
```

Then add a second scenario at the end of `main()`, before
`destroy_engine(engine)` (which destroys the first engine) — create a
second engine with `WINDOW_HAMMING` and custom band splits, push a sine-ish
signal, and confirm the frame comes back with sane values. Replace:

```cpp
    // Stereo chunk: mixed down to mono by averaging channels.
    float stereo[] = {2.0f, 4.0f}; // one frame, 2 channels -> mono 3.0
    push_samples(engine, stereo, 1, 2);

    FeatureFrame frame3 = get_latest_features(engine);
    assert(frame3.channels == 2);
    assert(frame3.waveform[3] == 3.0f);

    destroy_engine(engine);

    printf("engine_test: all tests passed\n");
    return 0;
}
```

with:

```cpp
    // Stereo chunk: mixed down to mono by averaging channels.
    float stereo[] = {2.0f, 4.0f}; // one frame, 2 channels -> mono 3.0
    push_samples(engine, stereo, 1, 2);

    FeatureFrame frame3 = get_latest_features(engine);
    assert(frame3.channels == 2);
    assert(frame3.waveform[3] == 3.0f);

    destroy_engine(engine);

    // Hamming window + custom band split configuration.
    EngineConfig hamming_config{};
    hamming_config.window_size = 16;
    hamming_config.sample_rate = 44100;
    hamming_config.update_rate_hz = 30.0f;
    hamming_config.fft_window_type = WINDOW_HAMMING;
    hamming_config.band_split_low_hz = 500.0f;
    hamming_config.band_split_high_hz = 2000.0f;

    EngineHandle hamming_engine = create_engine(hamming_config);

    float samples[16];
    for (int i = 0; i < 16; ++i) {
        samples[i] = static_cast<float>(i % 4) - 1.5f; // simple non-zero signal
    }
    push_samples(hamming_engine, samples, 16, 1);

    FeatureFrame hamming_frame = get_latest_features(hamming_engine);
    assert(hamming_frame.waveform_len == 16);
    assert(hamming_frame.spectrum_len == 9);
    assert(!std::isnan(hamming_frame.rms));
    assert(!std::isnan(hamming_frame.spectral_centroid));
    assert(hamming_frame.rms > 0.0f);

    destroy_engine(hamming_engine);

    printf("engine_test: all tests passed\n");
    return 0;
}
```

- [ ] **Step 2: Run the test to verify it fails (compile error)**

Run: `./engine/build.sh`
Expected: build fails — `engine.cpp`'s call to `compute_band_energy` still
uses the old 4-argument signature (from Task 3), so the library itself
fails to compile.

- [ ] **Step 3: Update `engine.cpp` — rename `hann_coeffs` to `window_coeffs` and select window by type**

In `engine/src/engine.cpp`, the `EngineImpl` struct currently has:

```cpp
struct EngineImpl {
    EngineConfig config;
    sound_viz::RingBuffer ring_buffer;
    std::vector<float> waveform_out;
    std::vector<float> hann_coeffs;
    std::vector<float> windowed_buf;
    std::vector<float> spectrum_out;
    uint64_t frame_counter = 0;
    uint32_t last_channels = 1;

    explicit EngineImpl(EngineConfig cfg)
        : config(cfg),
          ring_buffer(cfg.window_size),
          waveform_out(cfg.window_size, 0.0f),
          hann_coeffs(cfg.window_size, 0.0f),
          windowed_buf(cfg.window_size, 0.0f),
          spectrum_out(cfg.window_size / 2 + 1, 0.0f) {
        sound_viz::hann_window(hann_coeffs.data(), hann_coeffs.size());
    }
};
```

Replace it with:

```cpp
struct EngineImpl {
    EngineConfig config;
    sound_viz::RingBuffer ring_buffer;
    std::vector<float> waveform_out;
    std::vector<float> window_coeffs;
    std::vector<float> windowed_buf;
    std::vector<float> spectrum_out;
    uint64_t frame_counter = 0;
    uint32_t last_channels = 1;

    explicit EngineImpl(EngineConfig cfg)
        : config(cfg),
          ring_buffer(cfg.window_size),
          waveform_out(cfg.window_size, 0.0f),
          window_coeffs(cfg.window_size, 0.0f),
          windowed_buf(cfg.window_size, 0.0f),
          spectrum_out(cfg.window_size / 2 + 1, 0.0f) {
        switch (config.fft_window_type) {
            case WINDOW_HAMMING:
                sound_viz::hamming_window(window_coeffs.data(), window_coeffs.size());
                break;
            case WINDOW_HANN:
            default:
                sound_viz::hann_window(window_coeffs.data(), window_coeffs.size());
                break;
        }
    }
};
```

- [ ] **Step 4: Update `get_latest_features` to use `window_coeffs` and pass band splits**

In `engine/src/engine.cpp`, `get_latest_features` currently has:

```cpp
    sound_viz::apply_window(impl->waveform_out.data(), impl->hann_coeffs.data(),
                             impl->windowed_buf.data(), impl->windowed_buf.size());
```

and:

```cpp
    sound_viz::BandEnergy band_energy = sound_viz::compute_band_energy(
        impl->spectrum_out.data(), impl->spectrum_out.size(),
        impl->config.sample_rate, impl->config.window_size);
```

Replace the first with:

```cpp
    sound_viz::apply_window(impl->waveform_out.data(), impl->window_coeffs.data(),
                             impl->windowed_buf.data(), impl->windowed_buf.size());
```

and the second with:

```cpp
    sound_viz::BandEnergy band_energy = sound_viz::compute_band_energy(
        impl->spectrum_out.data(), impl->spectrum_out.size(),
        impl->config.sample_rate, impl->config.window_size,
        impl->config.band_split_low_hz, impl->config.band_split_high_hz);
```

- [ ] **Step 5: Run the build and full test suite to verify it passes**

Run: `./engine/build.sh`
Expected: build succeeds, and ctest reports all tests passing, including
`engine_test: all tests passed` and the new Hamming/custom-split scenario.

- [ ] **Step 6: Commit**

```bash
git add engine/src/engine.cpp engine/tests/engine_test.cpp
git commit -m "Wire FFT window type and band split config into the engine"
```

---

### Task 5: Python bindings — expose new config fields

**Files:**
- Modify: `engine/bindings/python_bindings.cpp`

- [ ] **Step 1: Add `<string>` include**

At the top of `engine/bindings/python_bindings.cpp`, add `<string>` to the
includes:

```cpp
#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>

#include <cstring>
#include <string>

#include "sound_viz/engine.h"
```

- [ ] **Step 2: Extend `PyEngine`'s constructor**

Replace:

```cpp
class PyEngine {
public:
    PyEngine(uint32_t window_size, uint32_t sample_rate) {
        EngineConfig config{};
        config.window_size = window_size;
        config.sample_rate = sample_rate;
        handle_ = create_engine(config);
    }
```

with:

```cpp
class PyEngine {
public:
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

- [ ] **Step 3: Update the `PYBIND11_MODULE` registration**

Replace:

```cpp
PYBIND11_MODULE(sound_viz_py, m) {
    py::class_<PyEngine>(m, "Engine")
        .def(py::init<uint32_t, uint32_t>(), py::arg("window_size"), py::arg("sample_rate"))
        .def("push_samples", &PyEngine::push_samples, py::arg("samples"), py::arg("n_channels") = 1)
        .def("get_latest_features", &PyEngine::get_latest_features);
}
```

with:

```cpp
PYBIND11_MODULE(sound_viz_py, m) {
    py::class_<PyEngine>(m, "Engine")
        .def(py::init<uint32_t, uint32_t, float, const std::string&, float, float>(),
             py::arg("window_size"), py::arg("sample_rate"),
             py::arg("update_rate_hz") = 0.0f,
             py::arg("fft_window_type") = "hann",
             py::arg("band_split_low_hz") = 250.0f,
             py::arg("band_split_high_hz") = 4000.0f)
        .def("push_samples", &PyEngine::push_samples, py::arg("samples"), py::arg("n_channels") = 1)
        .def("get_latest_features", &PyEngine::get_latest_features);
}
```

- [ ] **Step 4: Rebuild and verify the Python module**

Run: `./engine/build.sh`
Expected: build succeeds (engine build auto-detects the frontend venv and
rebuilds `sound_viz_py` if pybind11 is available — confirm
`engine/build/sound_viz_py*.so` has a fresh timestamp).

Then run a quick smoke check:

```bash
./frontend/run.sh -c "
import sound_viz_py
e = sound_viz_py.Engine(window_size=8, sample_rate=44100)
e2 = sound_viz_py.Engine(window_size=8, sample_rate=44100, update_rate_hz=15.0, fft_window_type='hamming', band_split_low_hz=500.0, band_split_high_hz=2000.0)
print('ok')
try:
    sound_viz_py.Engine(window_size=8, sample_rate=44100, fft_window_type='bogus')
except ValueError as exc:
    print('value_error:', exc)
"
```

Expected output:
```
ok
value_error: fft_window_type must be 'hann' or 'hamming'
```

- [ ] **Step 5: Commit**

```bash
git add engine/bindings/python_bindings.cpp
git commit -m "Expose update rate, FFT window type, and band split config via pybind11"
```

---

### Task 6: Frontend CLI args and per-instance configuration

**Files:**
- Modify: `frontend/main.py`

- [ ] **Step 1: Add new `argparse` arguments**

In `frontend/main.py`'s `main()`, the current parser setup is:

```python
def main():
    parser = argparse.ArgumentParser(description="Sound visualizer - phase 1b spectrum viewer")
    parser.add_argument("wav_path", help="Path to a WAV file")
    args = parser.parse_args()

    app = QtWidgets.QApplication(sys.argv)
    window = WaveformWindow(args.wav_path)
    window.setWindowTitle("Sound Visualizer - Waveform + Spectrum + Features (Phase 1c)")
    window.resize(800, 600)
    window.show()
    app.exec_()
```

Replace it with:

```python
def main():
    parser = argparse.ArgumentParser(description="Sound visualizer - phase 1d configurability")
    parser.add_argument("wav_path", help="Path to a WAV file")
    parser.add_argument("--window-size", type=int, default=1024, help="Analysis window size (samples)")
    parser.add_argument("--update-rate", type=float, default=30.0, help="Target UI update rate (Hz)")
    parser.add_argument("--fft-window", choices=["hann", "hamming"], default="hann", help="FFT window function")
    parser.add_argument("--band-split-low", type=float, default=250.0, help="Low/mid band split frequency (Hz)")
    parser.add_argument("--band-split-high", type=float, default=4000.0, help="Mid/high band split frequency (Hz)")
    args = parser.parse_args()

    app = QtWidgets.QApplication(sys.argv)
    window = WaveformWindow(args.wav_path, args)
    window.setWindowTitle("Sound Visualizer - Waveform + Spectrum + Features (Phase 1d)")
    window.resize(800, 600)
    window.show()
    app.exec_()
```

- [ ] **Step 2: Remove the module-level `WINDOW_SIZE`, `SPECTRUM_LEN`, `CHUNK_FRAMES` constants**

Currently near the top of `frontend/main.py`:

```python
WINDOW_SIZE = 1024
SPECTRUM_LEN = WINDOW_SIZE // 2 + 1
CHUNK_FRAMES = 1024
PEAK_HOLD_SECONDS = 1.0
PEAK_DECAY_PER_SECOND = 1.0
```

Replace with (keeping only the constants that remain fixed):

```python
PEAK_HOLD_SECONDS = 1.0
PEAK_DECAY_PER_SECOND = 1.0
```

- [ ] **Step 3: Update `WaveformWindow.__init__` signature and derive per-instance config**

Currently:

```python
    def __init__(self, wav_path):
        super().__init__()

        data, sample_rate = sf.read(wav_path, dtype="float32", always_2d=True)
        self.data = data
        self.sample_rate = sample_rate
        self.n_channels = data.shape[1]
        self.read_pos = 0

        self.engine = sound_viz_py.Engine(window_size=WINDOW_SIZE, sample_rate=sample_rate)

        self.waveform_plot = pg.PlotWidget()
        self.waveform_plot.setYRange(-1.0, 1.0)
        self.curve = self.waveform_plot.plot(np.zeros(WINDOW_SIZE))

        self.spectrum_plot = pg.PlotWidget()
        self.spectrum_bars = pg.BarGraphItem(
            x=np.arange(SPECTRUM_LEN), height=np.zeros(SPECTRUM_LEN), width=0.8
        )
        self.spectrum_plot.addItem(self.spectrum_bars)
```

Replace with:

```python
    def __init__(self, wav_path, args):
        super().__init__()

        data, sample_rate = sf.read(wav_path, dtype="float32", always_2d=True)
        self.data = data
        self.sample_rate = sample_rate
        self.n_channels = data.shape[1]
        self.read_pos = 0

        self.window_size = args.window_size
        self.spectrum_len = self.window_size // 2 + 1
        self.chunk_frames = max(1, round(sample_rate / args.update_rate))

        self.engine = sound_viz_py.Engine(
            window_size=self.window_size,
            sample_rate=sample_rate,
            update_rate_hz=args.update_rate,
            fft_window_type=args.fft_window,
            band_split_low_hz=args.band_split_low,
            band_split_high_hz=args.band_split_high,
        )

        self.waveform_plot = pg.PlotWidget()
        self.waveform_plot.setYRange(-1.0, 1.0)
        self.curve = self.waveform_plot.plot(np.zeros(self.window_size))

        self.spectrum_plot = pg.PlotWidget()
        self.spectrum_bars = pg.BarGraphItem(
            x=np.arange(self.spectrum_len), height=np.zeros(self.spectrum_len), width=0.8
        )
        self.spectrum_plot.addItem(self.spectrum_bars)
```

- [ ] **Step 4: Update the timer setup to use `self.chunk_frames`**

Currently, at the end of `__init__`:

```python
        interval_ms = int(1000 * CHUNK_FRAMES / sample_rate)
        self.tick_interval_s = interval_ms / 1000.0
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.on_tick)
        self.timer.start(interval_ms)
```

Replace with:

```python
        interval_ms = max(1, int(1000 * self.chunk_frames / sample_rate))
        self.tick_interval_s = interval_ms / 1000.0
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.on_tick)
        self.timer.start(interval_ms)
```

- [ ] **Step 5: Update `on_tick` to use `self.chunk_frames`**

Currently:

```python
    def on_tick(self):
        if self.read_pos >= len(self.data):
            self.timer.stop()
            return

        chunk = self.data[self.read_pos:self.read_pos + CHUNK_FRAMES]
        self.read_pos += CHUNK_FRAMES
```

Replace with:

```python
    def on_tick(self):
        if self.read_pos >= len(self.data):
            self.timer.stop()
            return

        chunk = self.data[self.read_pos:self.read_pos + self.chunk_frames]
        self.read_pos += self.chunk_frames
```

- [ ] **Step 6: Manual smoke test**

Run with defaults (should behave like Phase 1c):

```bash
./frontend/run.sh main.py fixtures/test_tone.wav
```

Expected: window opens, title shows "Phase 1d", waveform/spectrum/meters
update as before.

Run with non-default config:

```bash
./frontend/run.sh main.py fixtures/test_tone.wav --window-size 2048 --update-rate 15 --fft-window hamming --band-split-low 500 --band-split-high 2000
```

Expected: window opens without error, runs at a visibly slower update rate
(~15 Hz instead of ~30 Hz), and the spectrum bar plot shows
`2048 // 2 + 1 == 1025` bars. Close the window when done.

- [ ] **Step 7: Commit**

```bash
git add frontend/main.py
git commit -m "Add CLI flags for window size, update rate, FFT window, and band splits"
```

---

### Task 7: Final verification

**Files:** none (verification only)

- [ ] **Step 1: Full engine build and test run**

Run: `./engine/build.sh`
Expected: all ctest targets pass —
`ring_buffer_test`, `window_test`, `fft_test`, `engine_test`,
`dsp_features_test`, each reporting success (Catch2 summary "All tests
passed" for `dsp_features_test`, `"<name>: all tests passed"` printf for the
others).

- [ ] **Step 2: Frontend smoke test with all new flags combined**

```bash
./frontend/run.sh main.py fixtures/test_tone.wav --window-size 512 --update-rate 20 --fft-window hamming --band-split-low 300 --band-split-high 3000
```

Expected: window opens, runs without exceptions, waveform plot shows 512
samples, spectrum plot shows `512 // 2 + 1 == 257` bars, meters update at
~20 Hz. Close the window when done.

- [ ] **Step 3: Commit (if any fixups were needed)**

If Steps 1-2 required any fixes, stage and commit them with a descriptive
message. If everything passed cleanly, no commit is needed for this task.

---

## Out of scope (deferred to later phases)

- Engine-side gating of recomputation based on `update_rate_hz`.
- Additional FFT window types beyond Hann/Hamming.
- Runtime reconfiguration of a live `Engine` instance.
