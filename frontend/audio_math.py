import numpy as np


def make_log_freq_grid(
    spectrum_len: int, sample_rate: float, n_rows: int = 256
) -> tuple[np.ndarray, np.ndarray]:
    linear_freqs = np.linspace(0.0, sample_rate / 2.0, spectrum_len)
    log_freqs = np.geomspace(20.0, sample_rate / 2.0, n_rows)
    return log_freqs, linear_freqs
