# Phase 1a Plumbing Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the end-to-end plumbing skeleton — C++ ring buffer + engine with a stable `FeatureFrame`/`EngineConfig` C API, a pybind11 binding, and a Python `pyqtgraph` harness that reads a WAV file and renders the raw waveform in real time, with no DSP yet.

**Architecture:** A static C++17 library (`sound_viz_engine`) implements a ring buffer and an `extern "C"` API (`create_engine`/`push_samples`/`get_latest_features`/`destroy_engine`) operating on the full v1 `FeatureFrame`/`EngineConfig` structs (only waveform fields populated in 1a). A pybind11 module (`sound_viz_py`) wraps this API for Python. A `pyqtgraph`/PyQt5 harness in `frontend/` reads a WAV file via `soundfile`, feeds chunks to the engine on a `QTimer`, and plots the returned waveform snapshot.

**Tech Stack:** C++17, CMake, pybind11, Python 3, numpy, soundfile, PyQt5, pyqtgraph.

Reference design: `docs/superpowers/specs/2026-06-12-phase-1a-plumbing-skeleton-design.md`

---

### Task 1: Project scaffolding

**Files:**
- Create: `.gitignore`
- Create: `engine/include/sound_viz/feature_frame.h`
- Create: `engine/include/sound_viz/engine.h`

- [ ] **Step 1: Create `.gitignore`**

```
engine/build/
frontend/.venv/
frontend/fixtures/
__pycache__/
*.pyc
```

- [ ] **Step 2: Create `engine/include/sound_viz/feature_frame.h`**

```cpp
#pragma once

#include <cstdint>

extern "C" {

typedef struct {
    uint32_t window_size;   // N, e.g. 1024 — size of the analysis window
    uint32_t sample_rate;   // from WAV header; echoed back in FeatureFrame
} EngineConfig;

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

}
```

- [ ] **Step 3: Create `engine/include/sound_viz/engine.h`**

```cpp
#pragma once

#include "sound_viz/feature_frame.h"

extern "C" {

typedef struct EngineImpl* EngineHandle;

EngineHandle create_engine(EngineConfig config);
void push_samples(EngineHandle engine, const float* samples, uint32_t n_frames, uint32_t n_channels);
FeatureFrame get_latest_features(EngineHandle engine);
void destroy_engine(EngineHandle engine);

}
```

- [ ] **Step 4: Commit**

```bash
git add .gitignore engine/include/sound_viz/feature_frame.h engine/include/sound_viz/engine.h
git commit -m "Add phase 1a C API headers (FeatureFrame, EngineConfig)"
```

---

### Task 2: Ring buffer (TDD)

**Files:**
- Create: `engine/src/ring_buffer.h`
- Create: `engine/src/ring_buffer.cpp`
- Create: `engine/tests/ring_buffer_test.cpp`
- Create: `engine/CMakeLists.txt`

- [ ] **Step 1: Create `engine/src/ring_buffer.h`**

```cpp
#pragma once

#include <cstddef>
#include <vector>

namespace sound_viz {

class RingBuffer {
public:
    explicit RingBuffer(size_t capacity);

    // Appends `count` samples to the buffer, overwriting the oldest samples
    // once capacity is exceeded.
    void push(const float* samples, size_t count);

    // Writes the most recent capacity() samples into `out`, oldest first.
    // Zero-pads the front until capacity() samples have been pushed in total.
    void copy_latest(float* out) const;

    size_t capacity() const { return buffer_.size(); }

private:
    std::vector<float> buffer_;
    size_t write_pos_ = 0;
    size_t total_pushed_ = 0;
};

} // namespace sound_viz
```

- [ ] **Step 2: Create a stub `engine/src/ring_buffer.cpp`**

This compiles but does not implement the real behavior yet — the test in
the next step should fail against it.

```cpp
#include "ring_buffer.h"

namespace sound_viz {

RingBuffer::RingBuffer(size_t capacity) : buffer_(capacity, 0.0f) {}

void RingBuffer::push(const float* samples, size_t count) {
    (void)samples;
    (void)count;
}

void RingBuffer::copy_latest(float* out) const {
    (void)out;
}

} // namespace sound_viz
```

