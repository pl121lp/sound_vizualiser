# Phase 2e Design — Live Microphone Input

## Scope

Wires up the "Mic" toolbar toggle (added in the transport-toolbar work, currently a stub
that just disables file transport controls and shows "Microphone (not implemented)") to
actually capture and visualize live audio, per `project_spec_final.md` Phase 2e ("Live
audio capture harness (PortAudio or similar) as an alternative input source to WAV
files").

Out of scope (explicitly deferred, confirmed with user):
- Input-device selection UI — uses the system default input device only.
- Any change to the C++ engine or pybind11 bindings — the engine stays capture-agnostic,
  same `push_samples`/`get_latest_features` contract used by WAV playback today.
- Cross-thread engine access — mic audio arrives on a PortAudio callback thread but is
  never pushed into the engine from that thread (see Thread safety below).
- macOS/Windows-specific backends — only a Linux-capable (in practice, cross-platform via
  PortAudio) backend is implemented, but behind an interface that doesn't assume Linux.

## Library choice

`sounddevice` (a PortAudio binding) is added as a new frontend dependency
(`frontend/requirements.txt`). PortAudio itself already supports Linux/macOS/Windows, so
the interface described below is portable in practice even though only Linux is being
tested right now. Rejected alternatives: raw ALSA bindings (genuinely Linux-only, more
code, no benefit here) and adding capture to the C++ engine via PortAudio (bigger blast
radius — new engine code, new bindings, new native build dependency — for no gain, since
WAV file reading already happens in the frontend, not the engine).

## New module: `frontend/mic_input.py`

A small, deliberately narrow interface so a future alternate backend is a drop-in
replacement:

```python
class MicUnavailableError(Exception):
    """Raised when no mic capture backend/device is usable."""

class MicInputSource:
    sample_rate: float
    channels: int  # always 1 (mono capture)

    def __init__(self, stream_factory=sounddevice.InputStream): ...
    def start(self) -> None: ...   # raises MicUnavailableError on failure
    def stop(self) -> None: ...
    def read_available(self) -> np.ndarray | None: ...  # None if nothing new
```

- `start()` queries the default input device's sample rate (`sounddevice.query_devices`),
  opens a mono `float32` `InputStream` via `stream_factory` (constructor-injected for
  testability — default is `sounddevice.InputStream`), and wraps any failure (missing
  `sounddevice` import, no default input device, PortAudio open failure,
  `sounddevice.PortAudioError`) into one `MicUnavailableError` so callers have a single
  `except` to handle.
- The stream's callback runs on PortAudio's own thread. It does **no** engine work — it
  only appends the incoming mono frame block onto a `queue.Queue` (thread-safe by
  construction, no manual locking needed).
- `read_available()` (called from the Qt main thread) drains the queue non-blockingly,
  concatenating any accumulated blocks into one array, returning `None` if the queue was
  empty since the last call.
- `stop()` closes and stops the PortAudio stream and drops the queue reference.

## Thread safety

The C++ engine's `push_samples`/`get_latest_features` are only ever called from the Qt
main thread today (file playback already does this via the `QTimer` tick). The spec
explicitly defers cross-thread engine safety to Phase 4 ("Confirm/extend the C API for
thread-safety"). To avoid pulling that work forward, the mic callback thread never touches
the engine — it only feeds the thread-safe queue above. The existing tick timer (same one
driving file playback, paced by the Rate slider) drains the queue and calls
`push_samples`/`get_latest_features` from the main thread, exactly like the file path
does. No new concurrency surface is introduced in the engine.

## `main.py` changes

Two refactors extract logic that both file-playback and mic-playback now share:

- `_configure_for_sample_rate(sample_rate)` — extracted from `load_file()`: creates the
  `Engine`, rebuilds the spectrogram/radial panels via the existing `_replace_panel`, and
  sets the tick timer's interval for the given sample rate. Callers:
  - `load_file()` — with the file's sample rate (unchanged behavior).
  - Enabling mic — with `self.mic_source.sample_rate`.
  - Disabling mic, if a file was previously loaded — with `self.sample_rate` again, to
    restore the file's engine/panels.
- `_process_frame(frame)` — extracted from `on_tick()`: the block that feeds `frame` into
  the waveform/spectrum/spectrogram/radial/meters (today's lines updating
  `self.curve`, `self.spectrum_bars`, `self.spectrogram`, `self.radial_spectrum`, the peak
  holds, and the 7 `BarMeter`s). Both the file-tick and new mic-tick paths call this after
  obtaining a frame.

`on_tick()` branches on `self.mic_enabled`:

```python
def on_tick(self):
    if self.mic_enabled:
        chunk = self.mic_source.read_available()
        if chunk is None:
            return  # nothing captured since last tick
        self.engine.push_samples(chunk, 1)
    else:
        # existing file-path logic: advance_or_pause, slice self.data, push_samples
        ...
    frame = self.engine.get_latest_features()
    self._process_frame(frame)
```

`on_mic_toggled(checked)`:

- **Enabling**: construct and `start()` a `MicInputSource`. On `MicUnavailableError`, show
  a warning dialog (same `QMessageBox.warning` pattern as the existing "Failed to load
  file" path) and revert the toggle (`blockSignals` around `setChecked(False)`, matching
  the existing revert pattern elsewhere in the file) without changing any other state. On
  success: `_configure_for_sample_rate(self.mic_source.sample_rate)`, then
  `set_paused(False)` to start the timer. Loop/restart/pause stay disabled for mic (already
  stubbed via `_set_transport_enabled`) since none of those concepts apply to a live
  stream.
- **Disabling**: `self.mic_source.stop(); self.mic_source = None`. If `self.has_file`,
  call `_configure_for_sample_rate(self.sample_rate)` to restore the file's engine/panels
  and re-pause (`set_paused(True)`) — matches today's behavior of leaving file transport
  paused until the user presses Pause/Play. `read_pos` is untouched, so file playback
  resumes from where it left off, not from the start. If no file was loaded, transport
  stays disabled/idle as before.
- `_update_path_label()` shows `"Microphone (default input device)"` while mic is active,
  replacing the current `"(not implemented)"` placeholder.

`closeEvent()` also stops `self.mic_source` if active, alongside the existing
`self.timer.stop()` (same Wayland-teardown-ordering concern already documented there).

`requirements.txt` gains `sounddevice`.

## Error handling

All mic-unavailable cases (library not installed, no default input device, PortAudio
failing to open the stream) surface as one `MicUnavailableError` from `mic_input.py`,
caught once in `on_mic_toggled` and shown as a warning dialog with the toggle reverted —
mic is a best-effort optional feature, never a hard crash, consistent with how a bad file
path is already handled in `load_file()`.

## Testing

- `MicInputSource` accepts an injectable `stream_factory`, so a unit test substitutes a
  fake `InputStream`-like object that synchronously invokes the registered callback with
  known sample blocks, then asserts `read_available()` drains/concatenates correctly and
  returns `None` when the queue is empty — no real audio hardware required, following the
  existing `audio_math.py`/pytest pattern (`frontend/tests/`).
- The `main.py` wiring (toggle handler, tick branching, panel/engine reconfiguration) is
  UI glue with no existing test coverage (consistent with the rest of `WaveformWindow`) —
  verified manually: toggle mic on/off with and without a file loaded, confirm
  visualizations respond to live input, confirm file playback resumes correctly after
  disabling mic, and confirm a missing/denied mic device shows the warning dialog and
  reverts the toggle instead of crashing.

## Out of scope for 2e

- Input-device selection (system default only).
- Engine/binding changes.
- Non-Linux backends.
- Pause semantics for mic (mic has no pause/loop/restart, per existing stub).
