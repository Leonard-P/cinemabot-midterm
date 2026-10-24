# voice.py — speech-to-text and text-to-speech helpers, from lab-06 pattern
from io import BytesIO
import os
from array import array
import tempfile
import wave

import streamlit as st
from openai import OpenAI


def _client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing. Add it to the project .env file.")
    return OpenAI(api_key=api_key)


def _has_speech_energy(wav: wave.Wave_read) -> bool:
    """Reject silent recorder payloads that Whisper may hallucinate from."""
    if wav.getsampwidth() != 2:
        return True
    samples = array("h", wav.readframes(wav.getnframes()))
    if not samples:
        return False
    if wav.getnchannels() > 1:
        samples = samples[::wav.getnchannels()]
    peak = max(abs(sample) for sample in samples)
    rms = (sum(sample * sample for sample in samples) / len(samples)) ** 0.5
    return peak >= 600 and rms >= 120


def speech_to_text(audio_bytes: bytes) -> str | None:
    if not audio_bytes:
        return None

    # The recorder returns WAV bytes. Do not send a tap or an empty recording
    # to Whisper because the API rejects audio under 0.1 sec.
    try:
        with wave.open(BytesIO(audio_bytes), "rb") as wav:
            duration = wav.getnframes() / wav.getframerate()
            has_speech_energy = _has_speech_energy(wav)
    except (wave.Error, EOFError, ZeroDivisionError):
        return None
    if duration < 0.3 or not has_speech_energy:
        return None

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(audio_bytes)
        tmp_path = f.name
    try:
        with open(tmp_path, "rb") as f:
            transcript = _client().audio.transcriptions.create(
                model="whisper-1",
                response_format="text",
                file=f,
            )
        return transcript
    finally:
        os.remove(tmp_path)


def text_to_speech(text: str) -> bytes:
    # strip markdown so the TTS doesn't read out asterisks
    import re
    clean = re.sub(r"[*_`#]", "", text)
    resp = _client().audio.speech.create(model="tts-1", voice="nova", input=clean)
    return resp.content


def autoplay_audio(audio_bytes: bytes) -> None:
    st.audio(audio_bytes, format="audio/mp3", autoplay=True)
