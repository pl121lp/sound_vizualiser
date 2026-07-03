import numpy as np

try:
    import sounddevice as sd
except Exception:
    sd = None


class AudioPlaybackUnavailableError(Exception):
    """Raised when audio output can't be started."""


def _default_stream_factory(**kwargs):
    if sd is None:
        raise AudioPlaybackUnavailableError("sounddevice/PortAudio not available")
    return sd.OutputStream(**kwargs)


class AudioPlaybackSource:
    """Plays back an in-memory audio buffer through the default output device.

    Mirrors MicInputSource's shape (start()/stop() + injectable stream_factory) so
    call sites and tests follow the same pattern. The callback advances its own
    position independently of any caller-side read cursor -- callers that want the
    two to track (e.g. after a restart) must call seek() explicitly.
    """

    def __init__(self, data, sample_rate, stream_factory=None):
        self._data = data
        self._sample_rate = sample_rate
        self._stream_factory = stream_factory or _default_stream_factory
        self._stream = None
        self._pos = 0
        self._paused = False
        self._loop = False
        self.finished = False

    def _callback(self, outdata, frames, time_info, status):
        if self._paused:
            outdata.fill(0)
            return

        remaining = len(self._data) - self._pos
        if remaining <= 0:
            if self._loop:
                self._pos = 0
                remaining = len(self._data)
            else:
                outdata.fill(0)
                self.finished = True
                raise sd.CallbackStop()

        n = min(frames, remaining)
        outdata[:n] = self._data[self._pos:self._pos + n]
        if n < frames:
            outdata[n:] = 0
        self._pos += n

    def start(self, start_frame=0):
        self._pos = start_frame
        self.finished = False
        try:
            self._stream = self._stream_factory(
                samplerate=self._sample_rate,
                channels=self._data.shape[1],
                dtype="float32",
                callback=self._callback,
            )
            self._stream.start()
        except AudioPlaybackUnavailableError:
            raise
        except Exception as exc:
            raise AudioPlaybackUnavailableError(str(exc)) from exc

    def stop(self):
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def seek(self, frame):
        self._pos = frame

    def set_paused(self, paused):
        self._paused = paused

    def set_loop(self, loop):
        self._loop = loop
