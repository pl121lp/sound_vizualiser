# Phase 2a: Spectrogram + Per-bin Peak-hold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a log-frequency scrolling spectrogram panel and per-bin peak-hold overlay to the Phase 1 visualizer frontend, with no changes to the C++ engine.

**Architecture:** Pure numpy math helpers in `frontend/audio_math.py` are unit-tested with pytest independently of Qt; `SpectrogramPanel` (added to `frontend/main.py`) owns the rolling buffer and `pg.ImageItem`; `WaveformWindow` gains per-bin peak-hold arrays and a `pg.ScatterPlotItem` overlay on the existing spectrum bar plot.

**Tech Stack:** Python/numpy, pyqtgraph (`ImageItem`, `ScatterPlotItem`, `colormap`), pytest

---

### Task 1: Add pytest and test scaffold

**Files:**
- Modify: `frontend/requirements.txt`
- Create: `frontend/tests/__init__.py`

- [ ] **Step 1: Add pytest to `frontend/requirements.txt`**

Append one line:
```
pytest>=7.0
```

- [ ] **Step 2: Install pytest into the venv**

```bash
./frontend/run.sh -m pip install "pytest>=7.0"
```

Expected: `Successfully installed pytest-...`

- [ ] **Step 3: Create the tests package**

```bash
touch frontend/tests/__init__.py
```

- [ ] **Step 4: Commit**

```bash
git add frontend/requirements.txt frontend/tests/__init__.py
git commit -m "chore: add pytest and test scaffold for frontend"
```

---

### Task 2: Create `audio_math.py` with `make_log_freq_grid`

**Files:**
- Create: `frontend/audio_math.py`
- Create: `frontend/tests/test_audio_math.py`

- [ ] **Step 1: Write the failing tests**

Create `frontend/tests/test_audio_math.py`:

```python
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from audio_math import make_log_freq_grid


def test_make_log_freq_grid_shape():
    log_freqs, linear_freqs = make_log_freq_grid(513, 44100.0)
    assert log_freqs.shape == (256,)
    assert linear_freqs.shape == (513,)


def test_make_log_freq_grid_range():
    log_freqs, linear_freqs = make_log_freq_grid(513, 44100.0)
    assert log_freqs[0] == pytest.approx(20.0)
    assert log_freqs[-1] == pytest.approx(22050.0)
    assert linear_freqs[0] == pytest.approx(0.0)
    assert linear_freqs[-1] == pytest.approx(22050.0)


def test_make_log_freq_grid_monotonic():
    log_freqs, linear_freqs = make_log_freq_grid(513, 44100.0)
    assert np.all(np.diff(log_freqs) > 0)
    assert np.all(np.diff(linear_freqs) >= 0)


def test_make_log_freq_grid_custom_n_rows():
    log_freqs, _ = make_log_freq_grid(513, 44100.0, n_rows=128)
    assert log_freqs.shape == (128,)
```

- [ ] **Step 2: Run to verify failure**

```bash
./frontend/run.sh -m pytest frontend/tests/test_audio_math.py -v
```

Expected: `ModuleNotFoundError: No module named 'audio_math'`

- [ ] **Step 3: Create `frontend/audio_math.py`**

```python
import numpy as np


def make_log_freq_grid(
    spectrum_len: int, sample_rate: float, n_rows: int = 256
) -> tuple[np.ndarray, np.ndarray]:
    linear_freqs = np.linspace(0.0, sample_rate / 2.0, spectrum_len)
    log_freqs = np.geomspace(20.0, sample_rate / 2.0, n_rows)
    return log_freqs, linear_freqs
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
./frontend/run.sh -m pytest frontend/tests/test_audio_math.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add frontend/audio_math.py frontend/tests/test_audio_math.py
git commit -m "feat: add make_log_freq_grid with tests"
```

---

### Task 3: Add `to_db_normalized` to `audio_math.py`

**Files:**
- Modify: `frontend/audio_math.py`
- Modify: `frontend/tests/test_audio_math.py`

- [ ] **Step 1: Update the import line in the test file**

Change the existing import at the top of `frontend/tests/test_audio_math.py` from:
```python
from audio_math import make_log_freq_grid
```
to:
```python
from audio_math import make_log_freq_grid, to_db_normalized
```

