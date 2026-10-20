# app.py — CineBot: Cinema Ticket & Showtime Assistant
import os
import time

import streamlit as st
from dotenv import load_dotenv

from dialog import new_state, process_turn
from extraction import extract

load_dotenv()

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
        st.caption(f"source: {d['source']}  |  latency: {d.get('latency', 0):.2f}s")
    if d.get("_tokens"):
        tok = d["_tokens"]
        st.caption(f"tokens — prompt: {tok['prompt']}, completion: {tok['completion']}")
    st.markdown("**Extracted slots:**")
    st.json({k: v for k, v in d.items()
             if k not in ("intent", "source", "latency", "_tokens") and v is not None})
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

# user input
if user_text := st.chat_input("e.g. Two IMAX tickets for Dune this Friday at 8pm"):
    st.session_state.messages.append({"role": "user", "content": user_text})

    # pass only non-system messages as history for memory trimming (A6)
    history = [msg for msg in st.session_state.messages if msg["role"] != "system"]

    t0 = time.time()
    slots, source = extract(user_text, history)
    latency = time.time() - t0

    reply = process_turn(st.session_state.dialog, slots)

    st.session_state.debug = {**slots, "source": source, "latency": latency}
    st.session_state.messages.append({"role": "assistant", "content": reply})
    st.rerun()
