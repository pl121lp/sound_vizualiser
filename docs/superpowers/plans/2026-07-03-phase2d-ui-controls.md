# Phase 2d UI Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a toolbar to `WaveformWindow` with checkable visualization-panel toggles and an update-rate slider, both mouse- and keyboard-driven, so the user can choose what's shown and how fast it refreshes without restarting the app.

**Architecture:** A pure helper `rate_hz_to_chunk_frames` in `frontend/audio_math.py` (unit-tested) replaces the inline chunk-size math in `WaveformWindow.__init__` so construction-time and runtime rate changes share one code path. `WaveformWindow` gains a `build_toolbar` method that adds 5 checkable `QAction`s (number-key shortcuts `1`-`5`) and a `QSlider` (range 5-60 Hz, step 5, `Up`/`Down` arrow shortcuts) to a `QToolBar`. Toggling an action flips a boolean flag and calls `setVisible` on the matching widget; `on_tick` checks these flags to skip per-panel work entirely while hidden. The engine itself is untouched — confirmed in the design doc that `update_rate_hz` is advisory-only and never read by the C++ engine.

**Tech Stack:** Python, PyQt5 (`QToolBar`, `QAction`, `QSlider`, `QWidgetAction` not needed — plain `toolbar.addWidget` suffices), pyqtgraph (unchanged), pytest.

## Global Constraints

