"""Piper TTS integration — generates WAV audio from text."""

import io
import os
import wave
import urllib.request
from pathlib import Path

VOICE_NAME = "en_US-lessac-medium"
VOICE_URL = (
    "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/"
    "en/en_US/lessac/medium/en_US-lessac-medium.onnx"
)
VOICE_CONFIG_URL = VOICE_URL + ".json"

# Use writable dir — /tmp on Railway, local voices/ for dev
VOICES_DIR = Path(os.environ.get("TMPDIR", Path(__file__).parent / "voices"))

_voice = None


def _download_voice():
    """Download voice model files if not present."""
    VOICES_DIR.mkdir(parents=True, exist_ok=True)
    model_path = VOICES_DIR / f"{VOICE_NAME}.onnx"
    config_path = VOICES_DIR / f"{VOICE_NAME}.onnx.json"

    if not model_path.exists():
        print(f"[TTS] Downloading voice model to {model_path}...")
        urllib.request.urlretrieve(VOICE_URL, str(model_path))
        print(f"[TTS] Model downloaded ({model_path.stat().st_size // 1024 // 1024}MB)")

    if not config_path.exists():
        print(f"[TTS] Downloading voice config...")
        urllib.request.urlretrieve(VOICE_CONFIG_URL, str(config_path))
        print(f"[TTS] Config downloaded")

    return model_path


def _get_voice():
    """Load the Piper voice, downloading if needed. Cached after first call."""
    global _voice
    if _voice is not None:
        return _voice

    model_path = _download_voice()

    from piper import PiperVoice
    print(f"[TTS] Loading voice model...")
    _voice = PiperVoice.load(str(model_path))
    print(f"[TTS] Voice loaded")
    return _voice


def synthesize_wav(text):
    """Convert text to WAV bytes using Piper TTS.

    Returns bytes containing a complete WAV file.
    """
    voice = _get_voice()
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        voice.synthesize_wav(text, wav_file)
    return buffer.getvalue()
