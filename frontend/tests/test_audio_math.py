import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from audio_math import (
    make_log_freq_grid,
    make_radial_angles,
    polar_bar_endpoints,
    rate_hz_to_chunk_frames,
    to_db_normalized,
    update_peak_hold,
)


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


def test_make_radial_angles_shape():
    cos_angles, sin_angles = make_radial_angles(4)
    assert cos_angles.shape == (4,)
    assert sin_angles.shape == (4,)


def test_make_radial_angles_bin0_at_top():
    cos_angles, sin_angles = make_radial_angles(4)
    assert cos_angles[0] == pytest.approx(0.0, abs=1e-6)
    assert sin_angles[0] == pytest.approx(1.0, abs=1e-6)


def test_make_radial_angles_sweeps_clockwise():
    # With bin 0 at 12 o'clock, bin 1 (of 4) should land at 3 o'clock if the
    # sweep is clockwise.
    cos_angles, sin_angles = make_radial_angles(4)
    assert cos_angles[1] == pytest.approx(1.0, abs=1e-6)
    assert sin_angles[1] == pytest.approx(0.0, abs=1e-6)


def test_make_radial_angles_unit_circle():
    cos_angles, sin_angles = make_radial_angles(37)
    np.testing.assert_allclose(cos_angles**2 + sin_angles**2, 1.0, atol=1e-10)


def test_polar_bar_endpoints_shape():
    mags = np.array([0.1, 0.5, 0.9], dtype=np.float32)
    cos_angles = np.array([1.0, 0.0, -1.0], dtype=np.float32)
    sin_angles = np.array([0.0, 1.0, 0.0], dtype=np.float32)
    x, y = polar_bar_endpoints(mags, cos_angles, sin_angles)
    assert x.shape == (6,)
    assert y.shape == (6,)


def test_polar_bar_endpoints_zero_magnitude_matches_inner_radius():
    mags = np.array([0.0, 0.0], dtype=np.float32)
    cos_angles = np.array([1.0, 0.0], dtype=np.float32)
    sin_angles = np.array([0.0, 1.0], dtype=np.float32)
    x, y = polar_bar_endpoints(mags, cos_angles, sin_angles, inner_radius=0.3, bar_scale=1.0)
    # Zero magnitude -> outer point coincides with inner point (spoke length 0).
    np.testing.assert_allclose(x[0::2], x[1::2], atol=1e-6)
    np.testing.assert_allclose(y[0::2], y[1::2], atol=1e-6)


def test_polar_bar_endpoints_full_magnitude_reaches_inner_plus_scale():
    mags = np.array([1.0, 1.0], dtype=np.float32)
    cos_angles = np.array([1.0, 0.0], dtype=np.float32)
    sin_angles = np.array([0.0, 1.0], dtype=np.float32)
    x, y = polar_bar_endpoints(mags, cos_angles, sin_angles, inner_radius=0.3, bar_scale=1.0)
    outer_radius = np.hypot(x[1::2], y[1::2])
    np.testing.assert_allclose(outer_radius, 1.3, atol=1e-6)


def test_polar_bar_endpoints_single_bin_exact_position():
    mags = np.array([0.5], dtype=np.float32)
    cos_angles = np.array([0.0], dtype=np.float32)  # bin at 12 o'clock (angle pi/2)
    sin_angles = np.array([1.0], dtype=np.float32)
    x, y = polar_bar_endpoints(mags, cos_angles, sin_angles, inner_radius=0.3, bar_scale=1.0)
    # inner point at (0, 0.3), outer point at (0, 0.3 + 0.5) = (0, 0.8)
    np.testing.assert_allclose(x, [0.0, 0.0], atol=1e-6)
    np.testing.assert_allclose(y, [0.3, 0.8], atol=1e-6)


def test_rate_hz_to_chunk_frames_typical():
    assert rate_hz_to_chunk_frames(44100.0, 30.0) == 1470


def test_rate_hz_to_chunk_frames_low_rate_large_chunk():
    assert rate_hz_to_chunk_frames(44100.0, 5.0) == 8820


def test_rate_hz_to_chunk_frames_floors_at_one_frame():
    assert rate_hz_to_chunk_frames(44100.0, 100000.0) == 1
