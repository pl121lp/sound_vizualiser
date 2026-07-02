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
