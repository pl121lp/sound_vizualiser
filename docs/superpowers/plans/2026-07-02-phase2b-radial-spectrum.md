# Phase 2b: Radial/Circular Spectrum Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a radial/circular spectrum panel to the Phase 1/2a visualizer frontend, mapping FFT bins around a circle with peak-hold markers, with no changes to the C++ engine.

**Architecture:** Pure numpy math helpers (`make_radial_angles`, `polar_bar_endpoints`) are added to `frontend/audio_math.py` and unit-tested with pytest independently of Qt. A new `RadialSpectrumPanel` widget (added to `frontend/main.py`, following the same shape as the existing `SpectrogramPanel`) owns the `pg.PlotWidget`/`pg.PlotCurveItem`/`pg.ScatterPlotItem` and does the log-frequency interpolation + polar mapping each tick. `WaveformWindow` instantiates it, adds it to the layout, and feeds it the spectrum plus the peak-hold array it already maintains — no new peak-hold state.

**Tech Stack:** Python/numpy, pyqtgraph (`PlotCurveItem` with `connect='pairs'`, `ScatterPlotItem`), pytest

## Global Constraints

- Radial view uses log-frequency binning via the existing `make_log_freq_grid`, with `n_bins = 256` (matches spectrogram's `n_freq_rows`).
- `inner_radius = 0.3`, `bar_scale = 1.0` — fixed constants, not configurable in this phase.
- Bin 0 (lowest frequency) sits at 12 o'clock (angle `pi/2` in `pg.PlotWidget`'s y-up Cartesian system); increasing bin index sweeps clockwise.
- Reuse `WaveformWindow.peak_hold_spectrum` (already computed for the linear bar plot) for the radial peak-hold markers — no duplicate peak-hold state or decay logic.
- `RadialSpectrumPanel` must be a self-contained widget with the same `__init__(spectrum_len, sample_rate, ...)` / `update(...)` shape as `SpectrogramPanel`, with no back-references into `WaveformWindow`, so Phase 2d can later show/hide/reorder panels without restructuring.

---

### Task 1: Add `make_radial_angles` to `audio_math.py`

**Files:**
- Modify: `frontend/audio_math.py`
- Modify: `frontend/tests/test_audio_math.py`

**Interfaces:**
- Produces: `make_radial_angles(n_bins: int) -> tuple[np.ndarray, np.ndarray]` — returns `(cos_angles, sin_angles)`, each shape `(n_bins,)`, `float64` (numpy default from `np.cos`/`np.sin`).

- [ ] **Step 1: Update the import line in the test file**

Change the existing import at the top of `frontend/tests/test_audio_math.py` from:
```python
from audio_math import make_log_freq_grid, to_db_normalized, update_peak_hold
```
to:
```python
from audio_math import make_log_freq_grid, make_radial_angles, to_db_normalized, update_peak_hold
```

- [ ] **Step 2: Append the new tests to `frontend/tests/test_audio_math.py`**

```python
def test_make_radial_angles_shape():
    cos_angles, sin_angles = make_radial_angles(4)
    assert cos_angles.shape == (4,)
    assert sin_angles.shape == (4,)


def test_make_radial_angles_bin0_at_top():
    cos_angles, sin_angles = make_radial_angles(4)
    assert cos_angles[0] == pytest.approx(0.0, abs=1e-6)
    assert sin_angles[0] == pytest.approx(1.0, abs=1e-6)


def test_make_radial_angles_sweeps_clockwise():
    # With bin 0 at 12 o'clock, bin 1 (of 4) should land at 3 o'clock if the
    # sweep is clockwise.
    cos_angles, sin_angles = make_radial_angles(4)
    assert cos_angles[1] == pytest.approx(1.0, abs=1e-6)
    assert sin_angles[1] == pytest.approx(0.0, abs=1e-6)


def test_make_radial_angles_unit_circle():
    cos_angles, sin_angles = make_radial_angles(37)
    np.testing.assert_allclose(cos_angles**2 + sin_angles**2, 1.0, atol=1e-10)
```

- [ ] **Step 3: Run to verify the new tests fail**

```bash
./frontend/run.sh -m pytest frontend/tests/test_audio_math.py::test_make_radial_angles_shape -v
```

Expected: `ImportError: cannot import name 'make_radial_angles'`

- [ ] **Step 4: Add `make_radial_angles` to `frontend/audio_math.py`**

