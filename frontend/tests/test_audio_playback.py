import os
import sys

import numpy as np
import pytest
import sounddevice as sd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from audio_playback import AudioPlaybackSource, AudioPlaybackUnavailableError


class FakeStream:
    def __init__(self, callback, samplerate, channels):
        self.callback = callback
        self.samplerate = samplerate
        self.channels = channels
        self.started = False
        self.closed = False

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def close(self):
        self.closed = True

    def feed(self, frames):
        outdata = np.zeros((frames, self.channels), dtype=np.float32)
        self.callback(outdata, frames, None, None)
        return outdata


def make_fake_factory():
    created = {}

    def factory(**kwargs):
        stream = FakeStream(
            callback=kwargs["callback"],
            samplerate=kwargs["samplerate"],
            channels=kwargs["channels"],
        )
        created["stream"] = stream
        return stream

    return factory, created


def make_data():
    return np.array([[0.1], [0.2], [0.3], [0.4]], dtype=np.float32)


def test_normal_read_copies_samples_and_advances_pos():
    factory, created = make_fake_factory()
    source = AudioPlaybackSource(make_data(), 48000.0, stream_factory=factory)
    source.start(0)

    outdata = created["stream"].feed(2)

    np.testing.assert_allclose(outdata, [[0.1], [0.2]])
    assert source._pos == 2


def test_paused_zero_fills_and_does_not_advance():
    factory, created = make_fake_factory()
    source = AudioPlaybackSource(make_data(), 48000.0, stream_factory=factory)
    source.start(0)
    source.set_paused(True)

    outdata = created["stream"].feed(2)

    np.testing.assert_allclose(outdata, np.zeros((2, 1)))
    assert source._pos == 0


def test_loop_wraps_position_to_zero_at_end():
    factory, created = make_fake_factory()
    source = AudioPlaybackSource(make_data(), 48000.0, stream_factory=factory)
    source.start(0)
    source.set_loop(True)
    source.seek(4)  # exactly at the end of the 4-frame buffer

    outdata = created["stream"].feed(2)

    np.testing.assert_allclose(outdata, [[0.1], [0.2]])
    assert source._pos == 2
    assert source.finished is False


def test_non_loop_end_zero_fills_sets_finished_and_raises_callback_stop():
    factory, created = make_fake_factory()
    source = AudioPlaybackSource(make_data(), 48000.0, stream_factory=factory)
    source.start(0)
    source.seek(4)  # exactly at the end of the 4-frame buffer

    with pytest.raises(sd.CallbackStop):
        created["stream"].feed(2)

    assert source.finished is True


def test_seek_repositions_pos():
    factory, _ = make_fake_factory()
    source = AudioPlaybackSource(make_data(), 48000.0, stream_factory=factory)
    source.start(0)

    source.seek(2)

    assert source._pos == 2


def test_start_wraps_factory_failure_in_playback_unavailable_error():
    def failing_factory(**kwargs):
        raise RuntimeError("no default output device")

    source = AudioPlaybackSource(make_data(), 48000.0, stream_factory=failing_factory)

    with pytest.raises(AudioPlaybackUnavailableError):
        source.start()


def test_stop_stops_and_closes_stream():
    factory, created = make_fake_factory()
    source = AudioPlaybackSource(make_data(), 48000.0, stream_factory=factory)
    source.start()

    source.stop()

    assert created["stream"].started is False
    assert created["stream"].closed is True
