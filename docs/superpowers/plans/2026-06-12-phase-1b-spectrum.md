# Phase 1b Spectrum Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Hann windowing + real FFT to the analysis engine, populate `spectrum`/`spectrum_len` in `FeatureFrame`, and render a spectrum bar plot in the Python frontend alongside the existing waveform view.

**Architecture:** Two new small C++ modules (`window.{h,cpp}`, `fft.{h,cpp}`) are added to `sound_viz_engine`. `fft.cpp` wraps a vendored header-only `pocketfft_hdronly.h` to compute a real-to-complex FFT magnitude spectrum. `EngineImpl::get_latest_features` applies a precomputed Hann window to the waveform snapshot, runs the FFT, and populates `frame.spectrum`/`frame.spectrum_len` (N/2+1 bins). The pybind11 binding copies `spectrum` into a numpy array, and `frontend/main.py` adds a second `pyqtgraph` plot with a `BarGraphItem` showing the spectrum bins.

**Tech Stack:** C++17, CMake, pocketfft (vendored header-only FFT), pybind11, Python 3, numpy, pyqtgraph.

Reference design: `docs/superpowers/specs/2026-06-12-phase-1b-spectrum-design.md`

---

### Task 1: Vendor pocketfft_hdronly.h

**Files:**
- Create: `engine/third_party/pocketfft/pocketfft_hdronly.h`
- Create: `engine/third_party/pocketfft/README.md`

- [ ] **Step 1: Create the third_party directory and download the header**

```bash
mkdir -p engine/third_party/pocketfft
curl -sL https://raw.githubusercontent.com/mreineck/pocketfft/5f27d5a8f51c5c25030cb22abf434decc9faf0ff/pocketfft_hdronly.h -o engine/third_party/pocketfft/pocketfft_hdronly.h
```

Expected: the file is created and is non-empty (~3850 lines). Verify with:

```bash
wc -l engine/third_party/pocketfft/pocketfft_hdronly.h
head -5 engine/third_party/pocketfft/pocketfft_hdronly.h
```

