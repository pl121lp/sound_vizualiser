# Phase 2e: Transport Toolbar (file select, loop, restart, pause, mic stub)

## Summary

Add a second, always-visible toolbar above the existing "Controls" toolbar in
`frontend/main.py`. It shows the current input file path and lets the user
open a new file (restarting the visualization), loop playback, restart from
the beginning, pause/resume, and toggle a microphone-input mode that is
stubbed (UI only, no capture). The app can now start with no file at all,
launching paused until the user picks one.

## Motivation

Currently `wav_path` is a required positional CLI argument and the file is
loaded once at construction time with no way to change it, pause, restart, or
loop from the UI. This closes several items from `todo.txt` (lines 7-13).

## Architecture

All changes are confined to `frontend/main.py`; no engine/C++ changes and no
new files. `WaveformWindow` gains:

- A `load_file(path)` method that does the work currently inlined in
  `__init__` (read file, construct `Engine`, size frequency-dependent
  panels), reusable both at startup and from the Open File button.
- A new `build_transport_toolbar()` method, called before `build_toolbar()`,
  with `self.addToolBarBreak()` between them so the transport toolbar renders
  as its own top row and the existing Controls toolbar stays on the row below.
- Playback/transport state: `self.loop_enabled`, `self.mic_enabled`,
  `self.has_file` (whether a file is currently loaded).
- `self.args = args` is stored on the instance (currently only used locally
  in `__init__`) so `load_file` can reuse `args.fft_window`,
  `args.band_split_low`, and `args.band_split_high` when rebuilding the
  `Engine` after an Open File selection.

### Startup with no file

`wav_path` becomes optional (`nargs="?"`, default `None`). When `None`:

- `WaveformWindow.__init__` skips `sf.read` and `Engine` construction
  entirely. `self.data = None`, `self.sample_rate` is left unset,
  `self.n_channels = 0`.
- The waveform/spectrum/spectrogram/radial panels are constructed against a
  placeholder `spectrum_len` derived from `args.window_size` alone (spectrum
  length doesn't depend on sample rate), but `SpectrogramPanel` and
  `RadialSpectrumPanel` need *some* sample rate to build their frequency
  grids — they are constructed lazily too: skipped until a file is loaded,
  with their layout slots left empty (a placeholder `QWidget` reserves the
  spot) until `load_file` swaps in real panels.
- The `QTimer` is created but not started.
- The transport toolbar shows "No file loaded" and only **Open File** and
  **Mic** are enabled; **Loop**, **Restart**, **Pause** are disabled (nothing
  to loop/restart/pause).

### Opening / switching files (`load_file`)

Used both for the initial file (if provided on the CLI) and for the Open File
button. Rebuilds engine + frequency-dependent panels in place, per user
selection:

```python
def load_file(self, path):
    data, sample_rate = sf.read(path, dtype="float32", always_2d=True)
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

    self._replace_panel("spectrogram", SpectrogramPanel(self.spectrum_len, sample_rate, self.rate_hz))
    self._replace_panel("radial_spectrum", RadialSpectrumPanel(self.spectrum_len, sample_rate))

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

`_replace_panel(attr, new_widget)` removes the old widget from its parent
layout at the same index, inserts the new one in its place, deletes the old
one (`setParent(None)`), and rebinds `self.<attr>` — preserving stretch
factors and position in `container`'s `QVBoxLayout`.

**Open File button** (`on_open_file`): `QFileDialog.getOpenFileName(self,
"Select Audio File", "", "WAV files (*.wav);;All files (*)")`; if a path is
returned, calls `load_file(path)`. This is the only way "restart the
visualization" happens per the todo — selecting a file always calls the same
rebuild path whether it's the first file or a replacement.

### Transport toolbar contents

Left to right, all as `QAction`s on the new toolbar:

| Control | Type | Behavior |
|---|---|---|
| Path label | `QLabel` | Shows `self.file_path`, "No file loaded", or "Microphone (not implemented)" |
| Open File... | action (button) | Opens file dialog, calls `load_file` |
| Mic | checkable action | Stub toggle, see below |
| Loop | checkable action | Sets `self.loop_enabled`; disabled when no file loaded or Mic on |
| Restart | action (button) | `read_pos = 0`; does not touch pause state |
| Pause | checkable action | `set_paused(checked)`; disabled when no file loaded or Mic on |

`set_paused(paused)` starts/stops `self.timer` and updates the Pause action's
checked state (guard against re-entrant signal emission when called
programmatically, e.g. from EOF handling).

### Mic toggle (stub)

`on_mic_toggled(checked)`:
- `self.mic_enabled = checked`
- Disables Open File, Loop, Restart, Pause actions when checked; re-enables
  them when unchecked (re-enabling only if `self.has_file` is true, since
  with no file loaded those stay disabled regardless).
- When checked: calls `set_paused(True)` and sets the path label to
  "Microphone (not implemented)".
- When unchecked: restores the label via `_update_path_label()` (does not
  auto-resume playback — user can press Pause/Play again).
- No audio capture is implemented; this is purely a UI state toggle for a
  future phase.

### End-of-file / loop behavior

In `on_tick`, replacing the current `if self.read_pos >= len(self.data):
self.timer.stop(); return`:

```python
if self.read_pos >= len(self.data):
    if self.loop_enabled:
        self.read_pos = 0
    else:
        self.set_paused(True)
        return
```

Restart (`on_restart`) only resets `read_pos = 0`; it does not change
play/pause state, matching "seek to start" semantics rather than "play from
start".

### Error handling

- `load_file` failures (e.g. `sf.read` raising on a corrupt/unsupported file)
  are caught and shown via `QtWidgets.QMessageBox.warning`, leaving the
  previously loaded file (or no-file state) intact — a failed Open File
  attempt must not tear down a working session.
- No new engine-side error paths; existing `Engine` construction failures
  propagate as before.

## Testing

- Existing `frontend/tests/test_audio_math.py` is unaffected (no changes to
  `audio_math.py`).
- Add lightweight Qt-level tests where practical (this project has no
  existing Qt widget tests, so we keep new coverage focused on pure logic
  that's easy to extract):
  - Extract the EOF/loop decision into a small pure function if feasible
    (e.g. `next_read_pos(read_pos, chunk_frames, data_len, loop_enabled) ->
    (new_read_pos, should_pause)`) in `audio_math.py`, unit tested the same
    way as `rate_hz_to_chunk_frames` and `update_peak_hold`.
  - Manual verification (per `run` skill / project convention): launch with
    no argument (starts paused, "No file loaded"), launch with a fixture wav
    (autoplays), Open File mid-playback (visualization rebuilds, sample-rate
    dependent panels redraw correctly), Loop toggle wraps at EOF, Restart
    resets position without changing play state, Pause/Play toggles the
    timer, Mic toggle disables file transport controls and shows the stub
    label.

## Out of scope

- Actual microphone capture (explicitly deferred to a later phase per
  `todo.txt` line 16).
- Non-WAV file format support in the Open File dialog.
- Persisting the last-opened file path across app restarts.
