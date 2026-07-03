import argparse
import os
import sys

import numpy as np
import soundfile as sf
from PyQt5 import QtCore, QtGui, QtWidgets
import pyqtgraph as pg

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "engine", "build"))
import sound_viz_py
from audio_math import (
    make_log_freq_grid,
    make_radial_angles,
    polar_bar_endpoints,
    rate_hz_to_chunk_frames,
    to_db_normalized,
    update_peak_hold,
)

PEAK_HOLD_SECONDS = 1.0
PEAK_DECAY_PER_SECOND = 1.0


class SpectrogramPanel(QtWidgets.QWidget):
    def __init__(self, spectrum_len: int, sample_rate: float, update_rate: float):
        super().__init__()

        n_freq_rows = 256
        history_cols = max(1, int(np.ceil(update_rate * 5.0)))

        self._log_freqs, self._linear_freqs = make_log_freq_grid(
            spectrum_len, sample_rate, n_freq_rows
        )
        self._buffer = np.zeros((history_cols, n_freq_rows), dtype=np.float32)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._plot = pg.PlotWidget()
        self._plot.setLabel("left", "Frequency (Hz)")
        self._plot.setLabel("bottom", "Time →")
        self._plot.setMouseEnabled(x=False, y=False)
        self._plot.hideAxis("bottom")

        cm = pg.colormap.get("inferno")
        self._image = pg.ImageItem()
        self._image.setColorMap(cm)
        self._image.setLevels([0.0, 1.0])
        self._plot.addItem(self._image)

        layout.addWidget(self._plot)
        self.setMinimumHeight(150)

    def update(self, spectrum: np.ndarray) -> None:
        col = to_db_normalized(
            np.interp(self._log_freqs, self._linear_freqs, spectrum).astype(np.float32)
        )
        self._buffer = np.roll(self._buffer, -1, axis=0)
        self._buffer[-1] = col
        self._image.setImage(self._buffer)


class RadialSpectrumPanel(QtWidgets.QWidget):
    def __init__(self, spectrum_len: int, sample_rate: float, n_bins: int = 256):
        super().__init__()

        self._log_freqs, self._linear_freqs = make_log_freq_grid(
            spectrum_len, sample_rate, n_bins
        )
        self._cos_angles, self._sin_angles = make_radial_angles(n_bins)
        self._inner_radius = 0.3
        self._bar_scale = 1.0

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._plot = pg.PlotWidget()
        self._plot.setAspectLocked(True)
        self._plot.hideAxis("left")
        self._plot.hideAxis("bottom")
        self._plot.setMouseEnabled(x=False, y=False)

        self._spokes = pg.PlotCurveItem(pen=pg.mkPen("c", width=1), connect="pairs")
        self._plot.addItem(self._spokes)

        self._peak_dots = pg.ScatterPlotItem(pen=None, brush=pg.mkBrush("r"), size=3)
        self._plot.addItem(self._peak_dots)

        layout.addWidget(self._plot)
        self.setMinimumHeight(150)

    def update(self, spectrum: np.ndarray, peak_hold_spectrum: np.ndarray) -> None:
        magnitude = to_db_normalized(
            np.interp(self._log_freqs, self._linear_freqs, spectrum).astype(np.float32)
        )
        peak = to_db_normalized(
            np.interp(
                self._log_freqs, self._linear_freqs, peak_hold_spectrum
            ).astype(np.float32)
        )

        x, y = polar_bar_endpoints(
            magnitude, self._cos_angles, self._sin_angles, self._inner_radius, self._bar_scale
        )
        self._spokes.setData(x, y)

        peak_x, peak_y = polar_bar_endpoints(
            peak, self._cos_angles, self._sin_angles, self._inner_radius, self._bar_scale
        )
        self._peak_dots.setData(x=peak_x[1::2], y=peak_y[1::2])