Expected output: a line count around `3853` and the first line `/*` (start of
the BSD-3-Clause license header that's embedded in the file).

- [ ] **Step 2: Create `engine/third_party/pocketfft/README.md`**

```markdown
# pocketfft (vendored)

`pocketfft_hdronly.h` is vendored from
https://github.com/mreineck/pocketfft, branch `cpp`, commit
`5f27d5a8f51c5c25030cb22abf434decc9faf0ff`.

Header-only C++17 real/complex FFT, BSD-3-Clause licensed (see the license
block at the top of the header). Used by `engine/src/fft.cpp` for the
real-to-complex FFT.
```

- [ ] **Step 3: Commit**

```bash
git add engine/third_party/pocketfft/pocketfft_hdronly.h engine/third_party/pocketfft/README.md
git commit -m "Vendor pocketfft_hdronly.h for spectrum FFT"
```

---

### Task 2: Hann window module (TDD)

**Files:**
- Create: `engine/src/window.h`
- Create: `engine/src/window.cpp`
- Create: `engine/tests/window_test.cpp`
- Modify: `engine/CMakeLists.txt`

- [ ] **Step 1: Create `engine/src/window.h`**

```cpp
#pragma once

#include <cstddef>

namespace sound_viz {

// Fills `out` (size n) with Hann window coefficients.
void hann_window(float* out, size_t n);

// out[i] = in[i] * window[i], for i in [0, n)
void apply_window(const float* in, const float* window, float* out, size_t n);

} // namespace sound_viz
```

- [ ] **Step 2: Create a stub `engine/src/window.cpp`**

This compiles but does not implement the real behavior yet — the test in
the next step should fail against it.

```cpp
#include "window.h"

namespace sound_viz {

void hann_window(float* out, size_t n) {
    for (size_t i = 0; i < n; ++i) {
        out[i] = 0.0f;
    }
}

void apply_window(const float* in, const float* window, float* out, size_t n) {
    (void)window;
    for (size_t i = 0; i < n; ++i) {
        out[i] = in[i];
    }
}

} // namespace sound_viz
```

- [ ] **Step 3: Create `engine/tests/window_test.cpp`**

```cpp
#include "window.h"

#include <cassert>
#include <cmath>
#include <cstdio>

using namespace sound_viz;

void test_hann_window_endpoints_and_peak() {
    float w[5];
    hann_window(w, 5);
    assert(std::abs(w[0] - 0.0f) < 1e-6f);
    assert(std::abs(w[4] - 0.0f) < 1e-6f);
    assert(std::abs(w[2] - 1.0f) < 1e-6f); // center sample
}

void test_apply_window() {
    float in[3] = {2.0f, 3.0f, 4.0f};
    float win[3] = {0.5f, 1.0f, 0.0f};
    float out[3];
    apply_window(in, win, out, 3);
    assert(out[0] == 1.0f);
    assert(out[1] == 3.0f);
    assert(out[2] == 0.0f);
}

int main() {
    test_hann_window_endpoints_and_peak();
    test_apply_window();
    printf("window_test: all tests passed\n");
    return 0;
}
```

- [ ] **Step 4: Modify `engine/CMakeLists.txt`** — add `src/window.cpp` to
the library and add the `window_test` executable

```cmake
cmake_minimum_required(VERSION 3.15)
project(sound_viz_engine LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_library(sound_viz_engine STATIC
    src/ring_buffer.cpp
    src/window.cpp
    src/engine.cpp
)
target_include_directories(sound_viz_engine PUBLIC include)
target_include_directories(sound_viz_engine PRIVATE src)

enable_testing()

add_executable(ring_buffer_test tests/ring_buffer_test.cpp)
target_include_directories(ring_buffer_test PRIVATE src)
target_link_libraries(ring_buffer_test PRIVATE sound_viz_engine)
add_test(NAME ring_buffer_test COMMAND ring_buffer_test)

add_executable(window_test tests/window_test.cpp)
target_include_directories(window_test PRIVATE src)
target_link_libraries(window_test PRIVATE sound_viz_engine)
add_test(NAME window_test COMMAND window_test)

add_executable(engine_test tests/engine_test.cpp)
target_link_libraries(engine_test PRIVATE sound_viz_engine)
add_test(NAME engine_test COMMAND engine_test)

find_package(pybind11 CONFIG QUIET)
if(pybind11_FOUND)
    pybind11_add_module(sound_viz_py bindings/python_bindings.cpp)
    target_link_libraries(sound_viz_py PRIVATE sound_viz_engine)
else()
    message(WARNING "pybind11 not found - skipping sound_viz_py Python module. "
                     "Pass -Dpybind11_DIR=$(frontend/.venv/bin/python -m pybind11 --cmakedir) to enable it.")
endif()
```

- [ ] **Step 5: Configure, build, and run the test to verify it fails**

```bash
cmake -S engine -B engine/build
cmake --build engine/build
engine/build/window_test
echo "exit code: $?"
```

Expected: build succeeds, but `window_test` aborts via a failed `assert`
(e.g. `w[2] == 1.0f` fails since the stub returns all zeros).

- [ ] **Step 6: Implement `engine/src/window.cpp` for real**

```cpp
#include "window.h"

#include <cmath>

namespace sound_viz {

void hann_window(float* out, size_t n) {
    if (n == 1) {
        out[0] = 1.0f;
        return;
    }
    const float two_pi = 6.283185307179586f;
    for (size_t i = 0; i < n; ++i) {
        out[i] = 0.5f * (1.0f - std::cos(two_pi * static_cast<float>(i) / static_cast<float>(n - 1)));
    }
}

void apply_window(const float* in, const float* window, float* out, size_t n) {
    for (size_t i = 0; i < n; ++i) {
        out[i] = in[i] * window[i];
    }
}

} // namespace sound_viz
```

- [ ] **Step 7: Rebuild and run the test, verify it passes**

```bash
cmake --build engine/build
engine/build/window_test
```

Expected: prints `window_test: all tests passed` and exits 0.

- [ ] **Step 8: Commit**

```bash
git add engine/CMakeLists.txt engine/src/window.h engine/src/window.cpp engine/tests/window_test.cpp
git commit -m "Add Hann window generation and application"
```

---

### Task 3: Real FFT magnitude module (TDD)

**Files:**
- Create: `engine/src/fft.h`
- Create: `engine/src/fft.cpp`
- Create: `engine/tests/fft_test.cpp`
- Modify: `engine/CMakeLists.txt`

- [ ] **Step 1: Create `engine/src/fft.h`**

```cpp
#pragma once

#include <cstddef>

namespace sound_viz {

// Computes the magnitude spectrum of a real input of size n (n even).
// Writes n/2 + 1 magnitude values into `out`.
void real_fft_magnitude(const float* in, size_t n, float* out);

} // namespace sound_viz
```

- [ ] **Step 2: Create a stub `engine/src/fft.cpp`**

This compiles but does not implement the real behavior yet — the test in
the next step should fail against it.

```cpp
#include "fft.h"

namespace sound_viz {

void real_fft_magnitude(const float* in, size_t n, float* out) {
    (void)in;
    for (size_t i = 0; i < n / 2 + 1; ++i) {
        out[i] = 0.0f;
    }
}

} // namespace sound_viz
```

- [ ] **Step 3: Create `engine/tests/fft_test.cpp`**

```cpp
#include "fft.h"
#include "window.h"

#include <cassert>
#include <cmath>
#include <cstdio>
#include <vector>

using namespace sound_viz;

int main() {
    const size_t n = 1024;
    const double sample_rate = 44100.0;
    const double freq = 1000.0;
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

    size_t peak_bin = 0;
    float peak_val = 0.0f;
    for (size_t i = 0; i < spectrum.size(); ++i) {
        if (spectrum[i] > peak_val) {
            peak_val = spectrum[i];
            peak_bin = i;
        }
    }

    size_t expected_bin = static_cast<size_t>(std::lround(freq * static_cast<double>(n) / sample_rate));
    long diff = static_cast<long>(peak_bin) - static_cast<long>(expected_bin);

    assert(spectrum.size() == n / 2 + 1);
    assert(peak_val > 0.0f);
    assert(diff >= -1 && diff <= 1);

    printf("fft_test: all tests passed (peak_bin=%zu expected=%zu)\n", peak_bin, expected_bin);
    return 0;
}
```

- [ ] **Step 4: Modify `engine/CMakeLists.txt`** — add `src/fft.cpp` to the
library, add the pocketfft include path, and add the `fft_test` executable

```cmake
cmake_minimum_required(VERSION 3.15)
project(sound_viz_engine LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_library(sound_viz_engine STATIC
    src/ring_buffer.cpp
    src/window.cpp
    src/fft.cpp
    src/engine.cpp
)
target_include_directories(sound_viz_engine PUBLIC include)
target_include_directories(sound_viz_engine PRIVATE src third_party/pocketfft)

enable_testing()

add_executable(ring_buffer_test tests/ring_buffer_test.cpp)
target_include_directories(ring_buffer_test PRIVATE src)
target_link_libraries(ring_buffer_test PRIVATE sound_viz_engine)
add_test(NAME ring_buffer_test COMMAND ring_buffer_test)

add_executable(window_test tests/window_test.cpp)
target_include_directories(window_test PRIVATE src)
target_link_libraries(window_test PRIVATE sound_viz_engine)
add_test(NAME window_test COMMAND window_test)

add_executable(fft_test tests/fft_test.cpp)
target_include_directories(fft_test PRIVATE src)
target_link_libraries(fft_test PRIVATE sound_viz_engine)
add_test(NAME fft_test COMMAND fft_test)

add_executable(engine_test tests/engine_test.cpp)
target_link_libraries(engine_test PRIVATE sound_viz_engine)
add_test(NAME engine_test COMMAND engine_test)

find_package(pybind11 CONFIG QUIET)
if(pybind11_FOUND)
    pybind11_add_module(sound_viz_py bindings/python_bindings.cpp)
    target_link_libraries(sound_viz_py PRIVATE sound_viz_engine)
else()
    message(WARNING "pybind11 not found - skipping sound_viz_py Python module. "
                     "Pass -Dpybind11_DIR=$(frontend/.venv/bin/python -m pybind11 --cmakedir) to enable it.")
endif()
```

- [ ] **Step 5: Configure, build, and run the test to verify it fails**

```bash
cmake -S engine -B engine/build
cmake --build engine/build
engine/build/fft_test
echo "exit code: $?"
```

Expected: build succeeds, but `fft_test` aborts via a failed `assert` (e.g.
`peak_val > 0.0f` fails since the stub returns all zeros).

- [ ] **Step 6: Implement `engine/src/fft.cpp` for real**

```cpp
#include "fft.h"
#include "pocketfft_hdronly.h"

#include <complex>
#include <vector>

namespace sound_viz {

void real_fft_magnitude(const float* in, size_t n, float* out) {
    pocketfft::shape_t shape{n};
    pocketfft::stride_t stride_in{sizeof(float)};
    pocketfft::stride_t stride_out{sizeof(std::complex<float>)};
    pocketfft::shape_t axes{0};

    std::vector<std::complex<float>> spectrum(n / 2 + 1);
    pocketfft::r2c(shape, stride_in, stride_out, axes, true, in, spectrum.data(), 1.0f);

    for (size_t i = 0; i < spectrum.size(); ++i) {
        out[i] = std::abs(spectrum[i]);
    }
}

} // namespace sound_viz
```

- [ ] **Step 7: Rebuild and run the test, verify it passes**

```bash
cmake --build engine/build
engine/build/fft_test
```

Expected: prints `fft_test: all tests passed (peak_bin=23 expected=23)` (or
`peak_bin` within 1 of `expected`) and exits 0.

- [ ] **Step 8: Commit**

```bash
git add engine/CMakeLists.txt engine/src/fft.h engine/src/fft.cpp engine/tests/fft_test.cpp
git commit -m "Add real FFT magnitude wrapper around pocketfft"
```

---

### Task 4: Wire spectrum into the engine (TDD)

**Files:**
- Modify: `engine/include/sound_viz/feature_frame.h`
- Modify: `engine/src/engine.cpp`
- Modify: `engine/tests/engine_test.cpp`

- [ ] **Step 1: Update `engine/tests/engine_test.cpp` assertions for the
new spectrum behavior**

With `window_size = 4`, `spectrum_len` will now be `4/2 + 1 = 3` and
`spectrum` will be a valid (non-null) pointer for every frame, including the
first one. Replace the two assertions that check for the 1a placeholder
values:

```cpp
    assert(frame1.spectrum == nullptr);
    assert(frame1.spectrum_len == 0);
```

with:

```cpp
    assert(frame1.spectrum != nullptr);
    assert(frame1.spectrum_len == 3);
```

The full file should now read:

```cpp
#include "sound_viz/engine.h"

#include <cassert>
#include <cstdio>

int main() {
    EngineConfig config{};
    config.window_size = 4;
    config.sample_rate = 44100;

    EngineHandle engine = create_engine(config);

    // First chunk: fewer samples than window_size -> zero-padded front.
    float chunk1[] = {1.0f, 2.0f};
    push_samples(engine, chunk1, 2, 1);

    FeatureFrame frame1 = get_latest_features(engine);
    assert(frame1.sample_rate == 44100);
    assert(frame1.channels == 1);
    assert(frame1.waveform_len == 4);
    assert(frame1.waveform[0] == 0.0f);
    assert(frame1.waveform[1] == 0.0f);
    assert(frame1.waveform[2] == 1.0f);
    assert(frame1.waveform[3] == 2.0f);
    assert(frame1.spectrum != nullptr);
    assert(frame1.spectrum_len == 3);
    assert(frame1.rms == 0.0f);
    assert(frame1.frame_index == 0);

    // Second chunk: fills the window exactly.
    float chunk2[] = {3.0f, 4.0f, 5.0f, 6.0f};
    push_samples(engine, chunk2, 4, 1);

    FeatureFrame frame2 = get_latest_features(engine);
    assert(frame2.waveform[0] == 3.0f);
    assert(frame2.waveform[1] == 4.0f);
    assert(frame2.waveform[2] == 5.0f);
    assert(frame2.waveform[3] == 6.0f);
    assert(frame2.spectrum != nullptr);
    assert(frame2.spectrum_len == 3);
    assert(frame2.frame_index == 1);

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

- [ ] **Step 2: Rebuild and run `engine_test` to verify it fails**

```bash
cmake --build engine/build
engine/build/engine_test
echo "exit code: $?"
```

Expected: aborts via a failed `assert` (`frame1.spectrum != nullptr` fails,
since `engine.cpp` still leaves `frame.spectrum` as `nullptr` from the
zero-initialized `FeatureFrame{}`).

- [ ] **Step 3: Modify `engine/src/engine.cpp`** to apply the Hann window,
run the FFT, and populate `spectrum`/`spectrum_len`

```cpp
#include "sound_viz/engine.h"
#include "ring_buffer.h"
#include "window.h"
#include "fft.h"

#include <vector>

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

extern "C" {

EngineHandle create_engine(EngineConfig config) {
    return new EngineImpl(config);
}

void push_samples(EngineHandle engine, const float* samples, uint32_t n_frames, uint32_t n_channels) {
    EngineImpl* impl = engine;
    impl->last_channels = n_channels;

    if (n_channels == 0) {
        return;
    }

    if (n_channels == 1) {
        impl->ring_buffer.push(samples, n_frames);
        return;
    }

    std::vector<float> mono(n_frames);
    for (uint32_t i = 0; i < n_frames; ++i) {
        float sum = 0.0f;
        for (uint32_t c = 0; c < n_channels; ++c) {
            sum += samples[i * n_channels + c];
        }
        mono[i] = sum / static_cast<float>(n_channels);
    }
    impl->ring_buffer.push(mono.data(), n_frames);
}

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
    return frame;
}

void destroy_engine(EngineHandle engine) {
    delete engine;
}

}
```

- [ ] **Step 4: Update comments in
`engine/include/sound_viz/feature_frame.h`**

Change:

```cpp
    // Frequency-domain
    const float* spectrum;     // nullptr in 1a (added in 1b)
    uint32_t spectrum_len;     // 0 in 1a
