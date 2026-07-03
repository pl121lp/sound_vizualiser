import numpy as np


def make_log_freq_grid(
    spectrum_len: int, sample_rate: float, n_rows: int = 256
) -> tuple[np.ndarray, np.ndarray]:
    linear_freqs = np.linspace(0.0, sample_rate / 2.0, spectrum_len)
    log_freqs = np.geomspace(20.0, sample_rate / 2.0, n_rows)
    return log_freqs, linear_freqs


def to_db_normalized(
    spectrum: np.ndarray, db_min: float = -80.0, db_max: float = 0.0
) -> np.ndarray:
    db = 20.0 * np.log10(np.asarray(spectrum, dtype=np.float64) + 1e-9)
    db = np.clip(db, db_min, db_max)
    return ((db - db_min) / (db_max - db_min)).astype(np.float32)


def update_peak_hold(
    spectrum: np.ndarray,
    peak_values: np.ndarray,
    peak_timers: np.ndarray,
    dt: float,
    hold_secs: float = 1.0,
    decay_per_sec: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    spectrum = np.asarray(spectrum)
    peak_values = peak_values.copy()
    peak_timers = peak_timers.copy()

    new_peak = spectrum >= peak_values
    peak_values[new_peak] = spectrum[new_peak]
    peak_timers[new_peak] = 0.0

    peak_timers[~new_peak] += dt
    decaying = (~new_peak) & (peak_timers > hold_secs)
    peak_values[decaying] = np.maximum(
        spectrum[decaying],
        peak_values[decaying] - decay_per_sec * dt,
    )

    return peak_values, peak_timers


def make_radial_angles(n_bins: int) -> tuple[np.ndarray, np.ndarray]:
    angles = np.pi / 2 - 2 * np.pi * np.arange(n_bins) / n_bins
    return np.cos(angles), np.sin(angles)


def polar_bar_endpoints(
    normalized_magnitudes: np.ndarray,
    cos_angles: np.ndarray,
    sin_angles: np.ndarray,
    inner_radius: float = 0.3,
    bar_scale: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    normalized_magnitudes = np.asarray(normalized_magnitudes)
    outer_radius = inner_radius + normalized_magnitudes * bar_scale
    n = len(normalized_magnitudes)
    x = np.empty(2 * n, dtype=np.float32)
    y = np.empty(2 * n, dtype=np.float32)
    x[0::2] = inner_radius * cos_angles
    y[0::2] = inner_radius * sin_angles
    x[1::2] = outer_radius * cos_angles
    y[1::2] = outer_radius * sin_angles
    return x, y


def rate_hz_to_chunk_frames(sample_rate: float, rate_hz: float) -> int:
    return max(1, round(sample_rate / rate_hz))


def advance_or_pause(read_pos: int, data_len: int, loop_enabled: bool) -> tuple[int, bool]:
    if read_pos < data_len:
        return read_pos, False
    if loop_enabled:
        return 0, False
    return read_pos, True
