# Phase 2e Live Mic Input Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing "Mic" toolbar toggle in `frontend/main.py` actually capture and
visualize live microphone audio, instead of showing "Microphone (not implemented)".

**Architecture:** A new `frontend/mic_input.py` module wraps `sounddevice` (a PortAudio
binding) behind a narrow `start()`/`stop()`/`read_available()` interface. The PortAudio
callback thread only appends captured frames to a `queue.Queue` — it never touches the
C++ engine. The existing `QTimer`-driven tick in `WaveformWindow` (already the sole caller
of `engine.push_samples`/`get_latest_features` for file playback) drains that queue each
tick and feeds the engine from the main thread only, so no new cross-thread engine access
is introduced.

**Tech Stack:** Python 3.13, PyQt5, pyqtgraph, numpy, `sounddevice` (new dependency,
PortAudio binding), pytest.

## Global Constraints

- No changes to the C++ engine or pybind11 bindings (`engine/`) — the engine stays
  capture-agnostic, consuming `push_samples(samples, n_channels)` exactly as it does today.
- Mic capture uses the system default input device only — no device-selection UI.
- Only a Linux-capable backend is implemented (`sounddevice`/PortAudio), but the
  `MicInputSource` interface must not assume Linux-specific behavior, so a different
  backend could later be substituted without changing `main.py`.
- Mic audio must never be pushed into the engine from the PortAudio callback thread —
  only from the Qt main thread (via the existing tick timer).
- Follow the existing repo pattern of catching all mic-unavailable conditions (missing
  library, no device, PortAudio failure) into one exception type, surfaced as a
  `QMessageBox.warning` with the toggle reverted — never a crash.
- Run frontend tests via `./frontend/run.sh -m pytest <path> -v` from the repo root
  (confirmed working pattern — see `frontend/tests/test_audio_math.py`).

---

### Task 1: `mic_input.py` — capture backend with injectable stream factory

**Files:**
- Create: `frontend/mic_input.py`
- Create: `frontend/tests/test_mic_input.py`
- Modify: `frontend/requirements.txt`

**Interfaces:**
- Produces: `frontend.mic_input.MicUnavailableError(Exception)` — raised by
  `MicInputSource.start()` when capture can't be started (message is the human-readable
  reason, e.g. `"sounddevice/PortAudio not available"` or a wrapped exception from the
  stream factory).
- Produces: `frontend.mic_input.MicInputSource`:
  - `__init__(self, stream_factory=None)` — `stream_factory` is a callable
    `(**kwargs) -> stream_obj` where `stream_obj` has `.start()`, `.stop()`, `.close()`
    methods and a `.samplerate` attribute (this is exactly `sounddevice.InputStream`'s
    shape). Defaults to a module-level `_default_stream_factory` that wraps
    `sounddevice.InputStream` and raises `MicUnavailableError` if `sounddevice` failed to
    import (missing package, or missing system PortAudio library — both surface as
    exceptions at `import sounddevice` time, not just `ModuleNotFoundError`).
  - `.sample_rate: float | None` — `None` until `start()` succeeds, then the actual rate
    the stream opened at (`stream_obj.samplerate`). Sample rate is discovered by opening
    the stream with `samplerate=None` (PortAudio picks the device default) and reading it
    back, rather than a separate device-query call — this keeps the whole class
    testable against a fake stream object with no real `sounddevice`/PortAudio needed.
  - `.channels: int` — always `1` (mono capture).
  - `start(self) -> None` — opens the stream via `self._stream_factory`, wraps any
    exception into `MicUnavailableError`, then calls `.start()` on the stream object.
  - `stop(self) -> None` — stops and closes the stream, only valid to call after a
    successful `start()`.
  - `read_available(self) -> np.ndarray | None` — drains everything currently in the
    internal queue (non-blocking), concatenates it into one 1-D `float32` array, and
    returns it; returns `None` if the queue was empty.

- [ ] **Step 1: Write the failing tests**

Create `frontend/tests/test_mic_input.py`:

```python
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from mic_input import MicInputSource, MicUnavailableError


class FakeStream:
    def __init__(self, callback, samplerate=48000.0):
        self.callback = callback
        self.samplerate = samplerate
        self.started = False
        self.closed = False

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def close(self):
        self.closed = True

    def feed(self, mono_frame: np.ndarray):
        # sounddevice calls back with shape (frames, channels); channels=1 here.
        indata = mono_frame.reshape(-1, 1).astype(np.float32)
        self.callback(indata, len(mono_frame), None, None)


def make_fake_factory():
    created = {}

    def factory(**kwargs):
        stream = FakeStream(callback=kwargs["callback"])
        created["stream"] = stream
        return stream

    return factory, created


def test_read_available_returns_none_when_nothing_captured():
    factory, _ = make_fake_factory()
    source = MicInputSource(stream_factory=factory)
    source.start()

    assert source.read_available() is None


def test_read_available_drains_and_concatenates_callback_frames():
    factory, created = make_fake_factory()
    source = MicInputSource(stream_factory=factory)
    source.start()

    created["stream"].feed(np.array([0.1, 0.2], dtype=np.float32))
    created["stream"].feed(np.array([0.3], dtype=np.float32))

    result = source.read_available()

    np.testing.assert_allclose(result, [0.1, 0.2, 0.3])
    assert source.read_available() is None  # queue drained


def test_start_sets_sample_rate_from_stream():
    factory, _ = make_fake_factory()
    source = MicInputSource(stream_factory=factory)

    assert source.sample_rate is None
    source.start()
    assert source.sample_rate == 48000.0
    assert source.channels == 1


def test_start_wraps_factory_failure_in_mic_unavailable_error():
    def failing_factory(**kwargs):
        raise RuntimeError("no default input device")

    source = MicInputSource(stream_factory=failing_factory)

    with pytest.raises(MicUnavailableError):
        source.start()


def test_stop_stops_and_closes_stream():
    factory, created = make_fake_factory()
    source = MicInputSource(stream_factory=factory)
    source.start()

    source.stop()

    assert created["stream"].started is False
    assert created["stream"].closed is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./frontend/run.sh -m pytest frontend/tests/test_mic_input.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'mic_input'`

- [ ] **Step 3: Add `sounddevice` to requirements and install it**

Modify `frontend/requirements.txt` — append a new line:

```
sounddevice
```

Run: `./frontend/run.sh -m pip install -r frontend/requirements.txt`
Expected: `sounddevice` installs successfully (it is a pure-Python/cffi wheel; it does not
need the system PortAudio shared library to *install*, only to *import and use* — if this
dev machine has no system PortAudio library, `import sounddevice` itself will still raise
at runtime, which is exactly the failure case `MicUnavailableError` exists to handle. Note
this to the user if `import sounddevice` fails during manual verification in later tasks —
they may need to install a system PortAudio package to actually exercise real capture).

- [ ] **Step 4: Write `frontend/mic_input.py`**

```python
import queue

import numpy as np

try:
    import sounddevice as sd
except Exception:
    sd = None


class MicUnavailableError(Exception):
    """Raised when live microphone capture can't be started."""


def _default_stream_factory(**kwargs):
    if sd is None:
        raise MicUnavailableError("sounddevice/PortAudio not available")
    return sd.InputStream(**kwargs)


class MicInputSource:
    """Live mic capture, backed by sounddevice/PortAudio.

    Only this one backend exists today, but callers (main.py) only use start(),
    stop(), read_available(), sample_rate, and channels -- a different platform
    backend could implement the same surface without touching call sites.
    """

    def __init__(self, stream_factory=None):
        self._stream_factory = stream_factory or _default_stream_factory
        self._stream = None
        self._queue = queue.Queue()
        self.sample_rate = None
        self.channels = 1

    def _callback(self, indata, frames, time_info, status):
        self._queue.put(indata[:, 0].copy())

    def start(self):
        try:
            self._stream = self._stream_factory(
                channels=self.channels,
                dtype="float32",
                callback=self._callback,
            )
            self._stream.start()
        except MicUnavailableError:
            raise
        except Exception as exc:
            raise MicUnavailableError(str(exc)) from exc

        self.sample_rate = float(self._stream.samplerate)

    def stop(self):
        self._stream.stop()
        self._stream.close()
        self._stream = None

    def read_available(self):
        chunks = []
        while True:
            try:
                chunks.append(self._queue.get_nowait())
            except queue.Empty:
                break
        if not chunks:
            return None
        return np.concatenate(chunks)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `./frontend/run.sh -m pytest frontend/tests/test_mic_input.py -v`
Expected: `5 passed`

- [ ] **Step 6: Commit**

```bash
git add frontend/mic_input.py frontend/tests/test_mic_input.py frontend/requirements.txt
git commit -m "feat: add MicInputSource capture backend (sounddevice/PortAudio)"
```

---

### Task 2: Extract `_configure_for_sample_rate` from `load_file`

**Files:**
- Modify: `frontend/main.py:171-324` (`__init__` attribute init, `load_file`)

**Interfaces:**
- Consumes: nothing new (pure refactor of existing `WaveformWindow` code).
- Produces: `WaveformWindow._configure_for_sample_rate(self, sample_rate: float) -> None`
  — creates `self.engine`, rebuilds the spectrogram/radial panels, sets
  `self.chunk_frames`/`self.tick_interval_s`/timer interval, and sets `self.sample_rate`.
  Task 4 calls this for both mic-enable and mic-disable-restore.
- Produces: `WaveformWindow.file_sample_rate: float | None` — the loaded file's sample
  rate, set once by `load_file` and never overwritten by mic mode, so mic-disable can
  restore the file's engine/panels via `_configure_for_sample_rate(self.file_sample_rate)`.
  (`self.sample_rate` itself now means "the currently active engine's sample rate",
  which changes when switching between file and mic.)

This task has no new automated test — `WaveformWindow` has no existing test coverage
(same as noted in the Phase 2d plan), so it's verified by manually confirming file
playback still works exactly as before.

- [ ] **Step 1: Add `self.file_sample_rate = None` to `__init__`**

In `frontend/main.py`, find this block (around line 179-188):

```python
        self.data = None
        self.sample_rate = None
        self.n_channels = 0
