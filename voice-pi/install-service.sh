#!/bin/bash
# Run on the Pi itself, from inside this directory, after it's been copied
# to /home/rgcon/wheresdat-voice and voice.env has been filled in (API_URL
# is already correct in voice.env.template — nothing to fill in there for
# a first run, just `cp voice.env.template voice.env`).
set -euo pipefail

TARGET=/home/rgcon/wheresdat-voice

if [ "$(pwd)" != "$TARGET" ]; then
    echo "Run this from $TARGET (copy this whole voice-pi/ directory there first)."
    exit 1
fi

if [ ! -f voice.env ]; then
    echo "voice.env not found — cp voice.env.template voice.env first."
    exit 1
fi

# sounddevice wraps PortAudio, doesn't bundle it — needs the system lib.
sudo apt-get update -qq
sudo apt-get install -y portaudio19-dev libasound2-dev
# pipewire-alsa routes ALSA's "default" device into PipeWire; without it
# PortAudio only sees raw hardware and never a Bluetooth headset. Linger
# keeps rgcon's PipeWire session running at boot for the system service.
sudo apt-get install -y pipewire-alsa
sudo loginctl enable-linger rgcon

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
# openwakeword's own package metadata hard-requires tflite-runtime, which
# has no published wheel for Python 3.13 on aarch64 (confirmed on real
# Pi4/Debian 13 hardware). Installed separately with --no-deps since
# wake_word.py explicitly requests the onnx backend instead — that one
# does have a wheel here, so tflite-runtime is never actually needed at
# runtime, only pip's resolver insists on it if asked for normally.
pip install --no-deps 'openwakeword>=0.6.0'
pip install -r requirements.txt

# Model weights are a separate download from the pip packages themselves.
python3 -c "from openwakeword.utils import download_models; download_models()"

mkdir -p voices
if [ ! -f "voices/en_US-lessac-medium.onnx" ]; then
    python3 -m piper.download_voices en_US-lessac-medium
    # download_voices drops files in the CWD, not ./voices/ — tts.py
    # expects them there specifically.
    mv en_US-lessac-medium.onnx en_US-lessac-medium.onnx.json voices/
fi

sudo cp wheresdat-voice.service /etc/systemd/system/wheresdat-voice.service
sudo systemctl daemon-reload
sudo systemctl enable wheresdat-voice.service
sudo systemctl restart wheresdat-voice.service

echo "Installed. Check status with: sudo systemctl status wheresdat-voice"
echo "Follow logs with:            journalctl -u wheresdat-voice -f"
