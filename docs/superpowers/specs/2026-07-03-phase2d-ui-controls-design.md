# Phase 2d Design — UI Controls (visualization toggles + update-rate)

## Scope

Phase 2d is entirely frontend — no changes to the C++ engine or pybind11 bindings.
Confirmed via code inspection: `EngineConfig.update_rate_hz` is advisory only (stored,
never read by any DSP logic — comment in `feature_frame.h` says so explicitly), and
`window_size` is baked into ring-buffer construction with no runtime setter. So the rate
control operates purely on the frontend's own tick pacing, and analysis window size stays
fixed for this phase (CLI-only, unchanged from Phase 1d).

Two additions:
- A `QToolBar` on `WaveformWindow` with 5 checkable panel-toggle actions and an
  update-rate slider, both keyboard- and mouse-driven.
- One new pure helper, `rate_hz_to_chunk_frames`, added to `audio_math.py` and unit-tested,
  extracted from the inline chunk-size math that already exists in `WaveformWindow.__init__`.

Out of scope (explicitly deferred, confirmed with user):
- Restart / loop playback buttons and mic-input source selection — separate future work,
  tracked in `todo.txt`, not part of this phase.
- Runtime-adjustable analysis window size or FFT window type — engine limitation, stays
  CLI-only.
- Persisting toggle/rate state across restarts.

## Panels and their toggle identities

Five independently toggleable units, each checked (visible) by default on startup:

| Toggle | Widget(s) controlled |
|---|---|
| Waveform | `self.waveform_plot` |
| Spectrum | `self.spectrum_plot` (bars + peak-hold dots) |
| Spectrogram | `self.spectrogram` |
| Radial | `self.radial_spectrum` |
| Meters | `meters_layout`'s container widget (all 7 `BarMeter`s as one unit) |

The meters row is one toggle, not seven — the 7 meters are cheap and conceptually one
"readout" panel, not five (matching the spec's `2d. UI controls` framing of one
"visualization-mode selector" alongside the rate slider, not per-meter granularity).

## Toolbar layout

A single `QToolBar` added to `WaveformWindow` via `addToolBar`, built in a new
`_build_toolbar()` method called from `__init__`:

```
[Waveform] [Spectrum] [Spectrogram] [Radial] [Meters]      Rate: [====O----] 30 Hz
```

- The 5 panel toggles are checkable `QAction`s (`setCheckable(True)`, `setChecked(True)`
  initially), added directly to the toolbar so they render as toggle buttons.
- The rate slider is a `QSlider(QtCore.Qt.Horizontal)` wrapped in a `QWidgetAction` so it
  can sit inline in the same toolbar, next to a `QLabel` showing the current rate
  (`"NN Hz"`), updated on every `valueChanged`.
- No menu bar, no separate dialog — everything needed is visible and reachable in one bar.

## Keyboard shortcuts

- Number keys `1`–`5` map to the same 5 `QAction`s as the toolbar buttons
  (`action.setShortcut(QtGui.QKeySequence(str(n)))`) — pressing a number toggles the exact
  same action as clicking its toolbar button, so there is one code path
  (`toggled` signal), not two.
- `Up` / `Down` arrow keys are bound to two additional non-visible `QAction`s
  (`setShortcut("Up"/"Down")`, not added to the toolbar) that call
  `self.rate_slider.setValue(self.rate_slider.value() + 5)` /
  `... - 5`, clamped by the slider's own `setRange(5, 60)` — so keyboard and mouse drive
  the identical `valueChanged` handler.

## Rate control mechanics

Slider: `setRange(5, 60)`, `setSingleStep(5)`, `setTickInterval(5)`,
`setValue(round(args.update_rate / 5) * 5)` clamped into range at construction.

`on_rate_changed(new_rate_hz)`, connected to the slider's `valueChanged`:

```python
def on_rate_changed(self, new_rate_hz):
    self.chunk_frames = rate_hz_to_chunk_frames(self.sample_rate, new_rate_hz)
    interval_ms = max(1, int(1000 * self.chunk_frames / self.sample_rate))
    self.tick_interval_s = interval_ms / 1000.0
    self.timer.setInterval(interval_ms)
    self.rate_label.setText(f"{new_rate_hz} Hz")
```

- `self.tick_interval_s` must be updated in lockstep with the timer interval since it
  directly feeds `update_peak_hold`'s decay math (`PEAK_DECAY_PER_SECOND * dt`) and the
  peak-meter hold/decay logic in `on_tick` — a stale value would make peak-hold decay at
  the wrong real-world rate after a rate change.
