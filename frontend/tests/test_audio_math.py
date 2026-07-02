import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from audio_math import make_log_freq_grid


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