class BarMeter(QtWidgets.QWidget):
    """A horizontal bar gauge with a title label and a live numeric readout."""

    def __init__(self, title, value_format, x_range=(0.0, 1.0), auto_scale=False):
        super().__init__()
        self.value_format = value_format
        self.auto_scale = auto_scale
        self.running_max = 1e-6

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        label_layout = QtWidgets.QHBoxLayout()
        label_layout.setContentsMargins(0, 0, 0, 0)

        self.title_label = QtWidgets.QLabel(f"{title}:")
        label_layout.addWidget(self.title_label)

        self.value_label = QtWidgets.QLabel()
        self.value_label.setFont(QtGui.QFont("monospace"))
        self.value_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        # Reserve enough horizontal space for the widest expected reading so the
        # meter doesn't resize (and shift the bar/label) as values change.
        self.value_label.setFixedWidth(self.value_label.fontMetrics().horizontalAdvance("0" * 10))
        label_layout.addWidget(self.value_label)
        label_layout.addStretch()

        layout.addLayout(label_layout)

        self.plot = pg.PlotWidget()
        self.plot.setMaximumHeight(40)
        self.plot.hideAxis("left")
        self.plot.hideAxis("bottom")
        self.plot.setMouseEnabled(x=False, y=False)
        self.plot.setYRange(-0.5, 0.5, padding=0)
        self.plot.setXRange(*x_range, padding=0)

        self.bar = pg.BarGraphItem(x0=[0.0], x1=[0.0], y0=[-0.3], y1=[0.3], brush="c")
        self.plot.addItem(self.bar)

        self.title = title
        layout.addWidget(self.plot)

        self.update_value(0.0)

    def update_value(self, value):
        if self.auto_scale:
            self.running_max = max(self.running_max * 0.98, value)
            upper = max(self.running_max * 1.2, 1e-6)
            self.plot.setXRange(0.0, upper, padding=0)

        self.bar.setOpts(x0=[0.0], x1=[value])
        self.value_label.setText(self.value_format.format(value))


