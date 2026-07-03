import queue

import numpy as np

try:
    import sounddevice as sd
except Exception:
    sd = None


class MicUnavailableError(Exception):
    """Raised when live microphone capture can't be started."""


def _default_stream_factory(**kwargs):
    if sd is None:
        raise MicUnavailableError("sounddevice/PortAudio not available")
    return sd.InputStream(**kwargs)


class MicInputSource:
    """Live mic capture, backed by sounddevice/PortAudio.

    Only this one backend exists today, but callers (main.py) only use start(),
    stop(), read_available(), sample_rate, and channels -- a different platform
    backend could implement the same surface without touching call sites.
    """

    def __init__(self, stream_factory=None):
        self._stream_factory = stream_factory or _default_stream_factory
        self._stream = None
        self._queue = queue.Queue()
        self.sample_rate = None
        self.channels = 1

    def _callback(self, indata, frames, time_info, status):
        self._queue.put(indata[:, 0].copy())

    def start(self):
        try:
            self._stream = self._stream_factory(
                channels=self.channels,
                dtype="float32",
                callback=self._callback,
            )
            self._stream.start()
        except MicUnavailableError:
            raise
        except Exception as exc:
            raise MicUnavailableError(str(exc)) from exc

        self.sample_rate = float(self._stream.samplerate)

    def stop(self):
        self._stream.stop()
        self._stream.close()
        self._stream = None

    def read_available(self):
        chunks = []
        while True:
            try:
                chunks.append(self._queue.get_nowait())
            except queue.Empty:
                break
        if not chunks:
            return None
        return np.concatenate(chunks)