- [ ] **Step 3: Create `engine/tests/ring_buffer_test.cpp`**

```cpp
#include "ring_buffer.h"

#include <cassert>
#include <cstdio>
#include <vector>

using sound_viz::RingBuffer;

void test_zero_padding_before_full() {
    RingBuffer rb(4);
    float samples[] = {1.0f, 2.0f};
    rb.push(samples, 2);

    std::vector<float> out(4);
    rb.copy_latest(out.data());

    assert(out[0] == 0.0f);
    assert(out[1] == 0.0f);
    assert(out[2] == 1.0f);
    assert(out[3] == 2.0f);
}

void test_wraps_when_over_capacity() {
    RingBuffer rb(4);
    float samples[] = {1.0f, 2.0f, 3.0f, 4.0f, 5.0f, 6.0f};
    rb.push(samples, 6);

    std::vector<float> out(4);
    rb.copy_latest(out.data());

    assert(out[0] == 3.0f);
    assert(out[1] == 4.0f);
    assert(out[2] == 5.0f);
    assert(out[3] == 6.0f);
}

int main() {
    test_zero_padding_before_full();
    test_wraps_when_over_capacity();
    printf("ring_buffer_test: all tests passed\n");
    return 0;
}
```

- [ ] **Step 4: Create `engine/CMakeLists.txt`**

```cmake
cmake_minimum_required(VERSION 3.15)
project(sound_viz_engine LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_library(sound_viz_engine STATIC
    src/ring_buffer.cpp
)
target_include_directories(sound_viz_engine PUBLIC include)
target_include_directories(sound_viz_engine PRIVATE src)

enable_testing()

add_executable(ring_buffer_test tests/ring_buffer_test.cpp)
target_include_directories(ring_buffer_test PRIVATE src)
target_link_libraries(ring_buffer_test PRIVATE sound_viz_engine)
add_test(NAME ring_buffer_test COMMAND ring_buffer_test)
```

- [ ] **Step 5: Configure and build**

```bash
cmake -S engine -B engine/build
cmake --build engine/build
```

Expected: build succeeds (stub compiles cleanly).

- [ ] **Step 6: Run the test to verify it fails**

```bash
engine/build/ring_buffer_test
echo "exit code: $?"
```

Expected: program aborts via a failed `assert` (non-zero exit code), since
`copy_latest` is still a stub.

- [ ] **Step 7: Implement `engine/src/ring_buffer.cpp` for real**

```cpp
#include "ring_buffer.h"

namespace sound_viz {

RingBuffer::RingBuffer(size_t capacity) : buffer_(capacity, 0.0f) {}

void RingBuffer::push(const float* samples, size_t count) {
    size_t capacity = buffer_.size();
    for (size_t i = 0; i < count; ++i) {
        buffer_[write_pos_] = samples[i];
        write_pos_ = (write_pos_ + 1) % capacity;
    }
    total_pushed_ += count;
}

void RingBuffer::copy_latest(float* out) const {
    size_t capacity = buffer_.size();
    if (total_pushed_ >= capacity) {
        for (size_t i = 0; i < capacity; ++i) {
            out[i] = buffer_[(write_pos_ + i) % capacity];
        }
        return;
    }

    size_t pad = capacity - total_pushed_;
    for (size_t i = 0; i < pad; ++i) {
        out[i] = 0.0f;
    }
    for (size_t i = 0; i < total_pushed_; ++i) {
        out[pad + i] = buffer_[i];
    }
}

} // namespace sound_viz
```

- [ ] **Step 8: Rebuild and run the test, verify it passes**

```bash
cmake --build engine/build
engine/build/ring_buffer_test
```

Expected: prints `ring_buffer_test: all tests passed` and exits 0.

- [ ] **Step 9: Commit**

```bash
git add engine/CMakeLists.txt engine/src/ring_buffer.h engine/src/ring_buffer.cpp engine/tests/ring_buffer_test.cpp
git commit -m "Add ring buffer with zero-padding and wraparound behavior"
```

---

### Task 3: Engine core (TDD)

**Files:**
- Create: `engine/src/engine.cpp`
- Create: `engine/tests/engine_test.cpp`
- Modify: `engine/CMakeLists.txt`