```

to:

```cpp
    // Frequency-domain
    const float* spectrum;     // populated in 1b: N/2+1 magnitude bins
    uint32_t spectrum_len;     // == window_size/2 + 1
```

- [ ] **Step 5: Rebuild and run the full C++ test suite, verify it passes**

```bash
cmake --build engine/build
cd engine/build && ctest --output-on-failure && cd ../..
```

Expected: `ring_buffer_test`, `window_test`, `fft_test`, and `engine_test`
all pass.

- [ ] **Step 6: Commit**

```bash
git add engine/include/sound_viz/feature_frame.h engine/src/engine.cpp engine/tests/engine_test.cpp
git commit -m "Populate FeatureFrame.spectrum via Hann window + FFT"
```

---

### Task 5: pybind11 binding + Python smoke test

**Files:**
- Modify: `engine/bindings/python_bindings.cpp`
- Modify: `engine/tests/python_smoke_test.py`

- [ ] **Step 1: Ensure the frontend virtualenv exists with dependencies
installed**

```bash
ls frontend/.venv/bin/python || python3 -m venv frontend/.venv
frontend/.venv/bin/pip install -r frontend/requirements.txt
```

Expected: `frontend/.venv` exists with `numpy`, `pybind11`, `soundfile`,
`pyqtgraph`, and `PyQt5` installed.

- [ ] **Step 2: Modify `engine/bindings/python_bindings.cpp`** — copy
`spectrum` into the returned dict, same pattern as `waveform`

In `PyEngine::get_latest_features`, after the existing `waveform` copy, add:

```cpp
        py::array_t<float> spectrum(frame.spectrum_len);
        std::memcpy(spectrum.mutable_data(), frame.spectrum, frame.spectrum_len * sizeof(float));
