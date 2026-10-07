"""Always-on wake-word listener using openWakeWord, plus the microphone
recording used for the query itself once triggered.

openWakeWord runs entirely locally (ONNX models, no cloud call) — this is
the piece that makes an always-listening device viable on Pi hardware and
on a home network without a "someone's audio is streaming to a cloud
service continuously" privacy question hanging over it.
"""

import logging
import time
from collections.abc import Callable
from math import gcd

import numpy as np
import sounddevice as sd
from openwakeword.model import Model as WakeModel
from scipy.signal import resample_poly

import config

log = logging.getLogger("voice-pi.wake")

TARGET_SAMPLE_RATE = 16000  # required by openWakeWord and faster-whisper
FRAME_SAMPLES = 1280  # openWakeWord's expected chunk size at 16kHz
QUERY_SECONDS = 4.0
WAKE_THRESHOLD = 0.5


def _device_input_rate(device) -> int:
    # Capture mics don't all support 16kHz directly — the Anker PowerConf
    # C200 (confirmed on real hardware) only opens at its native 48000Hz;
    # PortAudio raises "Invalid sample rate [PaErrorCode -9997]" otherwise.
    # Recording at whatever rate the device actually supports and
    # resampling in software avoids hardcoding a rate that only works for
    # one specific mic.
    info = sd.query_devices(device, "input")
    return int(round(info["default_samplerate"]))


def _to_target_rate(audio: np.ndarray, from_rate: int) -> np.ndarray:
    if from_rate == TARGET_SAMPLE_RATE:
        return audio
    factor = gcd(from_rate, TARGET_SAMPLE_RATE)
    up, down = TARGET_SAMPLE_RATE // factor, from_rate // factor
    resampled = resample_poly(audio.astype(np.float32), up, down)
    return np.clip(resampled, -32768, 32767).astype(np.int16)


def load_wake_model() -> WakeModel:
    # openwakeword's pip package ships code only — the actual model
    # weights (.onnx/.tflite) are a separate download, fetched here on
    # first run rather than left as a silent manual prerequisite.
    # Idempotent: no-ops if already present.
    from openwakeword.utils import download_models
    download_models()

    log.info("Loading wake-word model: %s", config.WAKE_WORD_MODEL)
    # inference_framework explicit, not default: tflite-runtime has no
    # published wheel for Python 3.13 on aarch64 (confirmed on real
    # hardware, Debian 13), so this deploys with only the onnx backend
    # installed — openwakeword's pretrained models ship in both formats,
    # this just has to actually ask for the one that's present.
    return WakeModel(wakeword_models=[config.WAKE_WORD_MODEL], inference_framework="onnx")


def listen_and_record(
    model: WakeModel,
    on_wake: Callable[[], None],
    query_seconds: float = QUERY_SECONDS,
) -> np.ndarray:
    """Blocks until the wake word fires, calls on_wake (opens the output
    stream and plays the acknowledgment chime — must not block, or it adds
    straight to the wake-to-recording gap below), then immediately captures the
    query on the SAME already-open input stream — no stream teardown and
    reopen between detection and recording. Confirmed on real hardware
    that tearing down and reopening a fresh stream (the previous
    listen-then-record split) added ~0.8s of dead gap on the C200's USB
    connection; said in one breath with no pause after the wake phrase,
    the whole query landed in that gap and got recorded as silence."""
    device_rate = _device_input_rate(config.AUDIO_INPUT_DEVICE)
    raw_frame_samples = round(FRAME_SAMPLES * device_rate / TARGET_SAMPLE_RATE)
    if device_rate != TARGET_SAMPLE_RATE:
        log.info(
            "Mic native rate %dHz, resampling to %dHz for the wake-word model",
            device_rate, TARGET_SAMPLE_RATE,
        )

    with sd.InputStream(
        samplerate=device_rate,
        channels=1,
        dtype="int16",
        blocksize=raw_frame_samples,
        device=config.AUDIO_INPUT_DEVICE,
    ) as stream:
        while True:
            frame, _ = stream.read(raw_frame_samples)
            frame16k = _to_target_rate(frame.flatten(), device_rate)
            # Rounding in raw_frame_samples can be off by a sample or two
            # for non-integer rate ratios; openWakeWord expects exactly
            # FRAME_SAMPLES per call.
            if len(frame16k) > FRAME_SAMPLES:
                frame16k = frame16k[:FRAME_SAMPLES]
            elif len(frame16k) < FRAME_SAMPLES:
                frame16k = np.pad(frame16k, (0, FRAME_SAMPLES - len(frame16k)))
            predictions = model.predict(frame16k)
            score = predictions.get(config.WAKE_WORD_MODEL, 0.0)
            if score >= WAKE_THRESHOLD:
                log.info("Wake word detected (score=%.2f)", score)
                model.reset()
                break

        on_wake()

        log.info("Recording query (%.1fs)...", query_seconds)
        query_raw_samples = int(query_seconds * device_rate)
        chunks = []
        captured = 0
        while captured < query_raw_samples:
            n = min(raw_frame_samples, query_raw_samples - captured)
            chunk, _ = stream.read(n)
            chunks.append(chunk)
            captured += chunk.shape[0]
        raw_audio = np.concatenate(chunks).flatten()

    return _to_target_rate(raw_audio, device_rate)
