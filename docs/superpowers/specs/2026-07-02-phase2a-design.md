# Phase 2a Design — Spectrogram + Per-bin Peak-hold

## Scope

Phase 2a is entirely frontend — no changes to the C++ engine or pybind11 bindings.

Two additions to `frontend/main.py`:

1. **Spectrogram panel**: scrolling time-frequency view added below the existing spectrum bar plot.
2. **Per-bin peak-hold overlay**: decaying max-value marker per frequency bin, overlaid on the existing spectrum bar plot.

## Spectrogram panel

### Layout

A new `SpectrogramPanel` widget is added to the existing `QVBoxLayout` in `WaveformWindow`, below the spectrum bar plot. It has a minimum height of 150 px and a stretch factor of 2 (vs 1 for the waveform and spectrum plots), so it scales naturally with window resize.

### Rolling buffer

- Shape: `(history_cols, n_freq_rows)` — numpy `float32` array, zero-initialized.
- `history_cols = ceil(update_rate * 5.0)` — 5 seconds of history at the configured update rate.
- `n_freq_rows = 256` — fixed; chosen to give good vertical resolution without excess cost.
- Each tick: `np.roll` left by one column, write new column into `[:, -1]`.

### Log-frequency mapping

Precomputed once at startup in `SpectrogramPanel.__init__`:

- `log_freqs`: 256 values log-spaced from 20 Hz to Nyquist (`sample_rate / 2`) — the target frequency grid.
- `linear_freqs`: the `spectrum_len` linear bin centre frequencies (`np.linspace(0, sample_rate / 2, spectrum_len)`).

Each tick, `np.interp(self.log_freqs, self.linear_freqs, spectrum)` maps the new spectrum column onto the 256 log-spaced rows in one call.

### Magnitude scaling

`20 * log10(magnitude + 1e-9)`, clamped to [−80, 0] dB, then normalised to [0, 1] for the colormap:

```
db = np.clip(20 * np.log10(spectrum_log + 1e-9), -80.0, 0.0)
normalised = (db + 80.0) / 80.0
```

### Rendering

- `pg.ImageItem` with pyqtgraph's built-in `inferno` colormap (dark = quiet, bright = loud).
- Image transposed so Y axis = frequency, X axis = time (time scrolls left, newest column on right).
- Axis labels: "Frequency (Hz)" on Y, "Time →" on X. Y-axis tick labels show Hz values at representative log positions.

### Class interface

```python
class SpectrogramPanel(QtWidgets.QWidget):
    def __init__(self, spectrum_len, sample_rate, update_rate):
        # precomputes log mapping, allocates rolling buffer, creates ImageItem
        ...

    def update(self, spectrum: np.ndarray) -> None:
        # rolls buffer, inserts new column, refreshes ImageItem
        ...
```

`WaveformWindow` instantiates one `SpectrogramPanel` and calls `self.spectrogram.update(frame["spectrum"])` from `on_tick`.

## Per-bin peak-hold overlay

### State (owned by `WaveformWindow`)

- `peak_hold_spectrum`: `np.zeros(spectrum_len, dtype=np.float32)` — current per-bin peak value.
- `peak_hold_timer_spectrum`: `np.zeros(spectrum_len, dtype=np.float32)` — seconds since each bin last set a new peak.

### Update logic (per tick, vectorised)

```python
dt = self.tick_interval_s
new_peak_mask = spectrum >= self.peak_hold_spectrum
self.peak_hold_spectrum[new_peak_mask] = spectrum[new_peak_mask]
self.peak_hold_timer_spectrum[new_peak_mask] = 0.0

self.peak_hold_timer_spectrum[~new_peak_mask] += dt
decaying = (~new_peak_mask) & (self.peak_hold_timer_spectrum > PEAK_HOLD_SECONDS)
self.peak_hold_spectrum[decaying] = np.maximum(
    spectrum[decaying],
    self.peak_hold_spectrum[decaying] - PEAK_DECAY_PER_SECOND * dt,
)
```

Reuses the existing constants `PEAK_HOLD_SECONDS = 1.0` and `PEAK_DECAY_PER_SECOND = 1.0`.

### Rendering

A `pg.ScatterPlotItem` (small red dots, size 3, no outline pen) added to the existing `spectrum_plot`. Updated each tick:

```python
self.peak_hold_dots.setData(
    x=np.arange(self.spectrum_len),
    y=self.peak_hold_spectrum,
)
```

## Code structure

`main.py` currently ~215 lines. Phase 2a additions:

| Addition | Approx. lines |
|---|---|
| `SpectrogramPanel` class | ~50 |
| Per-bin peak-hold state + update in `WaveformWindow` | ~20 |
| Total | ~70 |

Estimated final size: ~285 lines — still a single-file frontend.

No new dependencies. pyqtgraph's `inferno` colormap is built-in; `np.interp` and `np.roll` are standard numpy.

## Out of scope for 2a

- Frequency axis tick labels (nice-to-have, deferred — axis label "Frequency (Hz)" is sufficient).
- Configurable history length or colormap (deferred to 2d UI controls).
- Radial/circular spectrum (Phase 2b).
- Color gradients / amplitude-threshold effects (Phase 2c).