```

and add `result["spectrum"] = spectrum;` to the dict. The full method
becomes:

```cpp
    py::dict get_latest_features() {
        FeatureFrame frame = ::get_latest_features(handle_);

        py::array_t<float> waveform(frame.waveform_len);
        std::memcpy(waveform.mutable_data(), frame.waveform, frame.waveform_len * sizeof(float));

        py::array_t<float> spectrum(frame.spectrum_len);
        std::memcpy(spectrum.mutable_data(), frame.spectrum, frame.spectrum_len * sizeof(float));

        py::dict result;
        result["frame_index"] = frame.frame_index;
        result["sample_rate"] = frame.sample_rate;
        result["channels"] = frame.channels;
        result["waveform"] = waveform;
        result["spectrum"] = spectrum;
        result["rms"] = frame.rms;
        result["zero_crossing_rate"] = frame.zero_crossing_rate;
        result["peak"] = frame.peak;
        result["band_energy_low"] = frame.band_energy_low;
        result["band_energy_mid"] = frame.band_energy_mid;
        result["band_energy_high"] = frame.band_energy_high;
        result["spectral_centroid"] = frame.spectral_centroid;
        return result;
    }
```

- [ ] **Step 3: Reconfigure CMake with the venv's pybind11 and build**

```bash
cmake -S engine -B engine/build -Dpybind11_DIR="$(frontend/.venv/bin/python -m pybind11 --cmakedir)"
cmake --build engine/build
```

Expected: build succeeds and produces a `sound_viz_py*.so` file under
`engine/build/`.

- [ ] **Step 4: Modify `engine/tests/python_smoke_test.py`** — assert on the
new `spectrum` field

After the existing assertions for `frame` (first `get_latest_features()`
call with `window_size=4`, so `spectrum_len == 3`), add:

```python
assert frame["spectrum"].shape == (3,)
```

and after the assertions for `frame2`, add:

```python
assert frame2["spectrum"].shape == (3,)
```

The full file becomes:

```python
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "build"))

