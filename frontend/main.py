import argparse
import os
import sys

import numpy as np
import soundfile as sf
from PyQt5 import QtCore, QtWidgets
import pyqtgraph as pg

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "engine", "build"))
import sound_viz_py

WINDOW_SIZE = 1024
CHUNK_FRAMES = 1024


class WaveformWindow(QtWidgets.QMainWindow):
    def __init__(self, wav_path):
        super().__init__()

        data, sample_rate = sf.read(wav_path, dtype="float32", always_2d=True)
        self.data = data
        self.sample_rate = sample_rate
        self.n_channels = data.shape[1]
        self.read_pos = 0

        self.engine = sound_viz_py.Engine(window_size=WINDOW_SIZE, sample_rate=sample_rate)

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setYRange(-1.0, 1.0)
        self.curve = self.plot_widget.plot(np.zeros(WINDOW_SIZE))
        self.setCentralWidget(self.plot_widget)

        interval_ms = int(1000 * CHUNK_FRAMES / sample_rate)
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.on_tick)
        self.timer.start(interval_ms)

    def on_tick(self):
        if self.read_pos >= len(self.data):
            self.timer.stop()
            return

        chunk = self.data[self.read_pos:self.read_pos + CHUNK_FRAMES]
        self.read_pos += CHUNK_FRAMES

        flat = chunk.reshape(-1).astype(np.float32)
        self.engine.push_samples(flat, self.n_channels)

        frame = self.engine.get_latest_features()
        self.curve.setData(frame["waveform"])


def main():
    parser = argparse.ArgumentParser(description="Sound visualizer - phase 1a waveform viewer")
    parser.add_argument("wav_path", help="Path to a WAV file")
    args = parser.parse_args()

    app = QtWidgets.QApplication(sys.argv)
    window = WaveformWindow(args.wav_path)
    window.setWindowTitle("Sound Visualizer - Waveform (Phase 1a)")
    window.resize(800, 400)
    window.show()
    app.exec_()


if __name__ == "__main__":
    main()
