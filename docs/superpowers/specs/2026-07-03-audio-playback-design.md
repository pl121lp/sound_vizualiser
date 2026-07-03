# Optional Audio Playback for File Input

## Goal

Let the user optionally hear the loaded audio file while the analytics/visualization
run, via a toggle in the transport toolbar. Does not apply to microphone input —
the toggle is only enabled when a file is loaded and mic mode is off.

## Non-goals

- No volume/gain control (system volume is sufficient; YAGNI).
- No output device selection (uses the default output device, matching how mic
  input already uses the default input device).
- No sample-accurate lockstep between playback and the visualization — see
  "Sync model" below for the accepted trade-off.

## Portability

`sounddevice` (already a project dependency, already used by `mic_input.py` for
mic capture) binds PortAudio, which abstracts the OS audio backend (ALSA/
PulseAudio/JACK on Linux, CoreAudio on macOS, WASAPI/DirectSound/MME on
Windows). The `OutputStream(samplerate=..., channels=..., dtype=..., callback=...)`
call shape used here is identical across platforms, so no OS-specific code is
introduced. This mirrors the mic-input implementation, which is already
cross-platform by the same mechanism.

## Sync model

Playback runs on its own real-time clock: the PortAudio callback thread
advances its own position independently of the Qt-timer-driven `read_pos` used
for visualization. Both start from the same frame position and free-run in
real time, so they track each other closely without being sample-locked. This
avoids blocking the Qt GUI thread (the rejected alternative was writing audio
synchronously inside `on_tick()`, which risks stalling the UI if the output
buffer is full) and keeps the implementation decoupled and simple.

## New module: `frontend/audio_playback.py`

Mirrors the shape of `mic_input.py`:

```python
class AudioPlaybackUnavailableError(Exception):
    """Raised when audio output can't be started."""

def _default_stream_factory(**kwargs):
    if sd is None:
        raise AudioPlaybackUnavailableError("sounddevice/PortAudio not available")
    return sd.OutputStream(**kwargs)

class AudioPlaybackSource:
    """Plays back an in-memory audio buffer through the default output device.

    Mirrors MicInputSource's shape (start/stop + injectable stream_factory) so
    call sites and tests follow the same pattern.
    """

    def __init__(self, data, sample_rate, stream_factory=None):
        ...

    def start(self, start_frame=0): ...
    def stop(self): ...
    def seek(self, frame): ...
    def set_paused(self, paused): ...
    def set_loop(self, loop): ...
```

Internal state:
- `_data`, `_sample_rate` — the already-loaded file buffer, passed in (no file
  I/O in this module).
- `_pos` — internal read cursor, advanced only by the callback thread.
- `_paused`, `_loop` — plain attributes, settable from the main thread (safe
  under the GIL for simple flag/int writes).
- `finished` — set by the callback when non-looping playback runs past the end
  of the buffer; polled from the main thread in `on_tick()` (no cross-thread Qt
  calls).

Callback behavior:
- While paused: zero-fill `outdata`, don't advance `_pos`.
- Normal: copy up to `frames` samples from `_data[_pos:]` into `outdata`,
  zero-fill any short tail, advance `_pos`.
- End of buffer, looping: wrap `_pos` back to 0 before copying.
- End of buffer, not looping: zero-fill `outdata`, set `finished = True`, raise
  `sd.CallbackStop()`.

## Integration in `frontend/main.py`

New state: `self.playback_enabled = False`, `self.playback_source = None`.

New toolbar control: a checkable `QAction("Play Audio")` added to the
transport toolbar alongside Loop/Restart/Pause. Gated by the same
`_set_transport_enabled(has_file)` call already used for those actions (i.e.
enabled only when a file is loaded and mic is off).

Wiring:

- **`on_playback_toggled(checked)`** (new handler):
  - `checked`: construct `AudioPlaybackSource(self.data, self.sample_rate)`,
    call `start(self.read_pos)`. On `AudioPlaybackUnavailableError`, show a
    `QMessageBox.warning` and un-check the action (mirrors
    `on_mic_toggled`'s failure path). On success, call
    `set_loop(self.loop_enabled)` and
    `set_paused(self.pause_action.isChecked())`, store the source, set
    `playback_enabled = True`.
  - not `checked`: `stop()` the source if present, clear it, set
    `playback_enabled = False`.
- **`on_pause_toggled`**: also calls `self.playback_source.set_paused(paused)`
  when a source is active.
- **`on_restart`**: also calls `self.playback_source.seek(0)` when active.
- **`on_loop_toggled`**: also calls `self.playback_source.set_loop(checked)`
  when active.
- **`on_mic_toggled(True)`**: force `playback_action.setChecked(False)` before
  switching to mic mode (stops and clears any active source via the toggle
  handler above).
- **`load_file()`**: force `playback_action.setChecked(False)` before loading
  the new buffer/sample rate (stops any active source; user re-enables
  playback for the new file explicitly).
- **`on_tick()`**: alongside the existing `should_pause` end-of-file check,
  poll `self.playback_source.finished` and un-check `playback_action` when the
  file has ended without looping.
- **`closeEvent`**: stop `playback_source` alongside the existing mic-source
  cleanup.

No new CLI arguments.

## Testing

`frontend/tests/test_audio_playback.py`, structured like
`test_mic_input.py`: a fake stream/factory test double that captures the
`callback` passed to it and lets the test invoke it directly with a fake
`outdata` buffer. Cases:

- Normal read copies the expected samples and advances `_pos`.
- While paused: zero-fill, `_pos` unchanged.
- Loop wraps `_pos` back to 0 and continues copying.
- Non-loop run-off-the-end zero-fills the tail, sets `finished = True`, and
  raises `sd.CallbackStop`.
- `seek()` repositions `_pos`.

No GUI/integration test against `main.py`'s toggle wiring — consistent with
how `MicInputSource` is tested today (unit-tested directly; the toolbar
handler itself isn't).
