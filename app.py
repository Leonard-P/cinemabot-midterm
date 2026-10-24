# app.py — CineBot: Cinema Ticket & Showtime Assistant
import os
import time
import hashlib

import streamlit as st
from dotenv import load_dotenv

from dialog import new_state, process_turn
from extraction import extract

load_dotenv()

# voice is optional — only imported when the packages are installed
try:
    from streamlit_mic_recorder import mic_recorder
    from voice import speech_to_text, text_to_speech, autoplay_audio
    VOICE_OK = True
except ImportError as exc:
    VOICE_OK = False
    VOICE_ERROR = f"{type(exc).__name__}: {exc}"
else:
    VOICE_ERROR = None

st.set_page_config(page_title="CineBot", page_icon="🎬", layout="wide")
st.title("🎬 CineBot — Cinema Ticket Assistant")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content":
         "Hi! I'm **CineBot**. I can book tickets, check showtimes, "
         "or cancel a reservation. What can I do for you?"}
    ]
    st.session_state.dialog = new_state()
    st.session_state.debug = {}
st.session_state.setdefault("processed_audio_digest", None)
st.session_state.setdefault("voice_recorder_key", 0)
st.session_state.setdefault("voice_enabled", False)
st.session_state.setdefault("pending_audio", None)
st.session_state.setdefault("tts_generating", False)

# sidebar debug panel (R9)
with st.sidebar:
    st.subheader("Debug panel")
    d = st.session_state.debug
    st.markdown(f"**Intent:** `{d.get('intent', '—')}`")
    if d.get("source"):
        src_label = d["source"]
        lat = d.get("latency", 0)
        vlat = d.get("voice_latency")
        lat_str = f"{lat:.2f}s extract"
        if vlat:
            lat_str += f" | {vlat:.2f}s voice"
        st.caption(f"source: {src_label}  |  {lat_str}")
    if d.get("_tokens"):
        tok = d["_tokens"]
        st.caption(f"tokens — prompt: {tok['prompt']}, completion: {tok['completion']}")
    st.markdown("**Extracted slots:**")
    st.json({k: v for k, v in d.items()
             if k not in ("intent", "source", "latency", "voice_latency", "_tokens", "_tool_log")
             and v is not None})
    if d.get("_tool_log"):
        st.markdown("**Tool calls:**")
        for entry in d["_tool_log"]:
            st.json(entry)
    st.markdown("**Dialog state:**")
    st.json({k: v for k, v in st.session_state.dialog.items() if v not in (None, 0, False)})
    st.markdown("---")
    if st.button("Start over"):
        del st.session_state["messages"]
        st.rerun()

def handle_input(user_text: str, voice_latency: float | None = None):
    st.session_state.messages.append({"role": "user", "content": user_text})
    # Render the new message in the transcript before the blocking model call.
    # The next rerun renders it from session state, so it is not duplicated.
    with transcript_tail:
        with st.chat_message("user"):
            st.markdown(user_text)

    history = [msg for msg in st.session_state.messages if msg["role"] != "system"]

    with status_slot:
        with st.spinner("Thinking..."):
            t0 = time.time()
            slots, source = extract(user_text, history)
            latency = time.time() - t0
            reply = process_turn(st.session_state.dialog, slots)

    # Voice output speaks replies to voice messages. The text reply is already
    # available even if the optional TTS request fails.
    if voice_latency is not None and VOICE_OK:
        t1 = time.time()
        st.session_state.tts_generating = True
        with status_slot:
            with st.spinner("Generating voice reply..."):
                try:
                    audio = text_to_speech(reply)
                except RuntimeError as exc:
                    st.warning(f"Voice reply unavailable: {exc}")
                    audio = None
        st.session_state.tts_generating = False
        if audio is not None:
            voice_latency += time.time() - t1
            st.session_state.pending_audio = audio

    st.session_state.debug = {
        **slots,
        "source": source,
        "latency": latency,
        "voice_latency": voice_latency,
    }
    st.session_state.messages.append({"role": "assistant", "content": reply})
    st.rerun()


# chat history
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# Reserve the transcript position before the fixed footer. Submitted messages
# render here even though the input callback runs after the footer is created.
transcript_tail = st.container()

# Keep voice controls above Streamlit's native bottom-pinned chat input.
with st.container():
    if VOICE_OK:
        if not st.session_state.voice_enabled:
            if st.button("Enable microphone", use_container_width=True):
                st.session_state.voice_enabled = True
                st.rerun()
            status_slot = st.empty()
        else:
            recording = mic_recorder(
                start_prompt="🎙️ Record",
                stop_prompt="⏹️ Stop",
                just_once=True,
                use_container_width=True,
                format="wav",
                key=f"cinebot-recorder-{st.session_state.voice_recorder_key}",
            )
            status_slot = st.empty()
            audio_bytes = recording.get("bytes") if recording else None
            digest = hashlib.sha256(audio_bytes).hexdigest() if audio_bytes else None
            if audio_bytes and digest != st.session_state.processed_audio_digest:
                st.session_state.processed_audio_digest = digest
                st.session_state.voice_recorder_key += 1
                with st.spinner("Transcribing..."):
                    t0 = time.time()
                    transcript = speech_to_text(audio_bytes)
                    stt_latency = time.time() - t0
                if transcript:
                    handle_input(transcript, voice_latency=stt_latency)
                else:
                    st.warning(
                        "No clear speech was detected. Please hold the microphone "
                        "closer and record a complete sentence."
                    )
                    st.rerun()
    else:
        status_slot = st.empty()
        st.warning(f"Microphone unavailable: {VOICE_ERROR}")

    if st.session_state.pending_audio is not None:
        autoplay_audio(st.session_state.pending_audio)
        st.session_state.pending_audio = None
    elif st.session_state.tts_generating:
        with status_slot:
            st.info("Generating voice reply...")

if user_text := st.chat_input("e.g. Two IMAX tickets for Dune this Friday at 8pm"):
    handle_input(user_text)
