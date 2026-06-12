import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys

import numpy as np
from PyQt5 import QtWidgets

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from main import WaveformWindow, WINDOW_SIZE, SPECTRUM_LEN, CHUNK_FRAMES

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "..", "fixtures", "test_tone.wav")

app = QtWidgets.QApplication(sys.argv)
window = WaveformWindow(FIXTURE_PATH)

window.on_tick()
window.on_tick()

curve_x, curve_y = window.curve.getData()
assert len(curve_y) == WINDOW_SIZE
assert np.any(curve_y != 0)
assert window.read_pos == 2 * CHUNK_FRAMES

heights = window.spectrum_bars.opts["height"]
assert len(heights) == SPECTRUM_LEN
assert np.any(heights != 0)

print("smoke_test_harness: OK")