import sound_viz_py

engine = sound_viz_py.Engine(window_size=4, sample_rate=44100)

engine.push_samples(np.array([1.0, 2.0], dtype=np.float32), 1)
frame = engine.get_latest_features()
assert frame["waveform"].tolist() == [0.0, 0.0, 1.0, 2.0], frame["waveform"]
assert frame["sample_rate"] == 44100
assert frame["channels"] == 1
assert frame["frame_index"] == 0
assert frame["spectrum"].shape == (3,)

engine.push_samples(np.array([3.0, 4.0, 5.0, 6.0], dtype=np.float32), 1)
frame2 = engine.get_latest_features()
assert frame2["waveform"].tolist() == [3.0, 4.0, 5.0, 6.0], frame2["waveform"]
assert frame2["frame_index"] == 1
assert frame2["spectrum"].shape == (3,)

print("python_smoke_test: OK")
```

- [ ] **Step 5: Run the smoke test**

```bash
frontend/.venv/bin/python engine/tests/python_smoke_test.py
```

Expected: prints `python_smoke_test: OK`.

- [ ] **Step 6: Commit**

```bash
git add engine/bindings/python_bindings.cpp engine/tests/python_smoke_test.py
git commit -m "Expose spectrum through the pybind11 binding"
```

---

### Task 6: Frontend spectrum bar plot

**Files:**
- Modify: `frontend/main.py`
- Modify: `frontend/scripts/smoke_test_harness.py`

- [ ] **Step 1: Modify `frontend/main.py`** — add a second `pyqtgraph` plot
with a `BarGraphItem` for the spectrum, laid out below the waveform plot

```python
import argparse
import os
import sys

