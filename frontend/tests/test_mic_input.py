import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from mic_input import MicInputSource, MicUnavailableError


class FakeStream:
    def __init__(self, callback, samplerate=48000.0):
        self.callback = callback
        self.samplerate = samplerate
        self.started = False
        self.closed = False

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def close(self):
        self.closed = True

    def feed(self, mono_frame: np.ndarray):
        # sounddevice calls back with shape (frames, channels); channels=1 here.
        indata = mono_frame.reshape(-1, 1).astype(np.float32)
        self.callback(indata, len(mono_frame), None, None)


def make_fake_factory():
    created = {}

    def factory(**kwargs):
        stream = FakeStream(callback=kwargs["callback"])
        created["stream"] = stream
        return stream

    return factory, created


def test_read_available_returns_none_when_nothing_captured():
    factory, _ = make_fake_factory()
    source = MicInputSource(stream_factory=factory)
    source.start()

    assert source.read_available() is None


def test_read_available_drains_and_concatenates_callback_frames():
    factory, created = make_fake_factory()
    source = MicInputSource(stream_factory=factory)
    source.start()

    created["stream"].feed(np.array([0.1, 0.2], dtype=np.float32))
    created["stream"].feed(np.array([0.3], dtype=np.float32))

    result = source.read_available()

    np.testing.assert_allclose(result, [0.1, 0.2, 0.3])
    assert source.read_available() is None  # queue drained


def test_start_sets_sample_rate_from_stream():
    factory, _ = make_fake_factory()
    source = MicInputSource(stream_factory=factory)

    assert source.sample_rate is None
    source.start()
    assert source.sample_rate == 48000.0
    assert source.channels == 1


def test_start_wraps_factory_failure_in_mic_unavailable_error():
    def failing_factory(**kwargs):
        raise RuntimeError("no default input device")

    source = MicInputSource(stream_factory=failing_factory)

    with pytest.raises(MicUnavailableError):
        source.start()


def test_stop_stops_and_closes_stream():
    factory, created = make_fake_factory()
    source = MicInputSource(stream_factory=factory)
    source.start()

    source.stop()

    assert created["stream"].started is False
    assert created["stream"].closed is True