Append to the end of `frontend/audio_math.py`:

```python
def make_radial_angles(n_bins: int) -> tuple[np.ndarray, np.ndarray]:
    angles = np.pi / 2 - 2 * np.pi * np.arange(n_bins) / n_bins
    return np.cos(angles), np.sin(angles)
```

- [ ] **Step 5: Run all tests to verify they pass**

```bash
./frontend/run.sh -m pytest frontend/tests/test_audio_math.py -v
```

Expected: `17 passed`

- [ ] **Step 6: Commit**

```bash
git add frontend/audio_math.py frontend/tests/test_audio_math.py
git commit -m "feat: add make_radial_angles with tests"
```

---

### Task 2: Add `polar_bar_endpoints` to `audio_math.py`

**Files:**
- Modify: `frontend/audio_math.py`
- Modify: `frontend/tests/test_audio_math.py`

**Interfaces:**
- Consumes: nothing from Task 1's function directly (tests pass in hand-built `cos_angles`/`sin_angles` arrays to keep the test isolated), but `RadialSpectrumPanel` (Task 3) will chain `make_radial_angles` output straight into this function.
- Produces: `polar_bar_endpoints(normalized_magnitudes: np.ndarray, cos_angles: np.ndarray, sin_angles: np.ndarray, inner_radius: float = 0.3, bar_scale: float = 1.0) -> tuple[np.ndarray, np.ndarray]` — returns `(x, y)`, each shape `(2*n,)`, `float32`, laid out as `[inner_0, outer_0, inner_1, outer_1, ...]` for `pg.PlotCurveItem(connect='pairs')`.

- [ ] **Step 1: Update the import line in the test file**

Change:
```python
from audio_math import make_log_freq_grid, make_radial_angles, to_db_normalized, update_peak_hold
```
to:
```python
from audio_math import (
    make_log_freq_grid,
    make_radial_angles,
    polar_bar_endpoints,
    to_db_normalized,
    update_peak_hold,
)
```

- [ ] **Step 2: Append the new tests to `frontend/tests/test_audio_math.py`**

```python
def test_polar_bar_endpoints_shape():
    mags = np.array([0.1, 0.5, 0.9], dtype=np.float32)
    cos_angles = np.array([1.0, 0.0, -1.0], dtype=np.float32)
    sin_angles = np.array([0.0, 1.0, 0.0], dtype=np.float32)
    x, y = polar_bar_endpoints(mags, cos_angles, sin_angles)
    assert x.shape == (6,)
    assert y.shape == (6,)


def test_polar_bar_endpoints_zero_magnitude_matches_inner_radius():
    mags = np.array([0.0, 0.0], dtype=np.float32)
    cos_angles = np.array([1.0, 0.0], dtype=np.float32)
    sin_angles = np.array([0.0, 1.0], dtype=np.float32)
    x, y = polar_bar_endpoints(mags, cos_angles, sin_angles, inner_radius=0.3, bar_scale=1.0)
    # Zero magnitude -> outer point coincides with inner point (spoke length 0).
    np.testing.assert_allclose(x[0::2], x[1::2], atol=1e-6)
    np.testing.assert_allclose(y[0::2], y[1::2], atol=1e-6)


def test_polar_bar_endpoints_full_magnitude_reaches_inner_plus_scale():
    mags = np.array([1.0, 1.0], dtype=np.float32)
    cos_angles = np.array([1.0, 0.0], dtype=np.float32)
    sin_angles = np.array([0.0, 1.0], dtype=np.float32)
    x, y = polar_bar_endpoints(mags, cos_angles, sin_angles, inner_radius=0.3, bar_scale=1.0)
    outer_radius = np.hypot(x[1::2], y[1::2])
    np.testing.assert_allclose(outer_radius, 1.3, atol=1e-6)


def test_polar_bar_endpoints_single_bin_exact_position():
    mags = np.array([0.5], dtype=np.float32)
    cos_angles = np.array([0.0], dtype=np.float32)  # bin at 12 o'clock (angle pi/2)
    sin_angles = np.array([1.0], dtype=np.float32)
    x, y = polar_bar_endpoints(mags, cos_angles, sin_angles, inner_radius=0.3, bar_scale=1.0)
    # inner point at (0, 0.3), outer point at (0, 0.3 + 0.5) = (0, 0.8)
    np.testing.assert_allclose(x, [0.0, 0.0], atol=1e-6)
    np.testing.assert_allclose(y, [0.3, 0.8], atol=1e-6)
```