import numpy as np
import soundfile as sf
from PyQt5 import QtCore, QtWidgets
import pyqtgraph as pg

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "engine", "build"))
import sound_viz_py

WINDOW_SIZE = 1024
SPECTRUM_LEN = WINDOW_SIZE // 2 + 1
CHUNK_FRAMES = 1024


class WaveformWindow(QtWidgets.QMainWindow):
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

        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        layout.addWidget(self.waveform_plot)
        layout.addWidget(self.spectrum_plot)
        self.setCentralWidget(container)

        interval_ms = int(1000 * CHUNK_FRAMES / sample_rate)
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.on_tick)
        self.timer.start(interval_ms)

    def on_tick(self):
        if self.read_pos >= len(self.data):
            self.timer.stop()
            return

        chunk = self.data[self.read_pos:self.read_pos + CHUNK_FRAMES]
        self.read_pos += CHUNK_FRAMES

        flat = chunk.reshape(-1).astype(np.float32)
        self.engine.push_samples(flat, self.n_channels)

        frame = self.engine.get_latest_features()
        self.curve.setData(frame["waveform"])
        self.spectrum_bars.setOpts(height=frame["spectrum"])


def main():
    parser = argparse.ArgumentParser(description="Sound visualizer - phase 1b spectrum viewer")
    parser.add_argument("wav_path", help="Path to a WAV file")
    args = parser.parse_args()

    app = QtWidgets.QApplication(sys.argv)
    window = WaveformWindow(args.wav_path)
    window.setWindowTitle("Sound Visualizer - Waveform + Spectrum (Phase 1b)")
    window.resize(800, 600)
    window.show()
    app.exec_()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Modify `frontend/scripts/smoke_test_harness.py`** — assert
