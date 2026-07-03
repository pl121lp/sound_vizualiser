# Transport Toolbar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an always-visible transport toolbar to the frontend that shows the current file path and lets the user open a file, loop, restart, pause, and (stub only) toggle microphone input — and let the app start with no file at all.

**Architecture:** All changes live in `frontend/main.py` (single-file frontend, matches existing project structure) plus one new pure helper function in `frontend/audio_math.py`. `WaveformWindow` gains a `load_file()` method that (re)builds the engine and the two sample-rate-dependent panels in place, a second toolbar built via `addToolBarBreak()` so it renders as its own top row, and transport state (`loop_enabled`, `mic_enabled`, `has_file`, `file_path`).

**Tech Stack:** Python, PyQt5 (`QtWidgets`/`QtCore`/`QtGui`), pyqtgraph, soundfile, pytest.

## Global Constraints

- No changes to `engine/` (C++) — this is a frontend-only feature.
- The Open File dialog filters to `*.wav` (plus `All files (*)`), per the approved design — no other format support in scope.
- Microphone input is a UI-only stub: no capture is implemented (deferred to a future phase per `todo.txt`).
- `frontend/main.py` stays a single file, following the existing project convention (no new frontend files besides tests).
- Existing behavior when a file is given on the CLI must be unchanged from the user's perspective (autoplay starts immediately).

Full design reference: `docs/superpowers/specs/2026-07-03-transport-toolbar-design.md`

---

### Task 1: `advance_or_pause` pure function

**Files:**
- Modify: `frontend/audio_math.py`
- Test: `frontend/tests/test_audio_math.py`

**Interfaces:**
- Produces: `advance_or_pause(read_pos: int, data_len: int, loop_enabled: bool) -> tuple[int, bool]` — given the current read position and total sample count, returns `(new_read_pos, should_pause)`. If `read_pos < data_len`, returns `(read_pos, False)` unchanged. If `read_pos >= data_len` (end of file reached): when `loop_enabled` is `True`, returns `(0, False)`; when `False`, returns `(read_pos, True)` (position left as-is, caller should pause). Task 2's `on_tick` consumes this exact signature.

- [ ] **Step 1: Write the failing tests**

Add to `frontend/tests/test_audio_math.py` (append at end of file, and add `advance_or_pause` to the existing `from audio_math import (...)` block at the top):

```python
from audio_math import (
    advance_or_pause,
    make_log_freq_grid,
    make_radial_angles,
    polar_bar_endpoints,
    rate_hz_to_chunk_frames,
    to_db_normalized,
    update_peak_hold,
)
```

```python
def test_advance_or_pause_mid_playback_unchanged():
    read_pos, should_pause = advance_or_pause(100, 1000, loop_enabled=False)
    assert read_pos == 100
    assert should_pause is False


def test_advance_or_pause_eof_no_loop_pauses():
    read_pos, should_pause = advance_or_pause(1000, 1000, loop_enabled=False)
    assert read_pos == 1000
    assert should_pause is True


def test_advance_or_pause_past_eof_no_loop_pauses():
    read_pos, should_pause = advance_or_pause(1200, 1000, loop_enabled=False)
    assert read_pos == 1200
    assert should_pause is True


def test_advance_or_pause_eof_with_loop_wraps_to_zero():
    read_pos, should_pause = advance_or_pause(1000, 1000, loop_enabled=True)
    assert read_pos == 0
    assert should_pause is False


def test_advance_or_pause_mid_playback_with_loop_enabled_unchanged():
    read_pos, should_pause = advance_or_pause(500, 1000, loop_enabled=True)
    assert read_pos == 500
    assert should_pause is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./frontend/run.sh -m pytest frontend/tests/test_audio_math.py -k advance_or_pause -v`
Expected: FAIL / ERROR — `ImportError: cannot import name 'advance_or_pause'`

- [ ] **Step 3: Implement `advance_or_pause`**

Append to `frontend/audio_math.py`:

