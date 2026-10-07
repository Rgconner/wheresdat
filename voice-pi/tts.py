"""Local text-to-speech via Piper — ONNX-based, runs comfortably on Pi4/5
CPU, no network call. Voice model files (.onnx + .onnx.json) are NOT bundled
in the pip package and need to be downloaded separately; see README.md.
"""

import logging
import pathlib

import numpy as np
from piper import PiperVoice

import config
from playback import OutputSession

log = logging.getLogger("voice-pi.tts")

_VOICE_DIR = pathlib.Path(__file__).parent / "voices"


def load_tts_voice() -> PiperVoice:
    model_path = _VOICE_DIR / f"{config.TTS_VOICE}.onnx"
    config_path = _VOICE_DIR / f"{config.TTS_VOICE}.onnx.json"
    if not model_path.exists() or not config_path.exists():
        raise RuntimeError(
            f"Piper voice files not found at {model_path} — download the "
            f"'{config.TTS_VOICE}' voice from Piper's voice catalog into "
            f"{_VOICE_DIR}/ (both the .onnx and .onnx.json files). See "
            "README.md for the exact fetch command."
        )
    log.info("Loading Piper voice: %s", config.TTS_VOICE)
    return PiperVoice.load(str(model_path), str(config_path))


def speak(voice: PiperVoice, text: str, out: OutputSession) -> None:
    """Queues the answer on the interaction's already-open output stream
    (opened at wake time, so a Bluetooth sink is awake by now). Returns
    once queued; closing `out` waits for playback to finish."""
    log.info("Speaking: %r", text)
    # PiperVoice.synthesize() yields AudioChunk objects with a raw int16
    # PCM buffer per chunk in current piper-tts releases — if the installed
    # version's return shape differs, this is the one call to adjust.
    # Each chunk (roughly a sentence) is queued as soon as it's synthesized:
    # measured on the Pi4, Piper takes ~7.7s to synthesize ~4s of speech,
    # so waiting for the whole answer before playing any of it roughly
    # doubled the time to first word.
    for audio_chunk in voice.synthesize(text):
        out.play(np.frombuffer(audio_chunk.audio_int16_bytes, dtype=np.int16))
