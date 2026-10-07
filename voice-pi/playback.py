"""Output side of one wake-word interaction: a single audio stream opened
the moment the wake word fires and held open until the answer has played.

A Bluetooth headset's sink sleeps when idle and takes a few hundred ms to
wake once a stream opens — anything played in that window is lost
(confirmed on the OpenComm headset: first words of every answer clipped).
Opening the stream at wake time means the link wakes while the user is
still talking and Whisper is still transcribing, so by the time the answer
is ready it's been up for seconds. Between sounds the stream plays silence,
which is what keeps the sink awake; closing it after the answer lets the
headset drop back to idle.
"""

import threading
import time

import numpy as np
import sounddevice as sd

import config

# Held after the last sample is handed to the device, before closing — the
# device/Bluetooth path has its own buffer, and closing immediately cuts
# off the end of the final word.
_TAIL_SECONDS = 0.3


def _chime(sample_rate: int, frequency: float = 880.0, duration: float = 0.15) -> np.ndarray:
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    tone = (0.3 * 32767 * np.sin(2 * np.pi * frequency * t)).astype(np.int16)
    # The stream was opened a moment ago, so the sink is still waking —
    # without this the (short) tone is swallowed whole.
    lead_in = np.zeros(int(sample_rate * config.OUTPUT_LEAD_IN_SECONDS), dtype=np.int16)
    return np.concatenate([lead_in, tone])


class OutputSession:
    """Use as: `wake_word.listen_and_record(model, on_wake=out.start)`,
    then `with out: ... out.play(samples) ...` — leaving the block waits for
    playback to finish and closes the stream. Safe to close if start() was
    never called."""

    def __init__(self, sample_rate: int):
        self.sample_rate = sample_rate
        self._stream = None
        self._pending = np.zeros(0, dtype=np.int16)
        self._lock = threading.Lock()
        self._drained = threading.Event()
        self._drained.set()

    def start(self) -> None:
        """Open the stream and play the acknowledgment chime. Non-blocking:
        the mic keeps recording the query while this plays."""
        self._stream = sd.OutputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="int16",
            device=config.AUDIO_OUTPUT_DEVICE,
            callback=self._fill,
        )
        self._stream.start()
        self.play(_chime(self.sample_rate))

    def play(self, samples: np.ndarray) -> None:
        """Queue int16 mono samples at self.sample_rate. Non-blocking."""
        with self._lock:
            self._pending = np.concatenate([self._pending, samples.astype(np.int16)])
            self._drained.clear()

    def _fill(self, outdata, frames, time_info, status) -> None:
        with self._lock:
            n = min(frames, len(self._pending))
            outdata[:n, 0] = self._pending[:n]
            outdata[n:] = 0  # silence between sounds keeps the sink awake
            self._pending = self._pending[n:]
            if not len(self._pending):
                self._drained.set()

    def close(self) -> None:
        if self._stream is None:
            return
        with self._lock:
            remaining = len(self._pending) / self.sample_rate
        # Timeout so a stalled/vanished device can't hang the main loop.
        self._drained.wait(timeout=remaining + 5)
        time.sleep(_TAIL_SECONDS)
        self._stream.stop()
        self._stream.close()
        self._stream = None

    def __enter__(self) -> "OutputSession":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