```python
def advance_or_pause(read_pos: int, data_len: int, loop_enabled: bool) -> tuple[int, bool]:
    if read_pos < data_len:
        return read_pos, False
    if loop_enabled:
        return 0, False
    return read_pos, True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./frontend/run.sh -m pytest frontend/tests/test_audio_math.py -v`
Expected: all tests PASS (existing tests plus the 5 new ones)

- [ ] **Step 5: Commit**

```bash
git add frontend/audio_math.py frontend/tests/test_audio_math.py
git commit -m "feat: add advance_or_pause for EOF/loop transport logic"
```

---

### Task 2: Lazy file loading + transport toolbar in `main.py`

**Files:**
- Modify: `frontend/main.py`

**Interfaces:**
- Consumes: `advance_or_pause(read_pos, data_len, loop_enabled)` from Task 1 (imported from `audio_math`).
- Produces (for manual verification / future work): `WaveformWindow.load_file(path)`, `WaveformWindow.set_paused(paused)` — no other code in this codebase currently calls into `WaveformWindow` from outside `main()`, so these are consumed only within this file.

This task has no automated test target (the codebase has no Qt widget test harness — `frontend/tests/` only covers pure functions in `audio_math.py`, per existing convention). Verification is manual, using `frontend/fixtures/test_tone.wav`, driven through `./frontend/run.sh main.py`. Steps below include an explicit manual verification checklist before the commit.

- [ ] **Step 1: Make `wav_path` optional on the CLI**

In `frontend/main.py`, in `main()`, replace:

```python
    parser.add_argument("wav_path", help="Path to a WAV file")
```

with:

```python
    parser.add_argument(
        "wav_path",
        nargs="?",
        default=None,
        help="Path to a WAV file (optional; if omitted, launches paused with no file loaded)",
    )
```

- [ ] **Step 2: Replace `WaveformWindow.__init__` for lazy startup**

Replace the entire `__init__` method (from `def __init__(self, wav_path, args):` through the line before `def on_tick(self):`) with:

```python
    def __init__(self, wav_path, args):
        super().__init__()

        self.args = args
        self.window_size = args.window_size
        self.spectrum_len = self.window_size // 2 + 1
        self.rate_hz = args.update_rate

        self.data = None
        self.sample_rate = None
        self.n_channels = 0
        self.read_pos = 0
        self.chunk_frames = 1
        self.has_file = False
        self.file_path = None
        self.loop_enabled = False
        self.mic_enabled = False
        self.engine = None

        self.waveform_plot = pg.PlotWidget()
        self.waveform_plot.setYRange(-1.0, 1.0)
        self.waveform_plot.setLabel("left", "Waveform")
        self.curve = self.waveform_plot.plot(np.zeros(self.window_size))

        self.spectrum_plot = pg.PlotWidget()
        self.spectrum_plot.setLabel("left", "Spectrum")
        self.spectrum_plot.enableAutoRange("y", False)
        self.spectrum_max = 1e-6
        self.spectrum_plot.setYRange(0.0, self.spectrum_max, padding=0)
        self.spectrum_bars = pg.BarGraphItem(
            x=np.arange(self.spectrum_len), height=np.zeros(self.spectrum_len), width=0.8
        )
        self.spectrum_plot.addItem(self.spectrum_bars)

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

        # SpectrogramPanel/RadialSpectrumPanel need a sample rate to build their
        # frequency grids, which isn't known until a file is loaded. These plain
        # QWidget placeholders reserve the layout slot; load_file() swaps in the
        # real panels via _replace_panel().
        self.spectrogram = QtWidgets.QWidget()
        self.spectrogram.setMinimumHeight(150)
        self.radial_spectrum = QtWidgets.QWidget()
        self.radial_spectrum.setMinimumHeight(150)

        container = QtWidgets.QWidget()
        self.container_layout = QtWidgets.QVBoxLayout(container)
        self.container_layout.addWidget(self.waveform_plot, stretch=1)
        self.container_layout.addWidget(self.spectrum_plot, stretch=1)
        self.container_layout.addWidget(self.spectrogram, stretch=2)
        self.container_layout.addWidget(self.radial_spectrum, stretch=2)

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
        self.container_layout.addWidget(self.meters_container)

        self.setCentralWidget(container)

        self.tick_interval_s = 1.0 / self.rate_hz
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.on_tick)

        self.show_waveform = True
        self.show_spectrum = True
        self.show_spectrogram = True
        self.show_radial = True
        self.show_meters = True

        self.build_transport_toolbar()
        self.addToolBarBreak()
        self.build_toolbar()

        if wav_path:
            self.load_file(wav_path)
```

