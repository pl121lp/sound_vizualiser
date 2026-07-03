# Phase 2b Design — Radial/Circular Spectrum

## Scope

Phase 2b is entirely frontend — no changes to the C++ engine or pybind11 bindings.

One addition to `frontend/main.py`: a `RadialSpectrumPanel` widget that maps the FFT
spectrum around a circle, added below the existing `SpectrogramPanel`. It reuses the
per-bin peak-hold state already computed in Phase 2a (`WaveformWindow.peak_hold_spectrum`)
rather than tracking its own.

One addition to `frontend/audio_math.py`: a pure `polar_bar_endpoints` function holding
the magnitude→radius→xy conversion math, unit-tested independently of Qt/pyqtgraph.

## Rendering approach

pyqtgraph has no native polar-plot type. The radial view is built by embedding polar
coordinates into a regular Cartesian `pg.PlotWidget`:

- `setAspectLocked(True)` so circles render as circles regardless of widget resize.
- Axes hidden, mouse interaction disabled (consistent with `SpectrogramPanel`).
- Each frequency bin becomes a line segment ("spoke") from a fixed inner radius out to a
  magnitude-scaled outer radius, at a fixed angle around the circle.
- All spokes are drawn with a single `pg.PlotCurveItem(connect='pairs')` — one draw call
  for all `n_bins` segments, avoiding per-bin plot items.

A custom `QPainter`-based approach (filled wedges, rounded bar caps, gradient fill) would
give richer visuals but adds real complexity and is better suited to Phase 2c
(color gradients / amplitude-threshold effects), which already owns visual styling work.

## Frequency mapping

Same log-frequency approach as the spectrogram, for visual consistency and better use of
angular space (linear bin index would compress most of the circle into the low end of the
spectrum):

- Reuses `make_log_freq_grid(spectrum_len, sample_rate, n_bins)` from `audio_math.py`.
- `n_bins = 256` — matches the spectrogram's `n_freq_rows`, so both views use the same
  perceptual resolution.

## Angle layout

Precomputed once at startup in `RadialSpectrumPanel.__init__`:

- `n_bins` angles evenly spaced around the full circle (`2*pi / n_bins` apart).
- Bin 0 (lowest frequency) at the top (angle = `-pi/2` in standard math convention, i.e.
  12 o'clock), increasing clockwise through to the highest frequency just short of 12
  o'clock again.
- `cos_angles`, `sin_angles` arrays of shape `(n_bins,)` precomputed once and reused every
  tick — no trig in the per-frame update path.

## Magnitude → radius mapping

- `inner_radius = 0.3` — small fixed hole at the center, keeps low-magnitude bins from
  cluttering the origin and gives the view a clear "ring" shape.
- `bar_scale = 1.0` — maximum additional radius for a fully-saturated (0 dB) bin.
- Both the live spectrum and the peak-hold array are normalized with the existing
  `to_db_normalized` (same `[-80, 0]` dB clamp as the spectrogram) before being mapped to
  radius, so all three views (bars, spectrogram, radial) treat magnitude consistently.

## `polar_bar_endpoints` (new, in `audio_math.py`)

```python
def polar_bar_endpoints(
    normalized_magnitudes: np.ndarray,
    cos_angles: np.ndarray,
    sin_angles: np.ndarray,
    inner_radius: float = 0.3,
    bar_scale: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Returns (x, y) endpoint arrays of shape (2*n,), pairs of (inner, outer) points
    per bin, ready for pg.PlotCurveItem(connect='pairs')."""
    outer_radius = inner_radius + normalized_magnitudes * bar_scale
    x = np.empty(2 * len(normalized_magnitudes), dtype=np.float32)
    y = np.empty(2 * len(normalized_magnitudes), dtype=np.float32)
    x[0::2] = inner_radius * cos_angles
    y[0::2] = inner_radius * sin_angles
    x[1::2] = outer_radius * cos_angles
    y[1::2] = outer_radius * sin_angles
    return x, y
```

Unit tests (pytest, mirroring `test_audio_math.py` style):
- All-zero magnitudes → every outer point sits exactly at `inner_radius` (spoke length 0).
- All-one magnitudes → every outer point sits at `inner_radius + bar_scale`.
- Known single-bin case (e.g. bin 0 at angle `-pi/2`) → exact expected `(x, y)` pair,
  checked with `np.isclose`.

A second small helper, `make_radial_angles(n_bins)`, returns `(cos_angles, sin_angles)`
given a bin count, encoding the "bin 0 at top, clockwise" convention described above in
one place:

```python
def make_radial_angles(n_bins: int) -> tuple[np.ndarray, np.ndarray]:
    angles = -np.pi / 2 + 2 * np.pi * np.arange(n_bins) / n_bins
    return np.cos(angles), np.sin(angles)
```

`RadialSpectrumPanel.__init__` and the pytest unit tests both call this, so the angle
convention is defined exactly once.

## Peak-hold markers

No new peak-hold state. `WaveformWindow` already maintains `self.peak_hold_spectrum`
(linear-domain, length `spectrum_len`) for the linear bar plot's red dots. `RadialSpectrumPanel.update()`
takes this array as a second argument, interpolates it onto the same log grid as the live
spectrum (`np.interp(self._log_freqs, self._linear_freqs, peak_hold_spectrum)`),
normalizes it with `to_db_normalized`, and maps it to a ring of dots by calling
`polar_bar_endpoints` again with the normalized peak-hold values and taking only the
outer point of each pair (odd indices, `x[1::2]`/`y[1::2]`) — the dots sit exactly at each
bin's outer radius, not as a spoke. Reusing `polar_bar_endpoints` keeps all polar-mapping
math in one tested function rather than duplicating the radius→xy conversion.

Rendered as a `pg.ScatterPlotItem` (small red dots, size 3, no outline pen) — same visual
style as the existing peak-hold dots on the linear spectrum plot.

## Class interface

```python
class RadialSpectrumPanel(QtWidgets.QWidget):
    def __init__(self, spectrum_len: int, sample_rate: float, n_bins: int = 256):
        # precomputes log/linear freq grids, cos/sin angle arrays
        # creates PlotWidget (aspect-locked, axes hidden), PlotCurveItem, ScatterPlotItem
        ...

    def update(self, spectrum: np.ndarray, peak_hold_spectrum: np.ndarray) -> None:
        # interpolates spectrum + peak_hold onto log grid, normalizes, maps to xy,
        # updates spoke curve and peak-dot scatter
        ...
```

`WaveformWindow` instantiates one `RadialSpectrumPanel` alongside `self.spectrogram` and
calls `self.radial.update(frame["spectrum"], self.peak_hold_spectrum)` from `on_tick`,
after `self.peak_hold_spectrum` has been updated for the tick.

## Layout

`RadialSpectrumPanel` is added as a fourth widget to the existing `QVBoxLayout` in
`WaveformWindow`, below `self.spectrogram`, with `stretch=2` (same as the spectrogram).

`RadialSpectrumPanel` follows the same `__init__(spectrum_len, sample_rate, ...)` /
`update(...)` shape as `SpectrogramPanel`, and is added/removed from the layout as a
single self-contained widget with no back-references into `WaveformWindow` beyond the
data passed into `update()`. This keeps it swappable: Phase 2d's visualization-mode
selector can show/hide or reorder these panels later without restructuring
`WaveformWindow` or the panel classes themselves. No mode-switcher scaffolding is added in
2b — that's 2d's job.

## Code structure

`main.py` currently ~285 lines (after Phase 2a). Phase 2b additions:

| Addition | Approx. lines |
|---|---|
| `RadialSpectrumPanel` class | ~55 |
| Instantiation + `on_tick` call in `WaveformWindow` | ~5 |
| Total in `main.py` | ~60 |

`audio_math.py` additions: `polar_bar_endpoints` (+ angle-array helper) — ~20 lines, plus
pytest unit tests (~30 lines) in `test_audio_math.py`.

Estimated final `main.py` size: ~345 lines — still a single-file frontend.

No new dependencies. `np.interp`, `np.cos`/`np.sin`, and `pg.PlotCurveItem`/`pg.ScatterPlotItem`
are all already in use or standard numpy/pyqtgraph.

## Out of scope for 2b

- Mode selector / show-hide UI controls (Phase 2d) — 2b only adds the panel to the
  always-visible stack.
- Color gradients on the radial bars (amplitude- or centroid-driven) — Phase 2c.
- Configurable inner radius, bar scale, or bin count — deferred, hardcoded constants for
  now (matches how spectrogram's `n_freq_rows = 256` and history length are hardcoded in
  2a).
- Frequency labels around the circle — nice-to-have, deferred (spectrogram also deferred
  its axis tick labels in 2a).