- [ ] **Step 1: Create a stub `engine/src/engine.cpp`**

This compiles but doesn't implement real behavior — the test in the next
step should fail against it.

```cpp
#include "sound_viz/engine.h"
#include "ring_buffer.h"

#include <vector>

struct EngineImpl {
    EngineConfig config;
    sound_viz::RingBuffer ring_buffer;
    std::vector<float> waveform_out;
    uint64_t frame_counter = 0;
    uint32_t last_channels = 1;

    explicit EngineImpl(EngineConfig cfg)
        : config(cfg),
          ring_buffer(cfg.window_size),
          waveform_out(cfg.window_size, 0.0f) {}
};

extern "C" {

EngineHandle create_engine(EngineConfig config) {
    return new EngineImpl(config);
}

void push_samples(EngineHandle engine, const float* samples, uint32_t n_frames, uint32_t n_channels) {
    (void)engine;
    (void)samples;
    (void)n_frames;
    (void)n_channels;
}

FeatureFrame get_latest_features(EngineHandle engine) {
    (void)engine;
    FeatureFrame frame{};
    return frame;
}

void destroy_engine(EngineHandle engine) {
    delete engine;
}

}
```

- [ ] **Step 2: Create `engine/tests/engine_test.cpp`**

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
    assert(frame1.spectrum == nullptr);
    assert(frame1.spectrum_len == 0);
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

- [ ] **Step 3: Modify `engine/CMakeLists.txt`** to add `engine.cpp` to the
library and add the `engine_test` executable

```cmake
cmake_minimum_required(VERSION 3.15)
project(sound_viz_engine LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_library(sound_viz_engine STATIC
    src/ring_buffer.cpp
    src/engine.cpp
)
target_include_directories(sound_viz_engine PUBLIC include)
target_include_directories(sound_viz_engine PRIVATE src)

enable_testing()

add_executable(ring_buffer_test tests/ring_buffer_test.cpp)
target_include_directories(ring_buffer_test PRIVATE src)
target_link_libraries(ring_buffer_test PRIVATE sound_viz_engine)
add_test(NAME ring_buffer_test COMMAND ring_buffer_test)

add_executable(engine_test tests/engine_test.cpp)
target_link_libraries(engine_test PRIVATE sound_viz_engine)
add_test(NAME engine_test COMMAND engine_test)
```

- [ ] **Step 4: Build and run the test to verify it fails**

```bash
cmake --build engine/build
engine/build/engine_test
echo "exit code: $?"
```

Expected: aborts via a failed `assert` (e.g. `frame1.waveform_len == 4`
fails since the stub returns a zero-initialized `FeatureFrame`).

- [ ] **Step 5: Implement `engine/src/engine.cpp` for real**

```cpp
#include "sound_viz/engine.h"
#include "ring_buffer.h"

#include <vector>

struct EngineImpl {
    EngineConfig config;
    sound_viz::RingBuffer ring_buffer;
    std::vector<float> waveform_out;
    uint64_t frame_counter = 0;
    uint32_t last_channels = 1;

    explicit EngineImpl(EngineConfig cfg)
        : config(cfg),
          ring_buffer(cfg.window_size),
          waveform_out(cfg.window_size, 0.0f) {}
};

extern "C" {

EngineHandle create_engine(EngineConfig config) {
    return new EngineImpl(config);
}

void push_samples(EngineHandle engine, const float* samples, uint32_t n_frames, uint32_t n_channels) {
    EngineImpl* impl = engine;
    impl->last_channels = n_channels;

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

    FeatureFrame frame{};
    frame.frame_index = impl->frame_counter++;
    frame.sample_rate = impl->config.sample_rate;
    frame.channels = impl->last_channels;
    frame.waveform = impl->waveform_out.data();
    frame.waveform_len = static_cast<uint32_t>(impl->waveform_out.size());
    return frame;
}

void destroy_engine(EngineHandle engine) {
    delete engine;
}

}
```

Note: `FeatureFrame frame{};` zero-initializes all fields, so `rms`,
`spectrum`, `spectrum_len`, etc. are already `0`/`nullptr` as required for
1a.

- [ ] **Step 6: Rebuild and run both tests, verify they pass**

