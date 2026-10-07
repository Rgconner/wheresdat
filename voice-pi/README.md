# WheresDat voice-pi

Hands-free retrieval front-end — "Hey Jarvis, M5x30 bolt?" spoken at a
Raspberry Pi mounted at the workbench, answered out loud with the
container's location, walked up through its parent chain.

This is the piece the original project spec called for from the start
(voice control as a hard requirement, not a nice-to-have, because hands
are dirty when you actually need this) and never got built. It runs
independently of the phone app and the k8s cluster's own services — a
standalone process on Pi hardware, with a local cache so it still answers
if the shop network drops.

**It talks to `registration`, not `datastore`, and not the raw database.**
`datastore` (the FastAPI service that actually owns the Postgres tables)
is `ClusterIP`-only — not reachable from outside the cluster at all, on
purpose. `registration` is the already-externally-exposed LoadBalancer
service that already proxies `/containers/search` straight through to
datastore. voice-pi reuses that existing, already-API-gated surface
rather than needing datastore (or, worse, the database itself) opened up
to the shop network just for this.

## Why a Pi, not the phone or the mini-PC cluster

- Phone OS background-mic restrictions make a real always-listening wake
  word unreliable without the app in the foreground — and the phone is
  explicitly the device that leaves the shed and gets reset/replaced.
- The mini-PC cluster already has a job (vision pipeline, database of
  record) and isn't physically positioned for mic pickup at the bench.
- A Pi is cheap, dedicated, mountable exactly where pickup quality
  matters, and openWakeWord/faster-whisper/Piper are all real, proven,
  Pi-CPU-sized local tooling — no cloud STT/TTS dependency, no
  always-on audio leaving the shop network.

## Architecture

```
wake word (local, openWakeWord)
  -> record ~4s
  -> speech-to-text (local, faster-whisper)
  -> search local SQLite cache (resynced via registration's
     /containers/search every 5 min — API_URL, not datastore)
     -> falls back to a live /containers/search call only if the
        cache comes back empty and the network's actually up
  -> walk parent_code chain in the cache for a full location trail
  -> text-to-speech (local, Piper) speaks the answer
```

The cache is a full wholesale resync, not incremental. datastore's own
`GET /containers` (bulk list) has no `since=` filter and isn't reachable
externally anyway — registration doesn't proxy that particular route, so
the resync instead calls `/containers/search?q=` with an empty query,
which matches everything via the same `LIKE '%%'` the search endpoint
already does. This dataset is small enough that a full replace on every
sync is simpler and plenty fast regardless.

## Setup

Deployed and verified on real hardware 2026-09-24 (Pi4, Raspberry Pi OS
64-bit / Debian 13 "trixie", Python 3.13, aarch64) — the steps below are
what actually worked, not the original untested plan. A few things
differed from a naive setup; each is called out where it bit.

1. **Format the Pi** (you're doing this part) — Raspberry Pi OS, 64-bit,
   Bookworm or newer. Enable SSH. Have a USB or HAT-based mic/speaker
   ready — the Pi's own hardware doesn't have a mic, only a headphone-out
   jack (confirmed via `sounddevice.query_devices()`: 0 input channels).

2. **Copy this directory to the Pi**, at `/home/<user>/wheresdat-voice`
   (not `/home/pi/` — that's only the username if you actually created a
   `pi` user; check with `cat /etc/passwd | grep 1000`, since Raspberry Pi
   Imager lets you set a custom username during imaging and won't
   necessarily be `pi`):
   ```
   scp -r voice-pi/ <user>@<pi-hostname>:/home/<user>/wheresdat-voice
   ```

3. **Fill in config**: `cp voice.env.template voice.env`. `API_URL` is
   already set to registration's real LoadBalancer address
   (`192.0.2.16:8102`, confirmed via `kubectl get svc -n wheresdat`,
   and confirmed reachable from the Pi across the home LAN / cluster
   subnet split via `curl`) — double check it still matches if the
   cluster's networking changes later. Also fix `CACHE_DB_PATH` if your
   username isn't `rgcon`.

4. **System dependency first** — `sounddevice` wraps PortAudio, doesn't
   bundle it:
   ```
   sudo apt-get install portaudio19-dev libasound2-dev
   ```

5. **Python packages, in two steps, not one `pip install -r requirements.txt`**:
   ```
   python3 -m venv .venv && source .venv/bin/activate
   pip install --no-deps 'openwakeword>=0.6.0'
   pip install -r requirements.txt
   ```
   openwakeword's own package metadata hard-requires `tflite-runtime`,
   which has no published wheel for Python 3.13 on aarch64 — confirmed,
   not a guess. It works fine on the *other* backend it supports, onnx
   (which does have a wheel here), and `wake_word.py` already requests
   `inference_framework="onnx"` explicitly — so tflite-runtime is never
   actually needed at runtime, only pip's resolver insists on it if asked
   for normally. requirements.txt deliberately omits openwakeword from
   its own list so a plain `pip install -r requirements.txt` doesn't
   re-trigger the same failure.

6. **Download the wake-word model weights** (separate from the pip
   package, which ships code only):
   ```
   python3 -c "from openwakeword.utils import download_models; download_models()"
   ```
   `wake_word.py` also calls this itself on every startup (idempotent,
   no-ops if already present), so this step is really just for a faster
   first `main.py` run, not strictly required by hand.

7. **Fetch a Piper voice** (not bundled in the pip package):
   ```
   python3 -m piper.download_voices en_US-lessac-medium
   mv en_US-lessac-medium.onnx en_US-lessac-medium.onnx.json voices/
   ```
   `download_voices` drops files in the current directory, NOT
   `./voices/` — confirmed, the move step is required, not optional.
   Swap `en_US-lessac-medium` for any other Piper voice if you'd rather;
   just keep `TTS_VOICE` in voice.env matching the filename.

8. **Install and start the service**:
   ```
   cd /home/<user>/wheresdat-voice
   ./install-service.sh
   ```
   (`install-service.sh` and `wheresdat-voice.service` both assume
   username `rgcon` — edit both if yours differs.)

9. **Test without the service** first if anything's misbehaving —
   `python3 main.py` runs it in the foreground with logs on screen,
   easier to debug than journalctl on a first pass.

## Verified working, real hardware (2026-09-24)

Cache sync against the real `registration` API, all three models
(openWakeWord/hey_jarvis, faster-whisper/base, Piper/en_US-lessac-medium)
loading cleanly, and the full TTS synthesis+playback path all confirmed
end-to-end. Only untested piece is the actual wake-word listening loop
itself, which needs a real mic plugged in — everything up to that point
(`main.py` run straight through) fails exactly where expected (no input
audio device) and nowhere else.

## Known rough edges (v1, honestly)

- **Wake word**: no pretrained "hey wheresdat" model exists — openWakeWord
  ships general ones (alexa, hey_jarvis, hey_mycroft). Starting with
  `hey_jarvis`. Training a custom wake word is a real, documented
  openWakeWord workflow if you want the actual phrase later — not done
  here, this ships with a placeholder trigger phrase.
- **Query recording is fixed-length (4s)**, not silence-detected — simple
  and reliable for short part-number-shaped queries, but it'll either cut
  off a longer question or sit listening through silence on a short one.
  Worth revisiting with real voice-activity detection once you see how
  4 seconds actually feels in practice.
- **No confirmation/retry loop** — if STT mishears the query, it just
  searches for the wrong text and reports no match or the wrong item.
  Fine for a v1; a "did you mean" step would be a reasonable v2.