```

Replace with:

```python
        self.data = None
        self.sample_rate = None
        self.file_sample_rate = None
        self.n_channels = 0
```

- [ ] **Step 2: Extract `_configure_for_sample_rate` and simplify `load_file`**

Find `load_file` (around line 278-324):

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
```

Replace with:

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
        self.file_sample_rate = sample_rate
        self.n_channels = data.shape[1]
        self.read_pos = 0

        self._configure_for_sample_rate(sample_rate)

        self.has_file = True
        self.file_path = path
        self._update_path_label()
        self._set_transport_enabled(True)
        if not self.mic_enabled:
            self.set_paused(False)

    def _configure_for_sample_rate(self, sample_rate):
        self.sample_rate = sample_rate
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

        interval_ms = max(1, int(1000 * self.chunk_frames / sample_rate))
        self.tick_interval_s = interval_ms / 1000.0
        self.timer.setInterval(interval_ms)
```

- [ ] **Step 3: Manually verify file playback is unchanged**

Run: `./frontend/run.sh main.py frontend/fixtures/test_tone.wav`
Expected: window opens, waveform/spectrum/spectrogram/radial/meters all animate exactly
as before this refactor (this is a pure code-motion change — no behavior difference).
Close the window when confirmed.

- [ ] **Step 4: Commit**

```bash
git add frontend/main.py
git commit -m "refactor: extract _configure_for_sample_rate from load_file"
```

---

### Task 3: Extract `_process_frame` from `on_tick`

**Files:**
- Modify: `frontend/main.py:430-496` (`on_tick`)

**Interfaces:**
- Produces: `WaveformWindow._process_frame(self, frame) -> None` — takes the dict
  returned by `engine.get_latest_features()` and updates every visualization panel and
  meter. Task 4's mic-tick branch calls this exact method after obtaining a frame.

Pure refactor again — no new automated test, manual verification only.

- [ ] **Step 1: Extract the visualization-update block into `_process_frame`**

Find `on_tick` (around line 430-496):

```python
    def on_tick(self):
        self.read_pos, should_pause = advance_or_pause(
            self.read_pos, len(self.data), self.loop_enabled
        )
        if should_pause:
            self.pause_action.setChecked(True)
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

Replace with:

```python
    def on_tick(self):
        self.read_pos, should_pause = advance_or_pause(
            self.read_pos, len(self.data), self.loop_enabled
        )
        if should_pause:
            self.pause_action.setChecked(True)
            return

        chunk = self.data[self.read_pos:self.read_pos + self.chunk_frames]
        self.read_pos += self.chunk_frames

        flat = chunk.reshape(-1).astype(np.float32)
        self.engine.push_samples(flat, self.n_channels)

        frame = self.engine.get_latest_features()
        self._process_frame(frame)

    def _process_frame(self, frame):
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

- [ ] **Step 2: Manually verify file playback is unchanged**

Run: `./frontend/run.sh main.py frontend/fixtures/test_tone.wav`
Expected: identical behavior to Task 2's manual check. Close the window when confirmed.

- [ ] **Step 3: Commit**

```bash
git add frontend/main.py
git commit -m "refactor: extract _process_frame from on_tick"
```

---

### Task 4: Wire mic capture into the toggle, tick loop, and window teardown

**Files:**
- Modify: `frontend/main.py` (imports, `__init__`, `on_mic_toggled`, `on_tick`,
  `_update_path_label`, `closeEvent`)

**Interfaces:**
- Consumes: `MicInputSource`, `MicUnavailableError` from `frontend/mic_input.py` (Task 1);
  `WaveformWindow._configure_for_sample_rate` (Task 2); `WaveformWindow._process_frame`
  (Task 3); `WaveformWindow.file_sample_rate` (Task 2).
- Produces: `WaveformWindow.mic_source: MicInputSource | None` — `None` whenever mic mode
  is off; a started `MicInputSource` whenever it's on.

No new automated tests (UI glue, consistent with the rest of `WaveformWindow`) — verified
manually in the steps below, including the mic-unavailable error path, which is exercisable
right now on a machine without a working PortAudio install (confirmed: this dev machine
currently has no system PortAudio library, so `sounddevice` will fail to import and the
warning-dialog path is exactly what should be observed).

- [ ] **Step 1: Import the new module**

In `frontend/main.py`, find the import block (around line 12-20):

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

Add directly after it:

```python
from mic_input import MicInputSource, MicUnavailableError
```

- [ ] **Step 2: Initialize `self.mic_source` in `__init__`**

Find (around line 186-188, after Task 2's edit):

```python
        self.loop_enabled = False
        self.mic_enabled = False
        self.engine = None
```

Replace with:

```python
        self.loop_enabled = False
        self.mic_enabled = False
        self.mic_source = None
        self.engine = None
```

- [ ] **Step 3: Replace `_update_path_label`'s mic text**

Find (around line 374-380):

```python
    def _update_path_label(self):
        if self.mic_enabled:
            self.path_label.setText("Microphone (not implemented)")
        elif self.has_file:
            self.path_label.setText(self.file_path)
        else:
            self.path_label.setText("No file loaded")
```

Replace with:

```python
    def _update_path_label(self):
        if self.mic_enabled:
            self.path_label.setText("Microphone (default input device)")
        elif self.has_file:
            self.path_label.setText(self.file_path)
        else:
            self.path_label.setText("No file loaded")
```

- [ ] **Step 4: Implement real start/stop in `on_mic_toggled`**

Find (around line 403-409):

```python
    def on_mic_toggled(self, checked):
        self.mic_enabled = checked
        self.open_action.setEnabled(not checked)
        self._set_transport_enabled(self.has_file)
        if checked:
            self.set_paused(True)
        self._update_path_label()
```

Replace with:

```python
    def on_mic_toggled(self, checked):
        if checked:
            mic_source = MicInputSource()
            try:
                mic_source.start()
            except MicUnavailableError as exc:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Microphone unavailable",
                    f"Could not start microphone capture:\n{exc}",
                )
                self.mic_action.blockSignals(True)
                self.mic_action.setChecked(False)
                self.mic_action.blockSignals(False)
                return

            self.mic_source = mic_source
            self.mic_enabled = True
            self.open_action.setEnabled(False)
            self._set_transport_enabled(self.has_file)
            self._configure_for_sample_rate(self.mic_source.sample_rate)
            self.set_paused(False)
        else:
            self.mic_enabled = False
            self.mic_source.stop()
            self.mic_source = None
            self.open_action.setEnabled(True)
            self._set_transport_enabled(self.has_file)
            if self.has_file:
                self._configure_for_sample_rate(self.file_sample_rate)
                self.set_paused(True)

        self._update_path_label()
```

- [ ] **Step 5: Branch `on_tick` on `self.mic_enabled`**

Find (around line 430-444, before Task 3's `_process_frame` call):

```python
    def on_tick(self):
        self.read_pos, should_pause = advance_or_pause(
            self.read_pos, len(self.data), self.loop_enabled
        )
        if should_pause:
            self.pause_action.setChecked(True)
            return

        chunk = self.data[self.read_pos:self.read_pos + self.chunk_frames]
        self.read_pos += self.chunk_frames

        flat = chunk.reshape(-1).astype(np.float32)
        self.engine.push_samples(flat, self.n_channels)

        frame = self.engine.get_latest_features()
        self._process_frame(frame)