- [ ] **Step 2: Append the new tests to `frontend/tests/test_audio_math.py`**

```python
def test_to_db_normalized_full_scale():
    result = to_db_normalized(np.array([1.0]))
    assert result[0] == pytest.approx(1.0, abs=1e-3)


def test_to_db_normalized_silence():
    result = to_db_normalized(np.array([0.0]))
    assert result[0] == pytest.approx(0.0, abs=1e-3)


def test_to_db_normalized_midpoint():
    # 0.01 amplitude → -40 dB → 0.5 normalized (db_min=-80, db_max=0)
    result = to_db_normalized(np.array([0.01]))
    assert result[0] == pytest.approx(0.5, abs=0.01)


def test_to_db_normalized_output_range():
    spectrum = np.array([0.0, 0.001, 0.01, 0.1, 1.0])
    result = to_db_normalized(spectrum)
    assert np.all(result >= 0.0)
    assert np.all(result <= 1.0)
```

- [ ] **Step 3: Run to verify the new tests fail**

```bash
./frontend/run.sh -m pytest frontend/tests/test_audio_math.py::test_to_db_normalized_full_scale -v
```

Expected: `ImportError: cannot import name 'to_db_normalized'`

- [ ] **Step 4: Add `to_db_normalized` to `frontend/audio_math.py`**

```python
def to_db_normalized(
    spectrum: np.ndarray, db_min: float = -80.0, db_max: float = 0.0
) -> np.ndarray:
    db = 20.0 * np.log10(np.asarray(spectrum, dtype=np.float64) + 1e-9)
    db = np.clip(db, db_min, db_max)
    return ((db - db_min) / (db_max - db_min)).astype(np.float32)
```

- [ ] **Step 5: Run all tests to verify they pass**

```bash
./frontend/run.sh -m pytest frontend/tests/test_audio_math.py -v
```

Expected: `8 passed`

- [ ] **Step 6: Commit**

```bash
git add frontend/audio_math.py frontend/tests/test_audio_math.py
git commit -m "feat: add to_db_normalized with tests"
```

---

### Task 4: Add `update_peak_hold` to `audio_math.py`

**Files:**
- Modify: `frontend/audio_math.py`
- Modify: `frontend/tests/test_audio_math.py`

- [ ] **Step 1: Update the import line in the test file**

Change:
```python
from audio_math import make_log_freq_grid, to_db_normalized
```
to:
```python
from audio_math import make_log_freq_grid, to_db_normalized, update_peak_hold
```

- [ ] **Step 2: Append the new tests to `frontend/tests/test_audio_math.py`**

```python
def test_update_peak_hold_new_peak():
    spectrum = np.array([0.8, 0.5], dtype=np.float32)
    peak_values = np.array([0.5, 0.6], dtype=np.float32)
    peak_timers = np.array([0.5, 0.5], dtype=np.float32)
    new_vals, new_timers = update_peak_hold(spectrum, peak_values, peak_timers, dt=0.1)
    assert new_vals[0] == pytest.approx(0.8)    # updated to new peak
    assert new_timers[0] == pytest.approx(0.0)  # timer reset
    assert new_vals[1] == pytest.approx(0.6)    # unchanged (0.5 < 0.6)
    assert new_timers[1] == pytest.approx(0.6)  # timer incremented


def test_update_peak_hold_within_hold_period():
    spectrum = np.array([0.3], dtype=np.float32)
    peak_values = np.array([0.8], dtype=np.float32)
    peak_timers = np.array([0.5], dtype=np.float32)
    new_vals, new_timers = update_peak_hold(
        spectrum, peak_values, peak_timers, dt=0.1, hold_secs=1.0
    )
    assert new_vals[0] == pytest.approx(0.8)    # no decay yet
    assert new_timers[0] == pytest.approx(0.6)  # timer incremented


def test_update_peak_hold_decay_after_hold():
    spectrum = np.array([0.3], dtype=np.float32)
    peak_values = np.array([0.8], dtype=np.float32)
    peak_timers = np.array([1.0], dtype=np.float32)
    new_vals, new_timers = update_peak_hold(
        spectrum, peak_values, peak_timers, dt=0.1, hold_secs=1.0, decay_per_sec=1.0
    )
    assert new_vals[0] == pytest.approx(0.7, abs=1e-5)   # decayed by 0.1
    assert new_timers[0] == pytest.approx(1.1, abs=1e-5)  # timer kept incrementing


def test_update_peak_hold_decay_clamps_to_spectrum():
    spectrum = np.array([0.3], dtype=np.float32)
    peak_values = np.array([0.35], dtype=np.float32)
    peak_timers = np.array([2.0], dtype=np.float32)
    new_vals, _ = update_peak_hold(
        spectrum, peak_values, peak_timers, dt=0.1, hold_secs=1.0, decay_per_sec=1.0
    )
    assert new_vals[0] == pytest.approx(0.3)  # clamped: 0.35 - 0.1 = 0.25 < 0.3


def test_update_peak_hold_does_not_mutate_inputs():
    spectrum = np.array([0.8], dtype=np.float32)
    peak_values = np.array([0.5], dtype=np.float32)
    peak_timers = np.array([0.0], dtype=np.float32)
    orig_peak = peak_values.copy()
    orig_timer = peak_timers.copy()
    update_peak_hold(spectrum, peak_values, peak_timers, dt=0.1)
    np.testing.assert_array_equal(peak_values, orig_peak)
    np.testing.assert_array_equal(peak_timers, orig_timer)
```

