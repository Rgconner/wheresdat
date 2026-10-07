"""Local speech-to-text via faster-whisper (CTranslate2 Whisper) — runs on
Pi4/5 CPU without a network round-trip. Model size is a real latency/
accuracy tradeoff on this hardware; see STT_MODEL_SIZE in voice.env."""

import logging
import re

import numpy as np
from faster_whisper import WhisperModel

import config

log = logging.getLogger("voice-pi.stt")


def load_stt_model() -> WhisperModel:
    log.info("Loading Whisper model: %s (int8, CPU)", config.STT_MODEL_SIZE)
    # int8 compute type: the realistic choice on Pi CPU, meaningfully faster
    # than float32 with an accuracy cost that's a fine trade for short,
    # part-number-shaped queries rather than long-form dictation.
    return WhisperModel(config.STT_MODEL_SIZE, device="cpu", compute_type="int8")


def transcribe(
    model: WhisperModel, audio_int16: np.ndarray, sample_rate: int = 16000, initial_prompt: str | None = None
) -> str:
    audio_float32 = audio_int16.astype(np.float32) / 32768.0
    segments, _info = model.transcribe(
        audio_float32,
        language="en",
        beam_size=1,  # greedy — latency matters more than marginal accuracy here
        vad_filter=True,
        initial_prompt=initial_prompt,
    )
    text = " ".join(seg.text.strip() for seg in segments).strip()
    # Whisper punctuates its output ("screws.") but the search downstream
    # is a raw substring LIKE match against container fields — trailing
    # punctuation that isn't literally part of the stored text breaks the
    # match. Strip it here rather than in every search call site.
    text = re.sub(r"^[\s.,!?]+|[\s.,!?]+$", "", text)
    log.info("Transcribed: %r", text)
    return text