- No changes to `engine/` (C++) or the pybind11 bindings — this phase is 100% frontend (per spec section "Phase 2 — Visualization breadth + interactivity", item 2d, and confirmed in the design doc).
- Analysis window size (`window_size`) and FFT window type stay CLI-only, unchanged from Phase 1d — no runtime control for these in this phase.
- Rate slider range is 5-60 Hz, step 5 (per design doc, user-confirmed).
- Meters are toggled as one unit (all 7 `BarMeter`s together), not individually.
- No new dependencies — use only `PyQt5.QtWidgets`/`QtGui`/`QtCore` classes already available via the existing `PyQt5` install.
- Restart/loop playback buttons and mic-input source selection are explicitly out of scope for this phase (tracked separately in `todo.txt`).
- Run all commands through `./frontend/run.sh` (uses the project's venv) from the repo root `/home/pl/gitprojects/sound_vizualiser`.

---

### Task 1: Add `rate_hz_to_chunk_frames` to `audio_math.py`

**Files:**
- Modify: `frontend/audio_math.py`
- Test: `frontend/tests/test_audio_math.py`

**Interfaces:**
- Produces: `rate_hz_to_chunk_frames(sample_rate: float, rate_hz: float) -> int`. Task 2 replaces `WaveformWindow.__init__`'s inline chunk-size math with a call to this function; Task 4's `on_rate_changed` also calls it.

- [ ] **Step 1: Write the failing tests**

In `frontend/tests/test_audio_math.py`, find the import block:
```python
from audio_math import (
    make_log_freq_grid,
    make_radial_angles,
    polar_bar_endpoints,
    to_db_normalized,
    update_peak_hold,
)
```
Change to:
```python
from audio_math import (
    make_log_freq_grid,
    make_radial_angles,
    polar_bar_endpoints,
    rate_hz_to_chunk_frames,
    to_db_normalized,
    update_peak_hold,
)
```

Then append at the end of the file:
```python


def test_rate_hz_to_chunk_frames_typical():
    assert rate_hz_to_chunk_frames(44100.0, 30.0) == 1470


def test_rate_hz_to_chunk_frames_low_rate_large_chunk():
    assert rate_hz_to_chunk_frames(44100.0, 5.0) == 8820


def test_rate_hz_to_chunk_frames_floors_at_one_frame():
    assert rate_hz_to_chunk_frames(44100.0, 100000.0) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
./frontend/run.sh -m pytest frontend/tests/test_audio_math.py -v
```

Expected: `ImportError: cannot import name 'rate_hz_to_chunk_frames' from 'audio_math'` (collection error, all tests in the file fail to collect).

- [ ] **Step 3: Implement the function**

Append to the end of `frontend/audio_math.py`:
```python


def rate_hz_to_chunk_frames(sample_rate: float, rate_hz: float) -> int:
    return max(1, round(sample_rate / rate_hz))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
./frontend/run.sh -m pytest frontend/tests/test_audio_math.py -v
```

Expected: `24 passed` (21 existing + 3 new).

- [ ] **Step 5: Commit**

```bash
git add frontend/audio_math.py frontend/tests/test_audio_math.py
git commit -m "feat: add rate_hz_to_chunk_frames with tests"
```

---

### Task 2: Wire `rate_hz_to_chunk_frames` into `WaveformWindow.__init__`

**Files:**
- Modify: `frontend/main.py`

**Interfaces:**
- Consumes: `rate_hz_to_chunk_frames(sample_rate, rate_hz) -> int` from Task 1.
- Produces: `self.rate_hz` (float) on `WaveformWindow`, holding the currently active update rate. Task 4's `build_toolbar`/`on_rate_changed` read and update it.

- [ ] **Step 1: Add the import**

Find:
```python
from audio_math import (
    make_log_freq_grid,
    make_radial_angles,
    polar_bar_endpoints,
    to_db_normalized,
    update_peak_hold,
)
```
Change to:
```python
from audio_math import (
    make_log_freq_grid,
    make_radial_angles,
    polar_bar_endpoints,
    rate_hz_to_chunk_frames,
    to_db_normalized,
    update_peak_hold,
)
```

- [ ] **Step 2: Replace the inline chunk-size calculation**

Find, in `WaveformWindow.__init__`:
```python
        self.window_size = args.window_size
        self.spectrum_len = self.window_size // 2 + 1
        self.chunk_frames = max(1, round(sample_rate / args.update_rate))
```
Change to:
```python
        self.window_size = args.window_size
        self.spectrum_len = self.window_size // 2 + 1
        self.rate_hz = args.update_rate
        self.chunk_frames = rate_hz_to_chunk_frames(sample_rate, self.rate_hz)
```

- [ ] **Step 3: Run the full test suite (regression check)**

```bash
./frontend/run.sh -m pytest frontend/tests/ -v
```

Expected: `24 passed`.

- [ ] **Step 4: Run the existing smoke test harness (regression check)**

```bash
./frontend/run.sh frontend/scripts/smoke_test_harness.py
```

Expected: `smoke_test_harness: OK` (confirms chunk-size math still produces identical behavior after the refactor).

- [ ] **Step 5: Commit**

```bash
git add frontend/main.py
git commit -m "refactor: use rate_hz_to_chunk_frames in WaveformWindow.__init__"
```

---

### Task 3: Toolbar panel-toggle actions, visibility flags, `on_tick` gating

**Files:**
- Modify: `frontend/main.py`

**Interfaces:**
- Consumes: existing `self.waveform_plot`, `self.spectrum_plot`, `self.spectrogram`, `self.radial_spectrum` widgets; `self.meters_container` (new in this task, wraps the existing meters row).
- Produces: `self.show_waveform` / `self.show_spectrum` / `self.show_spectrogram` / `self.show_radial` / `self.show_meters` booleans; `self.panel_actions` dict (`flag_attr -> QAction`); `build_toolbar()` method; `on_panel_toggled(checked: bool, widget: QtWidgets.QWidget, flag_attr: str)` method. Task 4 extends `build_toolbar()` with the rate slider.

- [ ] **Step 1: Wrap the meters row in a container widget**

Find:
```python
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
```
Change to:
```python
        self.meters_container = QtWidgets.QWidget()
        meters_layout = QtWidgets.QHBoxLayout(self.meters_container)
        meters_layout.setContentsMargins(0, 0, 0, 0)
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
        layout.addWidget(self.meters_container)
```

A `QWidget` (unlike a bare `QLayout`) supports `.setVisible()`, which is required to toggle the whole meters row as one unit.

- [ ] **Step 2: Add `build_toolbar` and `on_panel_toggled` methods**

Find the `closeEvent` method:
```python
    def closeEvent(self, event):
```
Add immediately before it (same indentation level, inside `WaveformWindow`):
```python
    def build_toolbar(self):
        toolbar = self.addToolBar("Controls")
        toolbar.setMovable(False)

        panel_specs = [
            ("Waveform", "1", self.waveform_plot, "show_waveform"),
            ("Spectrum", "2", self.spectrum_plot, "show_spectrum"),
            ("Spectrogram", "3", self.spectrogram, "show_spectrogram"),
            ("Radial", "4", self.radial_spectrum, "show_radial"),
            ("Meters", "5", self.meters_container, "show_meters"),
        ]
        self.panel_actions = {}
        for label, key, widget, flag_attr in panel_specs:
            action = QtWidgets.QAction(label, self)
            action.setCheckable(True)
            action.setShortcut(QtGui.QKeySequence(key))
            action.toggled.connect(
                lambda checked, w=widget, attr=flag_attr: self.on_panel_toggled(checked, w, attr)
            )
            action.setChecked(True)
            toolbar.addAction(action)
            self.panel_actions[flag_attr] = action

    def on_panel_toggled(self, checked, widget, flag_attr):
        widget.setVisible(checked)
        setattr(self, flag_attr, checked)

```

`action.toggled.connect(...)` runs before `action.setChecked(True)` so that the initial `True` state flows through the exact same `on_panel_toggled` path as later user clicks — no separate flag-initialization code needed. `QAction.setShortcut` defaults to `Qt.WindowShortcut` context, so `1`-`5` work regardless of which child widget currently has focus.

- [ ] **Step 3: Call `build_toolbar()` at the end of `__init__`**

Find:
```python
        interval_ms = max(1, int(1000 * self.chunk_frames / sample_rate))
        self.tick_interval_s = interval_ms / 1000.0
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.on_tick)
        self.timer.start(interval_ms)
```
Change to:
```python
        interval_ms = max(1, int(1000 * self.chunk_frames / sample_rate))
        self.tick_interval_s = interval_ms / 1000.0
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.on_tick)
        self.timer.start(interval_ms)

        self.build_toolbar()
```

`build_toolbar()` must run after `self.timer` exists because Task 4's rate slider setup (added to `build_toolbar` in the next task) calls `self.timer.setInterval(...)` during its initial sync. Placing it here also guarantees it runs after every widget it references (`self.meters_container` etc.) has already been constructed. It's still safe before `self.show()`/`app.exec_()` — no tick can fire until the Qt event loop actually starts.

- [ ] **Step 4: Gate `on_tick` behind the visibility flags**

Find the entire `on_tick` method:
```python
    def on_tick(self):
        if self.read_pos >= len(self.data):
            self.timer.stop()
            return

        chunk = self.data[self.read_pos:self.read_pos + self.chunk_frames]
        self.read_pos += self.chunk_frames

        flat = chunk.reshape(-1).astype(np.float32)
        self.engine.push_samples(flat, self.n_channels)

        frame = self.engine.get_latest_features()
        self.curve.setData(frame["waveform"])
        self.spectrum_bars.setOpts(height=frame["spectrum"])

        spectrum_peak = float(np.max(frame["spectrum"]))
        if spectrum_peak > self.spectrum_max:
            self.spectrum_max = spectrum_peak * 1.1
            self.spectrum_plot.setYRange(0.0, self.spectrum_max, padding=0)

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
        self.radial_spectrum.update(spectrum, self.peak_hold_spectrum)

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
Replace it with:
```python
    def on_tick(self):
        if self.read_pos >= len(self.data):
            self.timer.stop()
            return

        chunk = self.data[self.read_pos:self.read_pos + self.chunk_frames]
        self.read_pos += self.chunk_frames

        flat = chunk.reshape(-1).astype(np.float32)
        self.engine.push_samples(flat, self.n_channels)

        frame = self.engine.get_latest_features()

        if self.show_waveform:
            self.curve.setData(frame["waveform"])

        if self.show_spectrum:
            self.spectrum_bars.setOpts(height=frame["spectrum"])
            spectrum_peak = float(np.max(frame["spectrum"]))
            if spectrum_peak > self.spectrum_max:
                self.spectrum_max = spectrum_peak * 1.1
                self.spectrum_plot.setYRange(0.0, self.spectrum_max, padding=0)

        if self.show_spectrogram:
            self.spectrogram.update(frame["spectrum"])

        if self.show_spectrum or self.show_radial:
            spectrum = np.asarray(frame["spectrum"], dtype=np.float32)
            self.peak_hold_spectrum, self.peak_hold_timer_spectrum = update_peak_hold(
                spectrum,
                self.peak_hold_spectrum,
                self.peak_hold_timer_spectrum,
                self.tick_interval_s,
                PEAK_HOLD_SECONDS,
                PEAK_DECAY_PER_SECOND,
            )
            if self.show_spectrum:
                self.peak_hold_dots.setData(
                    x=np.arange(self.spectrum_len),
                    y=self.peak_hold_spectrum,
                )
            if self.show_radial:
                self.radial_spectrum.update(spectrum, self.peak_hold_spectrum)

        if self.show_meters:
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

The shared `update_peak_hold` call runs whenever either the Spectrum panel or the Radial panel is visible, since both consume `self.peak_hold_spectrum`; each panel's own render call (`peak_hold_dots.setData` / `radial_spectrum.update`) stays behind its own flag.

- [ ] **Step 5: Run the full test suite and smoke test harness (regression check)**

```bash
./frontend/run.sh -m pytest frontend/tests/ -v
./frontend/run.sh frontend/scripts/smoke_test_harness.py
```

Expected: `24 passed`, then `smoke_test_harness: OK`. (`build_toolbar()` running during `WaveformWindow.__init__` inside the smoke test's offscreen `QApplication` confirms the toggle wiring doesn't crash outside a fully-shown window.)

- [ ] **Step 6: Commit**

```bash
git add frontend/main.py
git commit -m "feat: add toolbar panel toggles with keyboard shortcuts and on_tick gating"
```

---

### Task 4: Rate slider, label, and Up/Down keyboard shortcuts

**Files:**
- Modify: `frontend/main.py`

**Interfaces:**
- Consumes: `rate_hz_to_chunk_frames` (Task 1); `self.rate_hz`, `self.sample_rate`, `self.chunk_frames`, `self.timer`, `self.tick_interval_s` (existing/Task 2); `build_toolbar()` (Task 3, extended here).
- Produces: `self.rate_slider` (`QtWidgets.QSlider`), `self.rate_value_label` (`QtWidgets.QLabel`), `on_rate_changed(new_rate_hz: int) -> None` method.

- [ ] **Step 1: Extend `build_toolbar` with the rate slider and shortcuts**

Find the end of `build_toolbar`'s panel-toggle loop:
```python
            action.setChecked(True)
            toolbar.addAction(action)
            self.panel_actions[flag_attr] = action
```
Add immediately after it, still inside `build_toolbar` (before the method ends):
```python
            action.setChecked(True)
            toolbar.addAction(action)
            self.panel_actions[flag_attr] = action

        toolbar.addSeparator()

        toolbar.addWidget(QtWidgets.QLabel("Rate:"))

        self.rate_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.rate_slider.setRange(5, 60)
        self.rate_slider.setSingleStep(5)
        self.rate_slider.setPageStep(5)
        self.rate_slider.setTickInterval(5)
        self.rate_slider.setFixedWidth(120)
        self.rate_value_label = QtWidgets.QLabel()

        initial_rate = min(60, max(5, round(self.rate_hz / 5) * 5))
        self.rate_slider.setValue(initial_rate)
        self.rate_slider.valueChanged.connect(self.on_rate_changed)
        self.on_rate_changed(self.rate_slider.value())

        toolbar.addWidget(self.rate_slider)
        toolbar.addWidget(self.rate_value_label)

        rate_up = QtWidgets.QAction(self)
        rate_up.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Up))
        rate_up.triggered.connect(lambda: self.rate_slider.setValue(self.rate_slider.value() + 5))
        self.addAction(rate_up)

        rate_down = QtWidgets.QAction(self)
        rate_down.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Down))
        rate_down.triggered.connect(lambda: self.rate_slider.setValue(self.rate_slider.value() - 5))
        self.addAction(rate_down)
```

`self.rate_slider.setValue(initial_rate)` is called *before* `valueChanged` is connected, so it can't fire `on_rate_changed` twice — the explicit `self.on_rate_changed(self.rate_slider.value())` call right after is the single source of the initial sync. `QSlider.setValue` clamps silently to `[5, 60]`, so `rate_up`/`rate_down`'s `+5`/`-5` never need their own clamping logic.

- [ ] **Step 2: Add the `on_rate_changed` method**

Find:
```python
    def on_panel_toggled(self, checked, widget, flag_attr):
        widget.setVisible(checked)
        setattr(self, flag_attr, checked)
```
Add immediately after it:
```python

    def on_rate_changed(self, new_rate_hz):
        self.rate_hz = new_rate_hz
        self.chunk_frames = rate_hz_to_chunk_frames(self.sample_rate, new_rate_hz)
        interval_ms = max(1, int(1000 * self.chunk_frames / self.sample_rate))
        self.tick_interval_s = interval_ms / 1000.0
        self.timer.setInterval(interval_ms)
        self.rate_value_label.setText(f"{new_rate_hz} Hz")
```

`self.tick_interval_s` is recomputed here because it directly feeds `update_peak_hold`'s decay math and the peak-meter hold/decay logic in `on_tick` — leaving it stale after a rate change would make peak-hold decay at the wrong real-world speed. `self.read_pos` (playback position) is untouched: only the chunk size read on future ticks changes.

- [ ] **Step 3: Run the full test suite and smoke test harness (regression check)**

```bash
./frontend/run.sh -m pytest frontend/tests/ -v
./frontend/run.sh frontend/scripts/smoke_test_harness.py
```

Expected: `24 passed`, then `smoke_test_harness: OK`.

- [ ] **Step 4: Commit**

```bash
git add frontend/main.py
git commit -m "feat: add update-rate slider with Up/Down keyboard shortcuts"
```

---

### Task 5: Smoke test

**Files:** none

- [ ] **Step 1: Run all unit tests**

```bash
./frontend/run.sh -m pytest frontend/tests/ -v
```

Expected: `24 passed`.

- [ ] **Step 2: Run the visualizer and verify manually**

```bash
./frontend/run.sh frontend/main.py frontend/fixtures/test_tone.wav
```

Verify:
- A toolbar appears at the top of the window with 5 checkable buttons (Waveform, Spectrum, Spectrogram, Radial, Meters), all checked initially, followed by a "Rate:" label, a slider, and a "NN Hz" value label reading `30 Hz` (the CLI default).
- Clicking each toolbar button hides/shows the matching panel and the surrounding layout reflows to fill/reclaim the freed space (no dead gaps).
- Pressing `1`, `2`, `3`, `4`, `5` toggles the same 5 panels as their corresponding toolbar buttons (works even when a plot widget has mouse focus).
- Dragging the rate slider changes the "NN Hz" label live and visibly changes how often the waveform/spectrum redraw (slower at 5 Hz, smoother at 60 Hz), without the audio position jumping or resetting.
- Pressing `Up`/`Down` arrow keys moves the slider by 5 Hz per press, clamped at 5 and 60, keeping the label in sync.
- Hiding all 4 visual panels leaves just the toolbar and the meters row (or an empty area if Meters is also hidden) without crashing; re-enabling any panel resumes its updates.

- [ ] **Step 3: Commit any fixes**

If cosmetic or behavioral issues were found and fixed during the smoke test:

```bash
git add frontend/main.py
git commit -m "fix: cosmetic adjustments from phase 2d smoke test"
```