- [ ] **Step 3: Run to verify the new tests fail**

```bash
./frontend/run.sh -m pytest frontend/tests/test_audio_math.py::test_update_peak_hold_new_peak -v
```

Expected: `ImportError: cannot import name 'update_peak_hold'`

- [ ] **Step 4: Add `update_peak_hold` to `frontend/audio_math.py`**

```python
def update_peak_hold(
    spectrum: np.ndarray,
    peak_values: np.ndarray,
    peak_timers: np.ndarray,
    dt: float,
    hold_secs: float = 1.0,
    decay_per_sec: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    spectrum = np.asarray(spectrum)
    peak_values = peak_values.copy()
    peak_timers = peak_timers.copy()

    new_peak = spectrum >= peak_values
    peak_values[new_peak] = spectrum[new_peak]
    peak_timers[new_peak] = 0.0

    peak_timers[~new_peak] += dt
    decaying = (~new_peak) & (peak_timers > hold_secs)
    peak_values[decaying] = np.maximum(
        spectrum[decaying],
        peak_values[decaying] - decay_per_sec * dt,
    )

    return peak_values, peak_timers
```

- [ ] **Step 5: Run all tests to verify they pass**

```bash
./frontend/run.sh -m pytest frontend/tests/test_audio_math.py -v
```

Expected: `13 passed`

- [ ] **Step 6: Commit**

```bash
git add frontend/audio_math.py frontend/tests/test_audio_math.py
git commit -m "feat: add update_peak_hold with tests"
```

---

### Task 5: Add `SpectrogramPanel` class to `main.py`

**Files:**
- Modify: `frontend/main.py`

No unit tests (widget requires a running Qt event loop). Verified visually in Task 7.

- [ ] **Step 1: Add import of `audio_math` helpers at the top of `main.py`**

After the existing `import sound_viz_py` line (line 11), add:

```python
from audio_math import make_log_freq_grid, to_db_normalized, update_peak_hold
```

- [ ] **Step 2: Insert `SpectrogramPanel` class before `BarMeter`**

Insert the following class between the `PEAK_DECAY_PER_SECOND = 1.0` constant (line 15) and the `class BarMeter` definition (line 17). Leave a blank line before and after:

```python
class SpectrogramPanel(QtWidgets.QWidget):
    def __init__(self, spectrum_len: int, sample_rate: float, update_rate: float):
        super().__init__()

        n_freq_rows = 256
        history_cols = max(1, int(np.ceil(update_rate * 5.0)))

        self._log_freqs, self._linear_freqs = make_log_freq_grid(
            spectrum_len, sample_rate, n_freq_rows
        )
        self._buffer = np.zeros((history_cols, n_freq_rows), dtype=np.float32)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._plot = pg.PlotWidget()
        self._plot.setLabel("left", "Frequency (Hz)")
        self._plot.setLabel("bottom", "Time →")
        self._plot.setMouseEnabled(x=False, y=False)
        self._plot.hideAxis("bottom")

        cm = pg.colormap.get("inferno")
        self._image = pg.ImageItem()
        self._image.setColorMap(cm)
        self._image.setLevels([0.0, 1.0])
        self._plot.addItem(self._image)

        layout.addWidget(self._plot)
        self.setMinimumHeight(150)

    def update(self, spectrum: np.ndarray) -> None:
        col = to_db_normalized(
            np.interp(self._log_freqs, self._linear_freqs, spectrum).astype(np.float32)
        )
        self._buffer = np.roll(self._buffer, -1, axis=0)
        self._buffer[-1] = col
        self._image.setImage(self._buffer)
```