```bash
cmake --build engine/build
engine/build/ring_buffer_test
engine/build/engine_test
```

Expected: both print their "all tests passed" messages and exit 0.

- [ ] **Step 7: Commit**

```bash
git add engine/CMakeLists.txt engine/src/engine.cpp engine/tests/engine_test.cpp
git commit -m "Implement engine core: create/push/get_latest_features/destroy"
```

---

### Task 4: Python environment and pybind11 bindings

**Files:**
- Create: `frontend/requirements.txt`
- Create: `engine/bindings/python_bindings.cpp`
- Modify: `engine/CMakeLists.txt`
- Create: `engine/tests/python_smoke_test.py`

- [ ] **Step 1: Create `frontend/requirements.txt`**

```
numpy
pybind11
soundfile
pyqtgraph
PyQt5
```

- [ ] **Step 2: Create the venv and install dependencies**

```bash
python3 -m venv frontend/.venv
frontend/.venv/bin/pip install -r frontend/requirements.txt
```

Expected: all five packages install successfully.

- [ ] **Step 3: Create `engine/bindings/python_bindings.cpp`**

```cpp
#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>

#include <cstring>

#include "sound_viz/engine.h"

namespace py = pybind11;

class PyEngine {
public:
    PyEngine(uint32_t window_size, uint32_t sample_rate) {
        EngineConfig config{};
        config.window_size = window_size;
        config.sample_rate = sample_rate;
        handle_ = create_engine(config);
    }

    ~PyEngine() {
        destroy_engine(handle_);
    }

    void push_samples(py::array_t<float, py::array::c_style | py::array::forcecast> samples,
                       uint32_t n_channels) {
        auto buf = samples.request();
        uint32_t n_frames = static_cast<uint32_t>(buf.size) / n_channels;
        ::push_samples(handle_, static_cast<const float*>(buf.ptr), n_frames, n_channels);
    }

    py::dict get_latest_features() {
        FeatureFrame frame = ::get_latest_features(handle_);

        py::array_t<float> waveform(frame.waveform_len);
        std::memcpy(waveform.mutable_data(), frame.waveform, frame.waveform_len * sizeof(float));

        py::dict result;
        result["frame_index"] = frame.frame_index;
        result["sample_rate"] = frame.sample_rate;
        result["channels"] = frame.channels;
        result["waveform"] = waveform;
        result["rms"] = frame.rms;
        result["zero_crossing_rate"] = frame.zero_crossing_rate;
        result["peak"] = frame.peak;
        result["band_energy_low"] = frame.band_energy_low;
        result["band_energy_mid"] = frame.band_energy_mid;
        result["band_energy_high"] = frame.band_energy_high;
        result["spectral_centroid"] = frame.spectral_centroid;
        return result;
    }

private:
    EngineHandle handle_;
};

PYBIND11_MODULE(sound_viz_py, m) {
    py::class_<PyEngine>(m, "Engine")
        .def(py::init<uint32_t, uint32_t>(), py::arg("window_size"), py::arg("sample_rate"))
        .def("push_samples", &PyEngine::push_samples, py::arg("samples"), py::arg("n_channels") = 1)
        .def("get_latest_features", &PyEngine::get_latest_features);
}
```

- [ ] **Step 4: Modify `engine/CMakeLists.txt`** to build the pybind11
module when pybind11 is available

Append to the end of the file:

```cmake
find_package(pybind11 CONFIG QUIET)
if(pybind11_FOUND)
    pybind11_add_module(sound_viz_py bindings/python_bindings.cpp)
    target_link_libraries(sound_viz_py PRIVATE sound_viz_engine)
endif()
```

- [ ] **Step 5: Reconfigure CMake with the venv's pybind11 and build**

```bash
cmake -S engine -B engine/build -Dpybind11_DIR="$(frontend/.venv/bin/python -m pybind11 --cmakedir)"
cmake --build engine/build
```

Expected: build succeeds and produces a `sound_viz_py*.so` file under
`engine/build/`.

- [ ] **Step 6: Create `engine/tests/python_smoke_test.py`**

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

engine.push_samples(np.array([3.0, 4.0, 5.0, 6.0], dtype=np.float32), 1)
frame2 = engine.get_latest_features()
assert frame2["waveform"].tolist() == [3.0, 4.0, 5.0, 6.0], frame2["waveform"]
assert frame2["frame_index"] == 1

