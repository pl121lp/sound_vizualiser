import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from audio_math import make_log_freq_grid, to_db_normalized


def test_make_log_freq_grid_shape():
    log_freqs, linear_freqs = make_log_freq_grid(513, 44100.0)
    assert log_freqs.shape == (256,)
    assert linear_freqs.shape == (513,)


def test_make_log_freq_grid_range():
    log_freqs, linear_freqs = make_log_freq_grid(513, 44100.0)
    assert log_freqs[0] == pytest.approx(20.0)
    assert log_freqs[-1] == pytest.approx(22050.0)
    assert linear_freqs[0] == pytest.approx(0.0)
    assert linear_freqs[-1] == pytest.approx(22050.0)


def test_make_log_freq_grid_monotonic():
    log_freqs, linear_freqs = make_log_freq_grid(513, 44100.0)
    assert np.all(np.diff(log_freqs) > 0)
    assert np.all(np.diff(linear_freqs) >= 0)


def test_make_log_freq_grid_custom_n_rows():
    log_freqs, _ = make_log_freq_grid(513, 44100.0, n_rows=128)
    assert log_freqs.shape == (128,)


def test_to_db_normalized_full_scale():
    result = to_db_normalized(np.array([1.0]))
    assert result[0] == pytest.approx(1.0, abs=1e-3)


def test_to_db_normalized_silence():
    result = to_db_normalized(np.array([0.0]))
    assert result[0] == pytest.approx(0.0, abs=1e-3)


def test_to_db_normalized_midpoint():
    # 0.01 amplitude → -40 dB → 0.5 normalized (db_min=-80, db_max=0)
    result = to_db_normalized(np.array([0.01]))
    assert result[0] == pytest.approx(0.5, abs=0.01)


def test_to_db_normalized_output_range():
    spectrum = np.array([0.0, 0.001, 0.01, 0.1, 1.0])
    result = to_db_normalized(spectrum)
    assert np.all(result >= 0.0)
    assert np.all(result <= 1.0)
