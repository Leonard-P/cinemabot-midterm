# voice.py — speech-to-text and text-to-speech helpers, from lab-06 pattern
import base64
import os
import tempfile

import streamlit as st
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def speech_to_text(audio_bytes: bytes) -> str | None:
    # write bytes to a temp mp3 and transcribe with Whisper
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        f.write(audio_bytes)
        tmp_path = f.name
    try:
        with open(tmp_path, "rb") as f:
            transcript = client.audio.transcriptions.create(
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
    resp = client.audio.speech.create(model="tts-1", voice="nova", input=clean)
    return resp.content


def autoplay_audio(audio_bytes: bytes) -> None:
    b64 = base64.b64encode(audio_bytes).decode()
    st.markdown(
        f'<audio autoplay><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>',
        unsafe_allow_html=True,
    )