```

Replace with:

```python
    def on_tick(self):
        if self.mic_enabled:
            chunk = self.mic_source.read_available()
            if chunk is None:
                return
            self.engine.push_samples(chunk, 1)
        else:
            self.read_pos, should_pause = advance_or_pause(
                self.read_pos, len(self.data), self.loop_enabled
            )
            if should_pause:
                self.pause_action.setChecked(True)
                return

            chunk = self.data[self.read_pos:self.read_pos + self.chunk_frames]
            self.read_pos += self.chunk_frames

            flat = chunk.reshape(-1).astype(np.float32)
            self.engine.push_samples(flat, self.n_channels)

        frame = self.engine.get_latest_features()
        self._process_frame(frame)
```

- [ ] **Step 6: Stop the mic stream on window close**

Find `closeEvent` (around line 570-576):

```python
    def closeEvent(self, event):
        # Stop the timer before the window starts tearing down. Otherwise a
        # pending on_tick can still update the plots (scheduling a repaint)
        # while Qt's Wayland backing store is mid-teardown for the closing
        # window, which segfaults inside QWaylandWindow::decoration().
        self.timer.stop()
        super().closeEvent(event)
```

Replace with:

```python
    def closeEvent(self, event):
        # Stop the timer before the window starts tearing down. Otherwise a
        # pending on_tick can still update the plots (scheduling a repaint)
        # while Qt's Wayland backing store is mid-teardown for the closing
        # window, which segfaults inside QWaylandWindow::decoration().
        self.timer.stop()
        if self.mic_source is not None:
            self.mic_source.stop()
        super().closeEvent(event)
```

- [ ] **Step 7: Manually verify the mic-unavailable path**

Run: `./frontend/run.sh main.py frontend/fixtures/test_tone.wav`

With the file playing, click the "Mic" toolbar button.

Expected (on a machine without a working system PortAudio install, which is the current
state of this dev machine): a "Microphone unavailable" warning dialog appears, and the
Mic button reverts to unchecked after dismissing it. File transport (loop/restart/pause)
remains exactly as it was before clicking Mic. Confirm clicking Mic again reproduces the
same result (no crash, no leaked state).

If a working PortAudio install *is* available (system package such as `libportaudio2` on
Debian/Ubuntu installed separately by the user, outside this plan's scope): expected
behavior is instead that the "Mic" button stays checked, the path label reads
"Microphone (default input device)", loop/restart/pause become disabled, and the
waveform/spectrum/meters respond live to sound picked up by the system's default input
device. Toggling Mic back off should resume the file at its prior `read_pos`, paused.

- [ ] **Step 8: Commit**

```bash
git add frontend/main.py
git commit -m "feat: wire live mic capture into the Mic toolbar toggle"
```

---

## Self-Review Notes

- **Spec coverage:** `mic_input.py` interface (Task 1) — done. Thread safety via
  queue-draining on the existing timer, no engine access from the callback thread (Task
  1's callback only does `queue.put`; Task 4's `on_tick` is the only caller of
  `push_samples` for mic data, on the Qt main thread) — done. Engine/panel
  reconfiguration on mic enable/disable, restoring the file's engine afterward (Task 2 +
  Task 4) — done. Error handling via one exception type + warning dialog + toggle revert
  (Task 4, Step 4/7) — done. Path label text update (Task 4, Step 3) — done.
  `requirements.txt` dependency (Task 1, Step 3) — done. Testability via injectable
  stream factory (Task 1) — done. Explicitly out of scope per the design doc (device
  selection, engine/binding changes, non-Linux backends, pause semantics for mic) — none
  of these are touched by any task, confirmed.
- **Placeholder scan:** no TBD/TODO; every step has complete, pasteable code or an exact
  command with expected output.
- **Type consistency:** `MicInputSource.read_available()` returns `np.ndarray | None`
  everywhere it's referenced (Task 1's tests, Task 4's `on_tick`). `mic_source.sample_rate`
  is a `float`, matching what `_configure_for_sample_rate(sample_rate)` expects (same type
  `load_file` already passes it, a `float` from `soundfile.read`). `MicUnavailableError`
  is the only exception type raised by `start()` and the only one caught in
  `on_mic_toggled` — consistent across Task 1 and Task 4.
