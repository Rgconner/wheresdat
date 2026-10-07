"""Loads voice.env (copied from voice.env.template) into simple module-level
constants. No framework — this runs standalone on the Pi, not inside the
k8s cluster, so it deliberately doesn't share config machinery with the
services/ FastAPI apps."""

import os
import pathlib

_ENV_PATH = pathlib.Path(__file__).parent / "voice.env"


def _load_env_file(path: pathlib.Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_env_file(_ENV_PATH)

API_URL = os.environ.get("API_URL", "").rstrip("/")
WAKE_WORD_MODEL = os.environ.get("WAKE_WORD_MODEL", "hey_jarvis")
CACHE_DB_PATH = os.environ.get(
    "CACHE_DB_PATH", str(pathlib.Path(__file__).parent / "cache.sqlite3")
)
CACHE_RESYNC_SECONDS = int(os.environ.get("CACHE_RESYNC_SECONDS", "300"))
STT_MODEL_SIZE = os.environ.get("STT_MODEL_SIZE", "base")
TTS_VOICE = os.environ.get("TTS_VOICE", "en_US-lessac-medium")
AUDIO_INPUT_DEVICE = os.environ.get("AUDIO_INPUT_DEVICE") or None
AUDIO_OUTPUT_DEVICE = os.environ.get("AUDIO_OUTPUT_DEVICE") or None
# Silence before the wake chime. The output stream opens at the wake word
# (see playback.py) and a Bluetooth sink takes a few hundred ms to wake, so
# without this the short chime is lost. Answers don't need it — by the time
# one is ready the stream has been open for seconds.
OUTPUT_LEAD_IN_SECONDS = float(os.environ.get("OUTPUT_LEAD_IN_SECONDS", "0.3"))

if AUDIO_INPUT_DEVICE is not None:
    AUDIO_INPUT_DEVICE = int(AUDIO_INPUT_DEVICE)
if AUDIO_OUTPUT_DEVICE is not None:
    AUDIO_OUTPUT_DEVICE = int(AUDIO_OUTPUT_DEVICE)


def require_api_url() -> str:
    if not API_URL or "CHANGE-ME" in API_URL:
        raise RuntimeError(
            "API_URL isn't set in voice.env — this is registration's "
            "externally-exposed URL (the LoadBalancer IP, port 8102), not "
            "datastore's in-cluster address. datastore is ClusterIP-only "
            "on purpose. See voice.env.template."
        )
    return API_URL