print("python_smoke_test: OK")
```

- [ ] **Step 7: Run the smoke test**

```bash
frontend/.venv/bin/python engine/tests/python_smoke_test.py
```

Expected: prints `python_smoke_test: OK`.

- [ ] **Step 8: Commit**

```bash
git add frontend/requirements.txt engine/bindings/python_bindings.cpp engine/CMakeLists.txt engine/tests/python_smoke_test.py
git commit -m "Add pybind11 bindings and Python smoke test"
```

---

### Task 5: Test WAV fixture generator

**Files:**
- Create: `frontend/scripts/generate_test_tone.py`

- [ ] **Step 1: Create `frontend/scripts/generate_test_tone.py`**

```python
import os

import numpy as np
import soundfile as sf

SAMPLE_RATE = 44100
DURATION_S = 3.0
FREQUENCY_HZ = 440.0

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "test_tone.wav")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    t = np.arange(int(SAMPLE_RATE * DURATION_S)) / SAMPLE_RATE
    waveform = (0.5 * np.sin(2 * np.pi * FREQUENCY_HZ * t)).astype(np.float32)

    sf.write(OUTPUT_PATH, waveform, SAMPLE_RATE)
    print(f"wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it to generate the fixture**

```bash
frontend/.venv/bin/python frontend/scripts/generate_test_tone.py
```

Expected: prints `wrote .../frontend/fixtures/test_tone.wav`. The
`fixtures/` directory is gitignored (Task 1's `.gitignore`), so this file
stays local.

- [ ] **Step 3: Commit**

```bash
git add frontend/scripts/generate_test_tone.py
git commit -m "Add script to generate a test tone WAV fixture"
```

---

### Task 6: Python harness (waveform viewer)

**Files:**
- Create: `frontend/main.py`
- Create: `frontend/scripts/smoke_test_harness.py`

- [ ] **Step 1: Create `frontend/main.py`**

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

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setYRange(-1.0, 1.0)
        self.curve = self.plot_widget.plot(np.zeros(WINDOW_SIZE))
        self.setCentralWidget(self.plot_widget)

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


def main():
    parser = argparse.ArgumentParser(description="Sound visualizer - phase 1a waveform viewer")
    parser.add_argument("wav_path", help="Path to a WAV file")
    args = parser.parse_args()

    app = QtWidgets.QApplication(sys.argv)
    window = WaveformWindow(args.wav_path)
    window.setWindowTitle("Sound Visualizer - Waveform (Phase 1a)")
    window.resize(800, 400)
    window.show()
    app.exec_()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Create `frontend/scripts/smoke_test_harness.py`**

This drives `WaveformWindow` headlessly (no event loop, no visible window)
to verify the wiring works without needing a display.

```python
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys

import numpy as np
from PyQt5 import QtWidgets

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from main import WaveformWindow, WINDOW_SIZE, CHUNK_FRAMES

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "..", "fixtures", "test_tone.wav")

app = QtWidgets.QApplication(sys.argv)
window = WaveformWindow(FIXTURE_PATH)

window.on_tick()
window.on_tick()

curve_x, curve_y = window.curve.getData()
assert len(curve_y) == WINDOW_SIZE
assert np.any(curve_y != 0)
assert window.read_pos == 2 * CHUNK_FRAMES

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
git commit -m "Add pyqtgraph waveform viewer harness"
```

---

### Task 7: End-to-end manual validation

**Files:** none (validation only)

- [ ] **Step 1: Run the full harness with a real display**

```bash
frontend/.venv/bin/python frontend/main.py frontend/fixtures/test_tone.wav
```

Expected: a window titled "Sound Visualizer - Waveform (Phase 1a)" opens,
showing a 440Hz sine wave scrolling/updating in the plot roughly in real
time, with no crashes. Close the window when done — this confirms phase 1a's
goal (validate the end-to-end interface and data flow) is met.

- [ ] **Step 2: Run the full C++ test suite via ctest**

```bash
cd engine/build && ctest --output-on-failure && cd ../..
```

Expected: `ring_buffer_test` and `engine_test` both pass.
