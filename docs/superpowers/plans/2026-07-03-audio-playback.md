# Optional Audio Playback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Play Audio" toggle to the transport toolbar in `frontend/main.py` that
optionally plays the loaded file's audio through the default output device while the
analytics/visualization run. Does not apply to microphone input.

**Architecture:** A new `frontend/audio_playback.py` module wraps a `sounddevice.OutputStream`
behind a narrow `start()`/`stop()`/`seek()`/`set_paused()`/`set_loop()` interface, mirroring
the existing `frontend/mic_input.py` pattern (injectable `stream_factory` for testability, one
`*UnavailableError` exception type). The PortAudio callback thread owns its own read
position into the already-loaded `self.data` buffer and advances it in real time,
independently of the Qt-timer-driven `read_pos` used for visualization — the two clocks are
decoupled but start from the same frame and both run in real time, so they track each other
closely without being sample-locked. `WaveformWindow`'s existing transport handlers
(pause/restart/loop/mic-toggle/load_file/tick/close) are extended to mirror their state onto
the playback source when one is active.

**Tech Stack:** Python 3.13, PyQt5, pyqtgraph, numpy, `sounddevice` (already a dependency,
already used by `mic_input.py`), pytest.

## Global Constraints

- No changes to the C++ engine or pybind11 bindings (`engine/`) — playback never touches
  `sound_viz_py.Engine`; it only reads the same in-memory `self.data` buffer that feeds it.
- No volume control and no output-device-selection UI — default output device only, at
  original sample level (see `docs/superpowers/specs/2026-07-03-audio-playback-design.md`).
- The "Play Audio" toggle must be enabled only when a file is loaded and mic mode is off —
  gated the same way as the existing Loop/Restart/Pause actions via `_set_transport_enabled`.