- [ ] **Step 3: Add `load_file` and `_replace_panel`**

Add these two methods immediately after `__init__` (before `on_tick`):

```python
    def load_file(self, path):
        try:
            data, sample_rate = sf.read(path, dtype="float32", always_2d=True)
        except Exception as exc:
            QtWidgets.QMessageBox.warning(
                self, "Failed to load file", f"Could not load '{path}':\n{exc}"
            )
            return

        self.data = data
        self.sample_rate = sample_rate
        self.n_channels = data.shape[1]
        self.read_pos = 0
        self.chunk_frames = rate_hz_to_chunk_frames(sample_rate, self.rate_hz)

        self.engine = sound_viz_py.Engine(
            window_size=self.window_size,
            sample_rate=sample_rate,
            update_rate_hz=self.rate_hz,
            fft_window_type=self.args.fft_window,
            band_split_low_hz=self.args.band_split_low,
            band_split_high_hz=self.args.band_split_high,
        )

        self._replace_panel(
            "spectrogram",
            SpectrogramPanel(self.spectrum_len, sample_rate, self.rate_hz),
            stretch=2,
            flag_attr="show_spectrogram",
        )
        self._replace_panel(
            "radial_spectrum",
            RadialSpectrumPanel(self.spectrum_len, sample_rate),
            stretch=2,
            flag_attr="show_radial",
        )

        self.has_file = True
        self.file_path = path
        self._update_path_label()
        self._set_transport_enabled(True)

        interval_ms = max(1, int(1000 * self.chunk_frames / sample_rate))
        self.tick_interval_s = interval_ms / 1000.0
        self.timer.setInterval(interval_ms)
        if not self.mic_enabled:
            self.set_paused(False)

    def _replace_panel(self, attr_name, new_widget, stretch, flag_attr):
        old_widget = getattr(self, attr_name)
        index = self.container_layout.indexOf(old_widget)
        self.container_layout.removeWidget(old_widget)
        old_widget.setParent(None)
        old_widget.deleteLater()
        new_widget.setVisible(getattr(self, flag_attr))
        self.container_layout.insertWidget(index, new_widget, stretch)
        setattr(self, attr_name, new_widget)
```

`flag_attr` restores the panel's current show/hide state (e.g. `show_spectrogram`) onto the freshly created widget — otherwise a panel the user had toggled off would pop back to visible every time a new file is loaded.

- [ ] **Step 4: Add the transport toolbar and its handlers**

Add these methods after `_replace_panel` (still before `on_tick`):