- `read_pos` (playback position in the source audio) is untouched — only the chunk size
  read per tick changes going forward; no seek, no restart.
- `rate_hz_to_chunk_frames(sample_rate, rate_hz)` is a new pure function in
  `audio_math.py`:

```python
def rate_hz_to_chunk_frames(sample_rate: float, rate_hz: float) -> int:
    return max(1, round(sample_rate / rate_hz))
```

  `WaveformWindow.__init__` is updated to call this same helper instead of its current
  inline `max(1, round(sample_rate / args.update_rate))`, so construction-time and
  runtime rate changes go through identical logic. Unit tests mirror the existing
  `test_audio_math.py` style: typical rate, very low rate (large chunk), very high rate
  clamped by the `max(1, ...)` floor.

## Panel visibility mechanics

Each toggle `QAction`'s `toggled(bool)` signal is connected to a handler that:
1. Calls `widget.setVisible(checked)` on the controlled widget(s) — Qt's `QVBoxLayout`
   automatically reclaims/restores space for hidden/shown widgets, no manual stretch-factor
   changes needed.
2. Sets the corresponding boolean flag (`self.show_waveform`, `self.show_spectrum`,
   `self.show_spectrogram`, `self.show_radial`, `self.show_meters`), all `True` initially.

`on_tick()` gates each panel's per-tick compute behind its flag, skipping work entirely
while hidden (agreed: cheaper than always-computing, and a small visual jump on re-show is
acceptable):

- `self.curve.setData(...)` — behind `show_waveform`.
- `self.spectrum_bars.setOpts(...)` and the spectrum-max auto-range check — behind
  `show_spectrum`.
- `self.spectrogram.update(...)` — behind `show_spectrogram`.
- `self.radial_spectrum.update(...)` — behind `show_radial`.
- The 7 `meter.update_value(...)` calls — behind `show_meters`.
- The shared `update_peak_hold` call (producing `self.peak_hold_spectrum`, consumed by
  both the Spectrum panel's peak dots and the Radial panel) runs when
  `self.show_spectrum or self.show_radial` — computed once, whichever consumer(s) are
  visible read the result. `self.peak_hold_dots.setData(...)` (the Spectrum panel's own
  peak markers) stays behind `show_spectrum` specifically.

Toggling a hidden panel back on resumes from whatever buffer/peak-hold state currently
holds (e.g. spectrogram's rolling image buffer, peak-hold decay arrays) — no reset on
show, consistent with "skip while hidden" rather than "pause and rewind."

## Code structure

`main.py` currently ~345 lines (after Phase 2b). Phase 2d additions:

| Addition | Approx. lines |
|---|---|
| `_build_toolbar()` (toolbar, 5 actions, slider, label, shortcuts) | ~45 |
| Visibility flags + toggle handlers | ~15 |
| `on_rate_changed` + rate-shortcut handlers | ~15 |
| `on_tick` gating (flag checks around existing calls) | ~15 (mostly indentation/conditionals on existing lines) |
| Total in `main.py` | ~80-90 |

`audio_math.py` additions: `rate_hz_to_chunk_frames` (~3 lines) plus pytest unit tests
(~15 lines) in `test_audio_math.py`.

Estimated final `main.py` size: ~430 lines — still a single-file frontend; no split
proposed for this phase (matches Phase 2b's precedent of deferring structural cleanup
until it's actually forced).

No new dependencies — `QToolBar`, `QAction`, `QSlider`, `QWidgetAction`, `QKeySequence`
are all standard `PyQt5.QtWidgets`/`QtGui`.

## Testing

- `rate_hz_to_chunk_frames`: unit-tested in `test_audio_math.py` (typical rate, very low
  rate, and the `max(1, ...)` floor at very high rates), same pattern as existing helpers.
- Toolbar/visibility/shortcut wiring is UI glue in `main.py`, which has no existing test
  coverage (no other `WaveformWindow` behavior is unit-tested either) — verified manually
  by running the app and exercising each toggle button, each number-key shortcut, the
  slider, and the up/down arrow keys against a fixture WAV file.

## Out of scope for 2d

- Restart/loop playback controls, mic-input source selection (separate todo items).
- Runtime-adjustable analysis window size / FFT window type (engine limitation).
- Per-meter toggles (meters row is one unit).
- Persisting control state across restarts.
- Color gradients / amplitude-threshold effects (Phase 2c, explicitly skipped for now per
  user direction).