- Loading a new file or switching to mic input must stop and un-check any active playback
  (per the design's "auto-stop and uncheck" behavior) rather than trying to carry it over.
- Pause/Restart/Loop must fully mirror onto the playback source while one is active (per the
  design's "fully mirror" transport behavior).
- Follow the existing repo pattern of catching all playback-unavailable conditions into one
  exception type, surfaced as a `QMessageBox.warning` with the toggle reverted — never a
  crash.
- Run frontend tests via `./frontend/run.sh -m pytest <path> -v` from the repo root.
- Run the app for manual verification via `./frontend/run.sh frontend/main.py frontend/fixtures/test_tone.wav`
  from the repo root (`frontend/fixtures/test_tone.wav` is a 3.0s, 44100Hz, mono test tone).

---

### Task 1: `audio_playback.py` — playback backend with injectable stream factory

**Files:**
- Create: `frontend/audio_playback.py`
- Test: `frontend/tests/test_audio_playback.py`

**Interfaces:**
- Produces: `AudioPlaybackUnavailableError` (exception), `AudioPlaybackSource` class with
  `__init__(self, data: np.ndarray, sample_rate: float, stream_factory=None)`,
  `start(self, start_frame: int = 0) -> None`, `stop(self) -> None`, `seek(self, frame: int) -> None`,
  `set_paused(self, paused: bool) -> None`, `set_loop(self, loop: bool) -> None`, and a
  `finished: bool` attribute (readable, set internally when non-looping playback runs off
  the end of `data`).

- [ ] **Step 1: Write the failing tests**

Create `frontend/tests/test_audio_playback.py`:

```python
import os
import sys

import numpy as np
import pytest
import sounddevice as sd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from audio_playback import AudioPlaybackSource, AudioPlaybackUnavailableError


class FakeStream:
    def __init__(self, callback, samplerate, channels):
        self.callback = callback
        self.samplerate = samplerate
        self.channels = channels
        self.started = False
        self.closed = False

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def close(self):
        self.closed = True

    def feed(self, frames):
        outdata = np.zeros((frames, self.channels), dtype=np.float32)
        self.callback(outdata, frames, None, None)
        return outdata


def make_fake_factory():
    created = {}

    def factory(**kwargs):
        stream = FakeStream(
            callback=kwargs["callback"],
            samplerate=kwargs["samplerate"],
            channels=kwargs["channels"],
        )
        created["stream"] = stream
        return stream

    return factory, created


def make_data():
    return np.array([[0.1], [0.2], [0.3], [0.4]], dtype=np.float32)


def test_normal_read_copies_samples_and_advances_pos():
    factory, created = make_fake_factory()
    source = AudioPlaybackSource(make_data(), 48000.0, stream_factory=factory)
    source.start(0)

    outdata = created["stream"].feed(2)

    np.testing.assert_allclose(outdata, [[0.1], [0.2]])
    assert source._pos == 2


def test_paused_zero_fills_and_does_not_advance():
    factory, created = make_fake_factory()
    source = AudioPlaybackSource(make_data(), 48000.0, stream_factory=factory)
    source.start(0)
    source.set_paused(True)

    outdata = created["stream"].feed(2)

    np.testing.assert_allclose(outdata, np.zeros((2, 1)))
    assert source._pos == 0


def test_loop_wraps_position_to_zero_at_end():
    factory, created = make_fake_factory()
    source = AudioPlaybackSource(make_data(), 48000.0, stream_factory=factory)
    source.start(0)
    source.set_loop(True)
    source.seek(4)  # exactly at the end of the 4-frame buffer

    outdata = created["stream"].feed(2)

    np.testing.assert_allclose(outdata, [[0.1], [0.2]])
    assert source._pos == 2
    assert source.finished is False


def test_non_loop_end_zero_fills_sets_finished_and_raises_callback_stop():
    factory, created = make_fake_factory()
    source = AudioPlaybackSource(make_data(), 48000.0, stream_factory=factory)
    source.start(0)
    source.seek(4)  # exactly at the end of the 4-frame buffer

    with pytest.raises(sd.CallbackStop):
        created["stream"].feed(2)

    assert source.finished is True


def test_seek_repositions_pos():
    factory, _ = make_fake_factory()
    source = AudioPlaybackSource(make_data(), 48000.0, stream_factory=factory)
    source.start(0)

    source.seek(2)

    assert source._pos == 2


def test_start_wraps_factory_failure_in_playback_unavailable_error():
    def failing_factory(**kwargs):
        raise RuntimeError("no default output device")

    source = AudioPlaybackSource(make_data(), 48000.0, stream_factory=failing_factory)

    with pytest.raises(AudioPlaybackUnavailableError):
        source.start()


def test_stop_stops_and_closes_stream():
    factory, created = make_fake_factory()
    source = AudioPlaybackSource(make_data(), 48000.0, stream_factory=factory)
    source.start()

    source.stop()

    assert created["stream"].started is False
    assert created["stream"].closed is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./frontend/run.sh -m pytest frontend/tests/test_audio_playback.py -v`
Expected: collection error / `ModuleNotFoundError: No module named 'audio_playback'` (the
module doesn't exist yet).

- [ ] **Step 3: Write the implementation**

Create `frontend/audio_playback.py`:

```python
import numpy as np

try:
    import sounddevice as sd
except Exception:
    sd = None


class AudioPlaybackUnavailableError(Exception):
    """Raised when audio output can't be started."""


def _default_stream_factory(**kwargs):
    if sd is None:
        raise AudioPlaybackUnavailableError("sounddevice/PortAudio not available")
    return sd.OutputStream(**kwargs)


class AudioPlaybackSource:
    """Plays back an in-memory audio buffer through the default output device.

    Mirrors MicInputSource's shape (start()/stop() + injectable stream_factory) so
    call sites and tests follow the same pattern. The callback advances its own
    position independently of any caller-side read cursor -- callers that want the
    two to track (e.g. after a restart) must call seek() explicitly.
    """

    def __init__(self, data, sample_rate, stream_factory=None):
        self._data = data
        self._sample_rate = sample_rate
        self._stream_factory = stream_factory or _default_stream_factory
        self._stream = None
        self._pos = 0
        self._paused = False
        self._loop = False
        self.finished = False

    def _callback(self, outdata, frames, time_info, status):
        if self._paused:
            outdata.fill(0)
            return

        remaining = len(self._data) - self._pos
        if remaining <= 0:
            if self._loop:
                self._pos = 0
                remaining = len(self._data)
            else:
                outdata.fill(0)
                self.finished = True
                raise sd.CallbackStop()

        n = min(frames, remaining)
        outdata[:n] = self._data[self._pos:self._pos + n]
        if n < frames:
            outdata[n:] = 0
        self._pos += n

    def start(self, start_frame=0):
        self._pos = start_frame
        self.finished = False
        try:
            self._stream = self._stream_factory(
                samplerate=self._sample_rate,
                channels=self._data.shape[1],
                dtype="float32",
                callback=self._callback,
            )
            self._stream.start()
        except AudioPlaybackUnavailableError:
            raise
        except Exception as exc:
            raise AudioPlaybackUnavailableError(str(exc)) from exc

    def stop(self):
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def seek(self, frame):
        self._pos = frame

    def set_paused(self, paused):
        self._paused = paused

    def set_loop(self, loop):
        self._loop = loop
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./frontend/run.sh -m pytest frontend/tests/test_audio_playback.py -v`
Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/audio_playback.py frontend/tests/test_audio_playback.py
git commit -m "feat: add AudioPlaybackSource for file-buffer playback via sounddevice"
```

---

### Task 2: Wire the "Play Audio" toggle into the transport toolbar

**Files:**
- Modify: `frontend/main.py:1-21` (imports), `frontend/main.py:186-191` (`__init__` state),
  `frontend/main.py:374-380` (`build_transport_toolbar`), `frontend/main.py:390-394`
  (`_set_transport_enabled`)

**Interfaces:**
- Consumes: `AudioPlaybackSource`, `AudioPlaybackUnavailableError` from Task 1's
  `frontend/audio_playback.py`.
- Produces: `self.playback_action` (QAction), `self.playback_enabled` (bool),
  `self.playback_source` (`AudioPlaybackSource | None`), `on_playback_toggled(self, checked)`
  method — later tasks wire other handlers to call `self.playback_source` methods when it's
  not `None`.

- [ ] **Step 1: Add the import**

In `frontend/main.py`, find:

```python
from mic_input import MicInputSource, MicUnavailableError
```

Replace with:

```python
from mic_input import MicInputSource, MicUnavailableError
from audio_playback import AudioPlaybackSource, AudioPlaybackUnavailableError
```

- [ ] **Step 2: Add playback state to `__init__`**

Find:

```python
        self.has_file = False
        self.file_path = None
        self.loop_enabled = False
        self.mic_enabled = False
        self.mic_source = None
        self.engine = None
```

Replace with:

```python
        self.has_file = False
        self.file_path = None
        self.loop_enabled = False
        self.mic_enabled = False
        self.mic_source = None
        self.engine = None
        self.playback_enabled = False
        self.playback_source = None
```

- [ ] **Step 3: Add the toolbar action**

Find (in `build_transport_toolbar`):

```python
        self.pause_action = QtWidgets.QAction("Pause", self)
        self.pause_action.setCheckable(True)
        self.pause_action.toggled.connect(self.on_pause_toggled)
        toolbar.addAction(self.pause_action)

        self._update_path_label()
        self._set_transport_enabled(False)
```

Replace with:

```python
        self.pause_action = QtWidgets.QAction("Pause", self)
        self.pause_action.setCheckable(True)
        self.pause_action.toggled.connect(self.on_pause_toggled)
        toolbar.addAction(self.pause_action)

        self.playback_action = QtWidgets.QAction("Play Audio", self)
        self.playback_action.setCheckable(True)
        self.playback_action.toggled.connect(self.on_playback_toggled)
        toolbar.addAction(self.playback_action)

        self._update_path_label()
        self._set_transport_enabled(False)
```

- [ ] **Step 4: Gate the action in `_set_transport_enabled`**

Find:

```python
    def _set_transport_enabled(self, has_file):
        file_controls_enabled = has_file and not self.mic_enabled
        self.loop_action.setEnabled(file_controls_enabled)
        self.restart_action.setEnabled(file_controls_enabled)
        self.pause_action.setEnabled(file_controls_enabled)
```

Replace with:

```python
    def _set_transport_enabled(self, has_file):
        file_controls_enabled = has_file and not self.mic_enabled
        self.loop_action.setEnabled(file_controls_enabled)
        self.restart_action.setEnabled(file_controls_enabled)
        self.pause_action.setEnabled(file_controls_enabled)
        self.playback_action.setEnabled(file_controls_enabled)
```

- [ ] **Step 5: Add the toggle handler**

Find (in `on_mic_toggled`, the end of the method):

```python
        self._update_path_label()

    def on_loop_toggled(self, checked):
        self.loop_enabled = checked
```

Replace with:

```python
        self._update_path_label()

    def on_playback_toggled(self, checked):
        if checked:
            source = AudioPlaybackSource(self.data, self.sample_rate)
            try:
                source.start(self.read_pos)
            except AudioPlaybackUnavailableError as exc:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Audio playback unavailable",
                    f"Could not start audio playback:\n{exc}",
                )
                self.playback_action.blockSignals(True)
                self.playback_action.setChecked(False)
                self.playback_action.blockSignals(False)
                return

            source.set_loop(self.loop_enabled)
            source.set_paused(self.pause_action.isChecked())
            self.playback_source = source
            self.playback_enabled = True
        else:
            if self.playback_source is not None:
                self.playback_source.stop()
                self.playback_source = None
            self.playback_enabled = False

    def on_loop_toggled(self, checked):
        self.loop_enabled = checked
```

- [ ] **Step 6: Manually verify the toggle starts and stops playback**

Run: `./frontend/run.sh frontend/main.py frontend/fixtures/test_tone.wav`

Click "Play Audio". Expected: the 3-second test tone becomes audible through the default
output device, looping in sync with whatever the Loop toggle is currently set to have no
effect yet (loop mirroring comes in Task 3 — for now just confirm sound starts). Click
"Play Audio" again. Expected: sound stops immediately, no crash, no warning dialog (assuming
a working output device on this machine). Close the window when confirmed.

If there is no working output device on this machine, expected instead: a "Audio playback
unavailable" warning dialog appears and the toggle reverts to unchecked — confirm no crash
and that Loop/Restart/Pause continue to work normally afterward.

- [ ] **Step 7: Commit**

```bash
git add frontend/main.py
git commit -m "feat: wire Play Audio toggle into transport toolbar"
```

---

### Task 3: Mirror Pause/Restart/Loop/mic/load_file/tick/close onto the playback source

**Files:**
- Modify: `frontend/main.py` (`on_playback_toggled`'s neighboring handlers: `on_loop_toggled`,
  `on_restart`, `set_paused`, `on_mic_toggled`, `load_file`, `on_tick`, `closeEvent`)

**Interfaces:**
- Consumes: `self.playback_source` and `self.playback_action` from Task 2.

- [ ] **Step 1: Mirror Loop**

Find:

```python
    def on_loop_toggled(self, checked):
        self.loop_enabled = checked
```

Replace with:

```python
    def on_loop_toggled(self, checked):
        self.loop_enabled = checked
        if self.playback_source is not None:
            self.playback_source.set_loop(checked)
```

- [ ] **Step 2: Mirror Restart**

Find:

```python
    def on_restart(self):
        self.read_pos = 0
```

Replace with:

```python
    def on_restart(self):
        self.read_pos = 0
        if self.playback_source is not None:
            self.playback_source.seek(0)
```

- [ ] **Step 3: Mirror Pause**

Find:

```python
    def set_paused(self, paused):
        if paused:
            self.timer.stop()
        else:
            self.timer.start()
        if self.pause_action.isChecked() != paused:
```

Replace with:

```python
    def set_paused(self, paused):
        if paused:
            self.timer.stop()
        else:
            self.timer.start()
        if self.playback_source is not None:
            self.playback_source.set_paused(paused)
        if self.pause_action.isChecked() != paused:
```

- [ ] **Step 4: Stop playback before switching to mic**

Find (start of `on_mic_toggled`):

```python
    def on_mic_toggled(self, checked):
        if checked:
            mic_source = MicInputSource()
```

Replace with:

```python
    def on_mic_toggled(self, checked):
        if checked:
            if self.playback_action.isChecked():
                self.playback_action.setChecked(False)

            mic_source = MicInputSource()
```

- [ ] **Step 5: Stop playback before loading a new file**

Find (start of `load_file`):

```python
    def load_file(self, path):
        try:
            data, sample_rate = sf.read(path, dtype="float32", always_2d=True)
```

Replace with:

```python
    def load_file(self, path):
        if self.playback_action.isChecked():
            self.playback_action.setChecked(False)

        try:
            data, sample_rate = sf.read(path, dtype="float32", always_2d=True)
```

- [ ] **Step 6: Poll for end-of-playback each tick**

Find (start of `on_tick`):

```python
    def on_tick(self):
        if self.mic_enabled:
```

Replace with:

```python
    def on_tick(self):
        if self.playback_source is not None and self.playback_source.finished:
            self.playback_action.setChecked(False)

        if self.mic_enabled:
```

- [ ] **Step 7: Stop playback on window close**

Find:

```python
        self.timer.stop()
        if self.mic_source is not None:
            self.mic_source.stop()
        super().closeEvent(event)
```

Replace with:

```python
        self.timer.stop()
        if self.mic_source is not None:
            self.mic_source.stop()
        if self.playback_source is not None:
            self.playback_source.stop()
        super().closeEvent(event)
```

- [ ] **Step 8: Manually verify full transport mirroring**

Run: `./frontend/run.sh frontend/main.py frontend/fixtures/test_tone.wav`

1. Click "Play Audio" — tone becomes audible (or the unavailable-dialog path, per Task 2).
2. Click "Pause" — both the visualization and the audio stop/mute together. Click "Pause"
   again — both resume together.
3. Click "Restart" — audio audibly jumps back to the start of the tone in sync with the
   waveform display resetting.
4. Click "Loop" on, then let the 3-second tone play to the end — expected: it loops back to
   the start audibly instead of stopping, and the "Play Audio" toggle stays checked.
5. Click "Loop" off, let the tone play to the end again — expected: audio stops, and
   "Play Audio" un-checks itself automatically (poll from Task 3 Step 6), while the
   visualization's own Pause toggle also gets checked per the pre-existing end-of-file
   behavior.
6. With "Play Audio" checked, click "Mic" on — expected: "Play Audio" un-checks and audio
   stops immediately (assuming a working mic device; otherwise confirm the mic-unavailable
   path leaves "Play Audio" and file transport untouched).
7. With "Play Audio" checked, click "Open File..." and pick `frontend/fixtures/test_tone.wav`
   again — expected: "Play Audio" un-checks and the new file loads normally; re-checking it
   plays the new file from the start.
8. Close the window while "Play Audio" is checked — expected: clean shutdown, no crash, no
   hung audio.

- [ ] **Step 9: Run the full test suite**

Run: `./frontend/run.sh -m pytest frontend/tests -v`
Expected: all tests PASS (no regressions in `test_audio_math.py`, `test_mic_input.py`,
`test_audio_playback.py`).

- [ ] **Step 10: Commit**

```bash
git add frontend/main.py
git commit -m "feat: mirror pause/restart/loop/mic/load/close onto audio playback"
```
