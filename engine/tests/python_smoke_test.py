import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "build"))

import sound_viz_py

engine = sound_viz_py.Engine(window_size=4, sample_rate=44100)

engine.push_samples(np.array([1.0, 2.0], dtype=np.float32), 1)
frame = engine.get_latest_features()
assert frame["waveform"].tolist() == [0.0, 0.0, 1.0, 2.0], frame["waveform"]
assert frame["sample_rate"] == 44100
assert frame["channels"] == 1
assert frame["frame_index"] == 0

engine.push_samples(np.array([3.0, 4.0, 5.0, 6.0], dtype=np.float32), 1)
frame2 = engine.get_latest_features()
assert frame2["waveform"].tolist() == [3.0, 4.0, 5.0, 6.0], frame2["waveform"]
assert frame2["frame_index"] == 1

print("python_smoke_test: OK")
