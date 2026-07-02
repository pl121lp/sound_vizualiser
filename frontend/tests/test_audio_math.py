import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from audio_math import make_log_freq_grid, to_db_normalized, update_peak_hold


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


def test_update_peak_hold_new_peak():
    spectrum = np.array([0.8, 0.5], dtype=np.float32)
    peak_values = np.array([0.5, 0.6], dtype=np.float32)
    peak_timers = np.array([0.5, 0.5], dtype=np.float32)
    new_vals, new_timers = update_peak_hold(spectrum, peak_values, peak_timers, dt=0.1)
    assert new_vals[0] == pytest.approx(0.8)    # updated to new peak
    assert new_timers[0] == pytest.approx(0.0)  # timer reset
    assert new_vals[1] == pytest.approx(0.6)    # unchanged (0.5 < 0.6)
    assert new_timers[1] == pytest.approx(0.6)  # timer incremented


def test_update_peak_hold_within_hold_period():
    spectrum = np.array([0.3], dtype=np.float32)
    peak_values = np.array([0.8], dtype=np.float32)
    peak_timers = np.array([0.5], dtype=np.float32)
    new_vals, new_timers = update_peak_hold(
        spectrum, peak_values, peak_timers, dt=0.1, hold_secs=1.0
    )
    assert new_vals[0] == pytest.approx(0.8)    # no decay yet
    assert new_timers[0] == pytest.approx(0.6)  # timer incremented


def test_update_peak_hold_decay_after_hold():
    spectrum = np.array([0.3], dtype=np.float32)
    peak_values = np.array([0.8], dtype=np.float32)
    peak_timers = np.array([1.0], dtype=np.float32)
    new_vals, new_timers = update_peak_hold(
        spectrum, peak_values, peak_timers, dt=0.1, hold_secs=1.0, decay_per_sec=1.0
    )
    assert new_vals[0] == pytest.approx(0.7, abs=1e-5)    # decayed by 0.1
    assert new_timers[0] == pytest.approx(1.1, abs=1e-5)  # timer kept incrementing


def test_update_peak_hold_decay_clamps_to_spectrum():
    spectrum = np.array([0.3], dtype=np.float32)
    peak_values = np.array([0.35], dtype=np.float32)
    peak_timers = np.array([2.0], dtype=np.float32)
    new_vals, _ = update_peak_hold(
        spectrum, peak_values, peak_timers, dt=0.1, hold_secs=1.0, decay_per_sec=1.0
    )
    assert new_vals[0] == pytest.approx(0.3)  # clamped: 0.35 - 0.1 = 0.25 < 0.3


def test_update_peak_hold_does_not_mutate_inputs():
    spectrum = np.array([0.8], dtype=np.float32)
    peak_values = np.array([0.5], dtype=np.float32)
    peak_timers = np.array([0.0], dtype=np.float32)
    orig_peak = peak_values.copy()
    orig_timer = peak_timers.copy()
    update_peak_hold(spectrum, peak_values, peak_timers, dt=0.1)
    np.testing.assert_array_equal(peak_values, orig_peak)
    np.testing.assert_array_equal(peak_timers, orig_timer)