```python
    def build_transport_toolbar(self):
        toolbar = self.addToolBar("Transport")
        toolbar.setMovable(False)

        self.path_label = QtWidgets.QLabel()
        toolbar.addWidget(self.path_label)
        toolbar.addSeparator()

        self.open_action = QtWidgets.QAction("Open File...", self)
        self.open_action.triggered.connect(self.on_open_file)
        toolbar.addAction(self.open_action)

        self.mic_action = QtWidgets.QAction("Mic", self)
        self.mic_action.setCheckable(True)
        self.mic_action.toggled.connect(self.on_mic_toggled)
        toolbar.addAction(self.mic_action)

        self.loop_action = QtWidgets.QAction("Loop", self)
        self.loop_action.setCheckable(True)
        self.loop_action.toggled.connect(self.on_loop_toggled)
        toolbar.addAction(self.loop_action)

        self.restart_action = QtWidgets.QAction("Restart", self)
        self.restart_action.triggered.connect(self.on_restart)
        toolbar.addAction(self.restart_action)

        self.pause_action = QtWidgets.QAction("Pause", self)
        self.pause_action.setCheckable(True)
        self.pause_action.toggled.connect(self.on_pause_toggled)
        toolbar.addAction(self.pause_action)

        self._update_path_label()
        self._set_transport_enabled(False)

    def _update_path_label(self):
        if self.mic_enabled:
            self.path_label.setText("Microphone (not implemented)")
        elif self.has_file:
            self.path_label.setText(self.file_path)
        else:
            self.path_label.setText("No file loaded")

    def _set_transport_enabled(self, has_file):
        file_controls_enabled = has_file and not self.mic_enabled
        self.loop_action.setEnabled(file_controls_enabled)
        self.restart_action.setEnabled(file_controls_enabled)
        self.pause_action.setEnabled(file_controls_enabled)

    def on_open_file(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select Audio File", "", "WAV files (*.wav);;All files (*)"
        )
        if path:
            self.load_file(path)

    def on_mic_toggled(self, checked):
        self.mic_enabled = checked
        self.open_action.setEnabled(not checked)
        self._set_transport_enabled(self.has_file)
        if checked:
            self.set_paused(True)
        self._update_path_label()

    def on_loop_toggled(self, checked):
        self.loop_enabled = checked

    def on_restart(self):
        self.read_pos = 0

    def on_pause_toggled(self, checked):
        self.set_paused(checked)

    def set_paused(self, paused):
        if paused:
            self.timer.stop()
        else:
            self.timer.start()
        if self.pause_action.isChecked() != paused:
            self.pause_action.blockSignals(True)
            self.pause_action.setChecked(paused)
            self.pause_action.blockSignals(False)
```

- [ ] **Step 5: Rewire `on_tick` for loop/pause at EOF**

Replace the start of `on_tick` (the file currently has, right after `def on_tick(self):`):

```python
        if self.read_pos >= len(self.data):
            self.timer.stop()
            return
```

with:

```python
        self.read_pos, should_pause = advance_or_pause(
            self.read_pos, len(self.data), self.loop_enabled
        )
        if should_pause:
            self.pause_action.setChecked(True)
            return
```

- [ ] **Step 6: Fix stale widget capture in `build_toolbar`'s panel toggles**

`build_toolbar()`'s panel-visibility checkboxes currently close over the *widget object* itself (`self.spectrogram`, `self.radial_spectrum`) at toolbar-construction time. Since `load_file`'s `_replace_panel` (Step 3) swaps `self.spectrogram`/`self.radial_spectrum` out for a new instance on every file load, those closures would keep pointing at the old, already-deleted placeholder — toggling "Spectrogram" or "Radial" after opening a file would do nothing visible. Fix by closing over the attribute *name* and resolving it via `getattr` at toggle time instead.

In `frontend/main.py`, in `build_toolbar()`, replace:

```python
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
```

with:

```python
        panel_specs = [
            ("Waveform", "1", "waveform_plot", "show_waveform"),
            ("Spectrum", "2", "spectrum_plot", "show_spectrum"),
            ("Spectrogram", "3", "spectrogram", "show_spectrogram"),
            ("Radial", "4", "radial_spectrum", "show_radial"),
            ("Meters", "5", "meters_container", "show_meters"),
        ]
        self.panel_actions = {}
        for label, key, widget_attr, flag_attr in panel_specs:
            action = QtWidgets.QAction(label, self)
            action.setCheckable(True)
            action.setShortcut(QtGui.QKeySequence(key))
            action.toggled.connect(
                lambda checked, w_attr=widget_attr, attr=flag_attr: self.on_panel_toggled(
                    checked, w_attr, attr
                )
            )
            action.setChecked(True)
            toolbar.addAction(action)
            self.panel_actions[flag_attr] = action
```