the spectrum bars are populated after ticking

```python
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys

import numpy as np
from PyQt5 import QtWidgets

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from main import WaveformWindow, WINDOW_SIZE, SPECTRUM_LEN, CHUNK_FRAMES

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "..", "fixtures", "test_tone.wav")

app = QtWidgets.QApplication(sys.argv)
window = WaveformWindow(FIXTURE_PATH)

window.on_tick()
window.on_tick()

curve_x, curve_y = window.curve.getData()
assert len(curve_y) == WINDOW_SIZE
assert np.any(curve_y != 0)
assert window.read_pos == 2 * CHUNK_FRAMES

heights = window.spectrum_bars.opts["height"]
assert len(heights) == SPECTRUM_LEN
assert np.any(heights != 0)

print("smoke_test_harness: OK")
```

- [ ] **Step 3: Run the headless smoke test**

```bash
frontend/.venv/bin/python frontend/scripts/smoke_test_harness.py
```

Expected: prints `smoke_test_harness: OK`.

- [ ] **Step 4: Commit**

```bash
git add frontend/main.py frontend/scripts/smoke_test_harness.py
git commit -m "Add spectrum bar plot to the frontend"
```

---

### Task 7: End-to-end manual validation

**Files:** none (validation only)

- [ ] **Step 1: Run the full C++ test suite via ctest**

```bash
cd engine/build && ctest --output-on-failure && cd ../..
```

Expected: `ring_buffer_test`, `window_test`, `fft_test`, and `engine_test`
all pass.

- [ ] **Step 2: Run both Python smoke tests**

```bash
frontend/.venv/bin/python engine/tests/python_smoke_test.py
frontend/.venv/bin/python frontend/scripts/smoke_test_harness.py
```

Expected: both print their `OK` messages.

- [ ] **Step 3: Run the full harness with a real display**

```bash
frontend/.venv/bin/python frontend/main.py frontend/fixtures/test_tone.wav
```

Expected: a window titled "Sound Visualizer - Waveform + Spectrum (Phase
1b)" opens, showing the waveform scrolling on top and a bar graph below it
with a spectral peak around the 440Hz test tone's bin (`round(440 * 1024 /
sample_rate)`), updating in real time with no crashes. Close the window when
done — this confirms phase 1b's goal (spectrum data flows end-to-end and
renders) is met.
