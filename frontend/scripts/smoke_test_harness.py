import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
from argparse import Namespace

import numpy as np
from PyQt5 import QtWidgets

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from main import WaveformWindow

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "..", "fixtures", "test_tone.wav")

args = Namespace(
    window_size=1024,
    update_rate=30.0,
    fft_window="hann",
    band_split_low=250.0,
    band_split_high=4000.0,
)

app = QtWidgets.QApplication(sys.argv)
window = WaveformWindow(FIXTURE_PATH, args)

window.on_tick()
window.on_tick()

curve_x, curve_y = window.curve.getData()
assert len(curve_y) == window.window_size
assert np.any(curve_y != 0)
assert window.read_pos == 2 * window.chunk_frames

heights = window.spectrum_bars.opts["height"]
assert len(heights) == window.spectrum_len
assert np.any(heights != 0)

print("smoke_test_harness: OK")
