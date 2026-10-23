# app.py — CineBot: Cinema Ticket & Showtime Assistant
import os
import time

import streamlit as st
from dotenv import load_dotenv

from dialog import new_state, process_turn
from extraction import extract

load_dotenv()

# voice is optional — only imported when the packages are installed
try:
    from audio_recorder_streamlit import audio_recorder
    from voice import speech_to_text, text_to_speech, autoplay_audio
    VOICE_OK = True
except ImportError:
    VOICE_OK = False

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

# chat history
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])


def handle_input(user_text: str, voice_latency: float | None = None):
    st.session_state.messages.append({"role": "user", "content": user_text})

    history = [msg for msg in st.session_state.messages if msg["role"] != "system"]

    t0 = time.time()
    slots, source = extract(user_text, history)
    latency = time.time() - t0

    reply = process_turn(st.session_state.dialog, slots)

    # voice output — speak the reply if input came from mic
    if voice_latency is not None and VOICE_OK:
        t1 = time.time()
        audio = text_to_speech(reply)
        voice_latency += time.time() - t1
        autoplay_audio(audio)

    st.session_state.debug = {
        **slots,
        "source": source,
        "latency": latency,
        "voice_latency": voice_latency,
    }
    st.session_state.messages.append({"role": "assistant", "content": reply})
    st.rerun()


# voice input
if VOICE_OK:
    st.markdown("---")
    st.caption("Speak or type:")
    audio_bytes = audio_recorder(pause_threshold=2.0, sample_rate=16000)
    if audio_bytes:
        with st.spinner("Transcribing..."):
            t0 = time.time()
            transcript = speech_to_text(audio_bytes)
            stt_latency = time.time() - t0
        if transcript:
            with st.chat_message("user"):
                st.markdown(f"🎤 {transcript}")
            handle_input(transcript, voice_latency=stt_latency)

# text input
if user_text := st.chat_input("e.g. Two IMAX tickets for Dune this Friday at 8pm"):
    handle_input(user_text)