class WaveformWindow(QtWidgets.QMainWindow):
    def __init__(self, wav_path, args):
        super().__init__()

        data, sample_rate = sf.read(wav_path, dtype="float32", always_2d=True)
        self.data = data
        self.sample_rate = sample_rate
        self.n_channels = data.shape[1]
        self.read_pos = 0

        self.window_size = args.window_size
        self.spectrum_len = self.window_size // 2 + 1
        self.rate_hz = args.update_rate
        self.chunk_frames = rate_hz_to_chunk_frames(sample_rate, self.rate_hz)

        self.engine = sound_viz_py.Engine(
            window_size=self.window_size,
            sample_rate=sample_rate,
            update_rate_hz=args.update_rate,
            fft_window_type=args.fft_window,
            band_split_low_hz=args.band_split_low,
            band_split_high_hz=args.band_split_high,
        )

        self.waveform_plot = pg.PlotWidget()
        self.waveform_plot.setYRange(-1.0, 1.0)
        self.waveform_plot.setLabel("left", "Waveform")
        self.curve = self.waveform_plot.plot(np.zeros(self.window_size))

        self.spectrum_plot = pg.PlotWidget()
        self.spectrum_plot.setLabel("left", "Spectrum")
        self.spectrum_plot.enableAutoRange("y", False)
        self.spectrum_max = 1e-6
        self.spectrum_plot.setYRange(0.0, self.spectrum_max, padding=0)
        self.spectrum_bars = pg.BarGraphItem(
            x=np.arange(self.spectrum_len), height=np.zeros(self.spectrum_len), width=0.8
        )
        self.spectrum_plot.addItem(self.spectrum_bars)

        self.rms_meter = BarMeter("RMS", "{:.3f}", x_range=(0.0, 1.0))
        self.zcr_meter = BarMeter("Zero-crossing rate", "{:.3f}", x_range=(0.0, 1.0))
        self.peak_meter = BarMeter("Peak", "{:.3f}", x_range=(0.0, 1.0))
        self.band_low_meter = BarMeter("Band energy (low)", "{:.2f}", auto_scale=True)
        self.band_mid_meter = BarMeter("Band energy (mid)", "{:.2f}", auto_scale=True)
        self.band_high_meter = BarMeter("Band energy (high)", "{:.2f}", auto_scale=True)
        self.centroid_meter = BarMeter("Spectral centroid (Hz)", "{:.0f}", auto_scale=True)

        self.peak_hold_line = pg.InfiniteLine(pos=0.0, angle=90, pen=pg.mkPen("r", width=2))
        self.peak_meter.plot.addItem(self.peak_hold_line)
        self.peak_hold_value = 0.0
        self.peak_hold_timer = 0.0
        self.spectrogram = SpectrogramPanel(self.spectrum_len, sample_rate, args.update_rate)
        self.peak_hold_spectrum = np.zeros(self.spectrum_len, dtype=np.float32)
        self.peak_hold_timer_spectrum = np.zeros(self.spectrum_len, dtype=np.float32)
        self.peak_hold_dots = pg.ScatterPlotItem(
            x=np.arange(self.spectrum_len),
            y=self.peak_hold_spectrum,
            pen=None,
            brush=pg.mkBrush("r"),
            size=3,
        )
        self.spectrum_plot.addItem(self.peak_hold_dots)
        self.radial_spectrum = RadialSpectrumPanel(self.spectrum_len, sample_rate)

        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        layout.addWidget(self.waveform_plot, stretch=1)
        layout.addWidget(self.spectrum_plot, stretch=1)
        layout.addWidget(self.spectrogram, stretch=2)
        layout.addWidget(self.radial_spectrum, stretch=2)

        self.meters_container = QtWidgets.QWidget()
        meters_layout = QtWidgets.QHBoxLayout(self.meters_container)
        meters_layout.setContentsMargins(0, 0, 0, 0)
        for meter in (
            self.rms_meter,
            self.zcr_meter,
            self.peak_meter,
            self.band_low_meter,
            self.band_mid_meter,
            self.band_high_meter,
            self.centroid_meter,
        ):
            meters_layout.addWidget(meter)
        layout.addWidget(self.meters_container)

        self.setCentralWidget(container)

        interval_ms = max(1, int(1000 * self.chunk_frames / sample_rate))
        self.tick_interval_s = interval_ms / 1000.0
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.on_tick)
        self.timer.start(interval_ms)

        self.build_toolbar()

    def on_tick(self):
        if self.read_pos >= len(self.data):
            self.timer.stop()
            return

        chunk = self.data[self.read_pos:self.read_pos + self.chunk_frames]
        self.read_pos += self.chunk_frames

        flat = chunk.reshape(-1).astype(np.float32)
        self.engine.push_samples(flat, self.n_channels)

        frame = self.engine.get_latest_features()

        if self.show_waveform:
            self.curve.setData(frame["waveform"])

        if self.show_spectrum:
            self.spectrum_bars.setOpts(height=frame["spectrum"])
            spectrum_peak = float(np.max(frame["spectrum"]))
            if spectrum_peak > self.spectrum_max:
                self.spectrum_max = spectrum_peak * 1.1
                self.spectrum_plot.setYRange(0.0, self.spectrum_max, padding=0)

        if self.show_spectrogram:
            self.spectrogram.update(frame["spectrum"])

        if self.show_spectrum or self.show_radial:
            spectrum = np.asarray(frame["spectrum"], dtype=np.float32)
            self.peak_hold_spectrum, self.peak_hold_timer_spectrum = update_peak_hold(
                spectrum,
                self.peak_hold_spectrum,
                self.peak_hold_timer_spectrum,
                self.tick_interval_s,
                PEAK_HOLD_SECONDS,
                PEAK_DECAY_PER_SECOND,
            )
            if self.show_spectrum:
                self.peak_hold_dots.setData(
                    x=np.arange(self.spectrum_len),
                    y=self.peak_hold_spectrum,
                )
            if self.show_radial:
                self.radial_spectrum.update(spectrum, self.peak_hold_spectrum)

        if self.show_meters:
            self.rms_meter.update_value(float(frame["rms"]))
            self.zcr_meter.update_value(float(frame["zero_crossing_rate"]))
            self.band_low_meter.update_value(float(frame["band_energy_low"]))
            self.band_mid_meter.update_value(float(frame["band_energy_mid"]))
            self.band_high_meter.update_value(float(frame["band_energy_high"]))
            self.centroid_meter.update_value(float(frame["spectral_centroid"]))

            peak = float(frame["peak"])
            self.peak_meter.update_value(peak)
            if peak >= self.peak_hold_value:
                self.peak_hold_value = peak
                self.peak_hold_timer = 0.0
            else:
                self.peak_hold_timer += self.tick_interval_s
                if self.peak_hold_timer > PEAK_HOLD_SECONDS:
                    self.peak_hold_value = max(
                        peak, self.peak_hold_value - PEAK_DECAY_PER_SECOND * self.tick_interval_s
                    )
            self.peak_hold_line.setValue(self.peak_hold_value)

    def build_toolbar(self):
        toolbar = self.addToolBar("Controls")
        toolbar.setMovable(False)

        panel_specs = [
            ("Waveform", "1", self.waveform_plot, "show_waveform"),
            ("Spectrum", "2", self.spectrum_plot, "show_spectrum"),
            ("Spectrogram", "3", self.spectrogram, "show_spectrogram"),
            ("Radial", "4", self.radial_spectrum, "show_radial"),
            ("Meters", "5", self.meters_container, "show_meters"),
        ]
        self.panel_actions = {}
        for label, key, widget, flag_attr in panel_specs:
            action = QtWidgets.QAction(label, self)
            action.setCheckable(True)
            action.setShortcut(QtGui.QKeySequence(key))
            action.toggled.connect(
                lambda checked, w=widget, attr=flag_attr: self.on_panel_toggled(checked, w, attr)
            )
            action.setChecked(True)
            toolbar.addAction(action)
            self.panel_actions[flag_attr] = action

        toolbar.addSeparator()

        toolbar.addWidget(QtWidgets.QLabel("Rate:"))

        self.rate_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.rate_slider.setRange(5, 60)
        self.rate_slider.setSingleStep(5)
        self.rate_slider.setPageStep(5)
        self.rate_slider.setTickInterval(5)
        self.rate_slider.setFixedWidth(120)
        self.rate_value_label = QtWidgets.QLabel()

        initial_rate = min(60, max(5, round(self.rate_hz / 5) * 5))
        self.rate_slider.setValue(initial_rate)
        self.rate_slider.valueChanged.connect(self.on_rate_changed)
        self.on_rate_changed(self.rate_slider.value())

        toolbar.addWidget(self.rate_slider)
        toolbar.addWidget(self.rate_value_label)

        rate_up = QtWidgets.QAction(self)
        rate_up.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Up))
        rate_up.triggered.connect(lambda: self.rate_slider.setValue(self.rate_slider.value() + 5))
        self.addAction(rate_up)

        rate_down = QtWidgets.QAction(self)
        rate_down.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Down))
        rate_down.triggered.connect(lambda: self.rate_slider.setValue(self.rate_slider.value() - 5))
        self.addAction(rate_down)

    def on_panel_toggled(self, checked, widget, flag_attr):
        widget.setVisible(checked)
        setattr(self, flag_attr, checked)

    def on_rate_changed(self, new_rate_hz):
        self.rate_hz = new_rate_hz
        self.chunk_frames = rate_hz_to_chunk_frames(self.sample_rate, new_rate_hz)
        interval_ms = max(1, int(1000 * self.chunk_frames / self.sample_rate))
        self.tick_interval_s = interval_ms / 1000.0
        self.timer.setInterval(interval_ms)
        self.rate_value_label.setText(f"{new_rate_hz} Hz")

    def closeEvent(self, event):
        # Stop the timer before the window starts tearing down. Otherwise a
        # pending on_tick can still update the plots (scheduling a repaint)
        # while Qt's Wayland backing store is mid-teardown for the closing
        # window, which segfaults inside QWaylandWindow::decoration().
        self.timer.stop()
        super().closeEvent(event)


def main():
    parser = argparse.ArgumentParser(description="Sound visualizer - phase 1d configurability")
    parser.add_argument("wav_path", help="Path to a WAV file")
    parser.add_argument("--window-size", type=int, default=1024, help="Analysis window size (samples)")
    parser.add_argument("--update-rate", type=float, default=30.0, help="Target UI update rate (Hz)")
    parser.add_argument("--fft-window", choices=["hann", "hamming"], default="hann", help="FFT window function")
    parser.add_argument("--band-split-low", type=float, default=250.0, help="Low/mid band split frequency (Hz)")
    parser.add_argument("--band-split-high", type=float, default=4000.0, help="Mid/high band split frequency (Hz)")
    args = parser.parse_args()

    app = QtWidgets.QApplication(sys.argv)
    window = WaveformWindow(args.wav_path, args)
    window.setWindowTitle("Sound Visualizer - Waveform + Spectrum + Features (Phase 1d)")
    window.resize(800, 600)
    window.show()
    app.exec_()


if __name__ == "__main__":
    main()
