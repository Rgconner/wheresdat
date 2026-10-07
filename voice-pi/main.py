"""Entry point: load models, sync the cache, then loop forever on
wake-word -> record -> transcribe -> search -> speak.

Run directly for testing: python3 main.py
Run as a service: see install-service.sh
"""

import logging

import cache as cache_mod
import config
import playback
import query
import stt
import tts
import wake_word

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
log = logging.getLogger("voice-pi.main")


def main() -> None:
    api_url = config.require_api_url()

    container_cache = cache_mod.ContainerCache(config.CACHE_DB_PATH)
    log.info("Initial cache sync...")
    if not container_cache.resync(api_url):
        age = container_cache.last_sync_age_seconds()
        if age is None:
            log.warning(
                "No cache present and initial sync failed — starting with an "
                "empty cache. Queries will only work while the network to "
                "the API is reachable."
            )
        else:
            log.warning("Initial sync failed, using existing cache (%.0fs old)", age)

    cache_mod.start_background_resync(
        container_cache, api_url, config.CACHE_RESYNC_SECONDS
    )

    wake_model = wake_word.load_wake_model()
    stt_model = stt.load_stt_model()
    tts_voice = tts.load_tts_voice()

    log.info("Ready. Listening for wake word: %s", config.WAKE_WORD_MODEL)

    while True:
        # Output opens at the wake word (on_wake) and closes once the answer
        # has played — see playback.py for why it isn't opened per-sound.
        out = playback.OutputSession(tts_voice.config.sample_rate)
        audio = wake_word.listen_and_record(wake_model, on_wake=out.start)
        with out:
            vocab_prompt = container_cache.vocabulary_prompt()
            text = stt.transcribe(stt_model, audio, initial_prompt=vocab_prompt)
            response = query.answer(container_cache, text)
            tts.speak(tts_voice, response, out)


if __name__ == "__main__":
    main()