- [ ] **Step 3: Run to verify the new tests fail**

```bash
./frontend/run.sh -m pytest frontend/tests/test_audio_math.py::test_polar_bar_endpoints_shape -v
```

Expected: `ImportError: cannot import name 'polar_bar_endpoints'`

- [ ] **Step 4: Add `polar_bar_endpoints` to `frontend/audio_math.py`**

Append to the end of `frontend/audio_math.py`:

```python
def polar_bar_endpoints(
    normalized_magnitudes: np.ndarray,
    cos_angles: np.ndarray,
    sin_angles: np.ndarray,
    inner_radius: float = 0.3,
    bar_scale: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    normalized_magnitudes = np.asarray(normalized_magnitudes)
    outer_radius = inner_radius + normalized_magnitudes * bar_scale
    n = len(normalized_magnitudes)
    x = np.empty(2 * n, dtype=np.float32)
    y = np.empty(2 * n, dtype=np.float32)
    x[0::2] = inner_radius * cos_angles
    y[0::2] = inner_radius * sin_angles
    x[1::2] = outer_radius * cos_angles
    y[1::2] = outer_radius * sin_angles
    return x, y
```

- [ ] **Step 5: Run all tests to verify they pass**

```bash
./frontend/run.sh -m pytest frontend/tests/test_audio_math.py -v
```

Expected: `21 passed`

- [ ] **Step 6: Commit**

```bash
git add frontend/audio_math.py frontend/tests/test_audio_math.py
git commit -m "feat: add polar_bar_endpoints with tests"
```

---

### Task 3: Add `RadialSpectrumPanel` class to `main.py`

**Files:**
- Modify: `frontend/main.py`

**Interfaces:**
- Consumes: `make_log_freq_grid(spectrum_len, sample_rate, n_rows) -> (log_freqs, linear_freqs)`, `make_radial_angles(n_bins) -> (cos_angles, sin_angles)`, `to_db_normalized(spectrum) -> np.ndarray`, `polar_bar_endpoints(normalized_magnitudes, cos_angles, sin_angles, inner_radius, bar_scale) -> (x, y)` — all from `frontend/audio_math.py` (Tasks 1–2 and prior phases).
- Produces: `RadialSpectrumPanel(spectrum_len: int, sample_rate: float, n_bins: int = 256)` with `.update(spectrum: np.ndarray, peak_hold_spectrum: np.ndarray) -> None`. Task 4 instantiates and drives this.

No unit tests (widget requires a running Qt event loop). Verified visually in Task 5.

- [ ] **Step 1: Update the `audio_math` import in `main.py`**

Change line 12:
```python
from audio_math import make_log_freq_grid, to_db_normalized, update_peak_hold
```
to:
```python
from audio_math import (
    make_log_freq_grid,
    make_radial_angles,
    polar_bar_endpoints,
    to_db_normalized,
    update_peak_hold,
)
```

- [ ] **Step 2: Insert `RadialSpectrumPanel` class after `SpectrogramPanel`**

`SpectrogramPanel` currently ends with the `update` method's `self._image.setImage(self._buffer)` line, followed by two blank lines and then `class BarMeter(QtWidgets.QWidget):`. Insert the new class in that gap, keeping one blank line before and after it (so there are still two blank lines separating each class):

```python
class RadialSpectrumPanel(QtWidgets.QWidget):
    def __init__(self, spectrum_len: int, sample_rate: float, n_bins: int = 256):
        super().__init__()

        self._log_freqs, self._linear_freqs = make_log_freq_grid(
            spectrum_len, sample_rate, n_bins
        )
        self._cos_angles, self._sin_angles = make_radial_angles(n_bins)
        self._inner_radius = 0.3
        self._bar_scale = 1.0

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._plot = pg.PlotWidget()
        self._plot.setAspectLocked(True)
        self._plot.hideAxis("left")
        self._plot.hideAxis("bottom")
        self._plot.setMouseEnabled(x=False, y=False)

        self._spokes = pg.PlotCurveItem(pen=pg.mkPen("c", width=1), connect="pairs")
        self._plot.addItem(self._spokes)

        self._peak_dots = pg.ScatterPlotItem(pen=None, brush=pg.mkBrush("r"), size=3)
        self._plot.addItem(self._peak_dots)

        layout.addWidget(self._plot)
        self.setMinimumHeight(150)

    def update(self, spectrum: np.ndarray, peak_hold_spectrum: np.ndarray) -> None:
        magnitude = to_db_normalized(
            np.interp(self._log_freqs, self._linear_freqs, spectrum).astype(np.float32)
        )
        peak = to_db_normalized(
            np.interp(
                self._log_freqs, self._linear_freqs, peak_hold_spectrum
            ).astype(np.float32)
        )

        x, y = polar_bar_endpoints(
            magnitude, self._cos_angles, self._sin_angles, self._inner_radius, self._bar_scale
        )
        self._spokes.setData(x, y)

        peak_x, peak_y = polar_bar_endpoints(
            peak, self._cos_angles, self._sin_angles, self._inner_radius, self._bar_scale
        )
        self._peak_dots.setData(x=peak_x[1::2], y=peak_y[1::2])
```