Then replace `on_panel_toggled`:

```python
    def on_panel_toggled(self, checked, widget, flag_attr):
        widget.setVisible(checked)
        setattr(self, flag_attr, checked)
```

with:

```python
    def on_panel_toggled(self, checked, widget_attr, flag_attr):
        getattr(self, widget_attr).setVisible(checked)
        setattr(self, flag_attr, checked)
```

- [ ] **Step 7: Import `advance_or_pause`**

In the existing import block near the top of `frontend/main.py`, update:

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

to:

```python
from audio_math import (
    advance_or_pause,
    make_log_freq_grid,
    make_radial_angles,
    polar_bar_endpoints,
    rate_hz_to_chunk_frames,
    to_db_normalized,
    update_peak_hold,
)
```

- [ ] **Step 8: Run the existing automated tests**

Run: `./frontend/run.sh -m pytest frontend/tests/ -v`
Expected: all tests PASS (this task doesn't change `audio_math.py`, so this just guards against an accidental regression from the `main.py` edits, e.g. a stray import error caught by collection).

- [ ] **Step 9: Manual verification — no file at launch**

Run: `./frontend/run.sh main.py`
Expected:
- Window opens without crashing.
- Transport toolbar (top row) shows "No file loaded"; Loop, Restart, Pause are disabled/greyed out; Open File... and Mic are enabled.
- Controls toolbar (second row) is visible below it.
- All plot panels are present but static/empty (no exception in the terminal).

- [ ] **Step 10: Manual verification — file given on CLI**

Run: `./frontend/run.sh main.py frontend/fixtures/test_tone.wav`
Expected:
- Playback starts immediately (matches pre-existing behavior).
- Transport toolbar shows the fixture's path; Loop, Restart, Pause are enabled.
- Waveform/spectrum/spectrogram/radial panels animate.

- [ ] **Step 11: Manual verification — Open File mid-session, and that panel toggles still work**

With the app running from Step 9 (no file), click **Open File...**, select `frontend/fixtures/test_tone.wav`.
Expected:
- Path label updates to the selected file's path.
- Playback starts automatically.
- Spectrogram and radial panels render correctly (they were rebuilt against the new sample rate) — no stale/frozen placeholder widgets.
- Toggle the "Spectrogram" and "Radial" checkboxes on the Controls toolbar (or press `3`/`4`) — they must show/hide the live panel that's actually rendering, not silently do nothing. This exercises the Step 6 fix (stale widget capture across a panel swap).

- [ ] **Step 12: Manual verification — Pause / Restart / Loop**

With a file playing:
- Click **Pause** — playback freezes, action shows checked/pressed state; click again — playback resumes from where it left off.
- Click **Restart** — visualization jumps back to the start of the file; if it was playing, it keeps playing from position 0; if paused, it stays paused showing frame 0.
- Enable **Loop**, let the file reach the end — playback should wrap back to the start and keep animating instead of stopping.
- Disable **Loop**, let the file reach the end — playback should stop and the **Pause** action should show its checked/paused state.

- [ ] **Step 13: Manual verification — Mic stub toggle**

With a file loaded and playing, click **Mic**.
Expected:
- Playback pauses.
- Path label shows "Microphone (not implemented)".
- Open File, Loop, Restart, Pause all become disabled.
- Unchecking Mic re-enables Loop/Restart/Pause and Open File, and the path label reverts to the file path. Playback stays paused until the user presses Pause/Play again.

- [ ] **Step 14: Manual verification — bad file path**

Run: `./frontend/run.sh main.py /nonexistent/path.wav`
Expected: a warning dialog appears ("Failed to load file..."); after dismissing it, the window shows the normal "No file loaded" transport state rather than crashing.

- [ ] **Step 15: Commit**

```bash
git add frontend/main.py
git commit -m "feat: add transport toolbar with file open, loop, restart, pause, and mic stub"
```