- [ ] **Step 3: Commit**

```bash
git add frontend/main.py
git commit -m "feat: add SpectrogramPanel widget"
```

---

### Task 6: Wire `SpectrogramPanel` and per-bin peak-hold into `WaveformWindow`

**Files:**
- Modify: `frontend/main.py`

- [ ] **Step 1: Instantiate `SpectrogramPanel` in `WaveformWindow.__init__`**

Find the line `self.peak_hold_timer = 0.0` (search for it — line numbers shifted after Task 5). Add immediately after it:

```python
        self.spectrogram = SpectrogramPanel(self.spectrum_len, sample_rate, args.update_rate)
```

- [ ] **Step 2: Add per-bin peak-hold state and overlay**

Directly after the `self.spectrogram = ...` line just added, add:

```python
        self.peak_hold_spectrum = np.zeros(self.spectrum_len, dtype=np.float32)
        self.peak_hold_timer_spectrum = np.zeros(self.spectrum_len, dtype=np.float32)
        self.peak_hold_dots = pg.ScatterPlotItem(
            x=np.arange(self.spectrum_len),
            y=self.peak_hold_spectrum,
            pen=None,
            brush=pg.mkBrush("r"),
            size=3,
        )
        self.spectrum_plot.addItem(self.peak_hold_dots)
```

- [ ] **Step 3: Add `self.spectrogram` to the layout with stretch factor**

Find the layout block in `WaveformWindow.__init__` (around line 123). Change:

```python
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        layout.addWidget(self.waveform_plot)
        layout.addWidget(self.spectrum_plot)
```

to:

```python
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        layout.addWidget(self.waveform_plot, stretch=1)
        layout.addWidget(self.spectrum_plot, stretch=1)
        layout.addWidget(self.spectrogram, stretch=2)
```

- [ ] **Step 4: Update `on_tick` to drive the spectrogram and per-bin peak-hold**

In `on_tick`, after the entire spectrum auto-range `if` block (i.e., after the closing line of `if spectrum_peak > self.spectrum_max: ...`) and before `self.rms_meter.update_value(...)`, add (at the same indentation level as the `if`):

```python
        self.spectrogram.update(frame["spectrum"])

        spectrum = np.asarray(frame["spectrum"], dtype=np.float32)
        self.peak_hold_spectrum, self.peak_hold_timer_spectrum = update_peak_hold(
            spectrum,
            self.peak_hold_spectrum,
            self.peak_hold_timer_spectrum,
            self.tick_interval_s,
            PEAK_HOLD_SECONDS,
            PEAK_DECAY_PER_SECOND,
        )
        self.peak_hold_dots.setData(
            x=np.arange(self.spectrum_len),
            y=self.peak_hold_spectrum,
        )
```

- [ ] **Step 5: Commit**

```bash
git add frontend/main.py
git commit -m "feat: wire SpectrogramPanel and per-bin peak-hold into WaveformWindow"
```

---

### Task 7: Smoke test

**Files:** none

- [ ] **Step 1: Run all unit tests**

```bash
./frontend/run.sh -m pytest frontend/tests/ -v
```

Expected: `13 passed`

- [ ] **Step 2: Run the visualizer**

```bash
./frontend/run.sh frontend/main.py frontend/fixtures/test_tone.wav
```

Verify:
- A spectrogram panel appears below the spectrum bar plot, roughly twice as tall as the other two plots
- The spectrogram scrolls leftward as audio plays; bright horizontal bands appear at the frequencies present in the test tone
- Red dots appear on the spectrum bar plot at the per-bin peak values, hold for ~1 second after the peak, then decay downward

- [ ] **Step 3: Commit any fixes**

If cosmetic issues were fixed during the smoke test:

```bash
git add frontend/main.py
git commit -m "fix: cosmetic adjustments from phase 2a smoke test"
```