- [ ] **Step 3: Commit**

```bash
git add frontend/main.py
git commit -m "feat: add RadialSpectrumPanel widget"
```

---

### Task 4: Wire `RadialSpectrumPanel` into `WaveformWindow`

**Files:**
- Modify: `frontend/main.py`

**Interfaces:**
- Consumes: `RadialSpectrumPanel(spectrum_len, sample_rate, n_bins=256)` / `.update(spectrum, peak_hold_spectrum)` from Task 3; `WaveformWindow.peak_hold_spectrum` (existing, set earlier in `__init__` and updated each tick in `on_tick`).

- [ ] **Step 1: Instantiate `RadialSpectrumPanel` in `WaveformWindow.__init__`**

Find the line `self.spectrum_plot.addItem(self.peak_hold_dots)` (the last line of the per-bin peak-hold block, right before the blank line preceding `container = QtWidgets.QWidget()`). Add immediately after it:

```python
        self.radial_spectrum = RadialSpectrumPanel(self.spectrum_len, sample_rate)
```

- [ ] **Step 2: Add `self.radial_spectrum` to the layout with a stretch factor**

Find:
```python
        layout.addWidget(self.waveform_plot, stretch=1)
        layout.addWidget(self.spectrum_plot, stretch=1)
        layout.addWidget(self.spectrogram, stretch=2)
```

Change to:
```python
        layout.addWidget(self.waveform_plot, stretch=1)
        layout.addWidget(self.spectrum_plot, stretch=1)
        layout.addWidget(self.spectrogram, stretch=2)
        layout.addWidget(self.radial_spectrum, stretch=2)
```

- [ ] **Step 3: Update `on_tick` to drive the radial panel**

Find the end of the per-bin peak-hold block in `on_tick`:
```python
        self.peak_hold_dots.setData(
            x=np.arange(self.spectrum_len),
            y=self.peak_hold_spectrum,
        )
```

Add immediately after it (same indentation), before the `self.rms_meter.update_value(...)` line:

```python
        self.radial_spectrum.update(spectrum, self.peak_hold_spectrum)
```

- [ ] **Step 4: Commit**

```bash
git add frontend/main.py
git commit -m "feat: wire RadialSpectrumPanel into WaveformWindow"
```

---

### Task 5: Smoke test

**Files:** none

- [ ] **Step 1: Run all unit tests**

```bash
./frontend/run.sh -m pytest frontend/tests/ -v
```

Expected: `21 passed`

- [ ] **Step 2: Run the visualizer**

```bash
./frontend/run.sh frontend/main.py frontend/fixtures/test_tone.wav
```

Verify:
- A radial/circular spectrum panel appears below the spectrogram, roughly the same height as the spectrogram.
- The panel shows spokes radiating from a small central hole outward; spoke lengths track the live spectrum, with the loudest frequencies producing the longest spokes.
- Red dots appear at the tip of each spoke's peak position, hold for ~1 second after the peak, then decay inward — mirroring the peak-hold dots on the linear spectrum bar plot above it.
- The lowest-frequency bin's spoke is at 12 o'clock, and sweeping clockwise moves toward higher frequencies.
- Resizing the window keeps the radial panel circular (not stretched into an ellipse).

- [ ] **Step 3: Commit any fixes**

If cosmetic issues were fixed during the smoke test:

```bash
git add frontend/main.py
git commit -m "fix: cosmetic adjustments from phase 2b smoke test"
```
