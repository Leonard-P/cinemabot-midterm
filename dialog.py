# dialog.py — state machine. The LLM already understood the user; this code decides what to do.
import json
import random
import re
import string
from pathlib import Path

CATALOG = json.loads((Path(__file__).parent / "catalog.json").read_text())

REQUIRED_SLOTS = ["movie", "date", "time", "tickets", "format"]

SLOT_QUESTIONS = {
    "movie":   "What movie would you like to see? We're showing: {movies}.",
    "date":    "What date works for you? (e.g. today, tomorrow, this Friday)",
    "time":    "What showtime? Available for {movie} in {format}: {times}.",
    "tickets": "How many tickets?",
    "format":  "Which format — {formats}?",
}


def _movie(title: str) -> dict | None:
    for m in CATALOG["movies"]:
        if m["title"] == title:
            return m
    return None


def _showtimes(title: str, fmt: str) -> list[str]:
    m = _movie(title)
    return m["showtimes"].get(fmt, []) if m else []


def _valid_showtime(title: str, fmt: str, time: str) -> bool:
    return time in _showtimes(title, fmt)


def _price(title: str, fmt: str, count: int) -> int:
    m = _movie(title)
    return m["price"][fmt] * count if m else 0


def _booking_id() -> str:
    return "CB-" + "".join(random.choices(string.digits, k=4))


def new_state() -> dict:
    return {
        "task": None,           # active task intent
        "movie": None,
        "date": None,
        "time": None,
        "tickets": None,
        "format": None,
        "booking_id": None,
        "awaiting_confirm": False,
        "fail_count": 0,
    }


def _missing(state: dict) -> list[str]:
    return [s for s in REQUIRED_SLOTS if state[s] is None]


def _summary(state: dict) -> str:
    total = _price(state["movie"], state["format"], state["tickets"])
    return (f"{state['tickets']}× {state['format']} — **{state['movie']}**"
            f" on {state['date']} at {state['time']} — **${total}**")


def _merge_slots(state: dict, slots: dict) -> str | None:
    """Merge new slot values into state. Returns an error message if a value is invalid, else None."""
    movie = slots.get("movie")
    if movie is not None:
        if _movie(movie) is None:
            titles = ", ".join(m["title"] for m in CATALOG["movies"])
            return f"We don't show \"{movie}\". Current titles: {titles}."
        state["movie"] = movie

    fmt = slots.get("format")
    if fmt is not None:
        if state["movie"] and fmt not in _movie(state["movie"])["formats"]:
            available = ", ".join(_movie(state["movie"])["formats"])
            return f"{state['movie']} isn't in {fmt}. Available: {available}."
        state["format"] = fmt

    time = slots.get("time")
    if time is not None:
        # only validate against catalog when we already have movie and format
        if state["movie"] and state["format"] and not _valid_showtime(state["movie"], state["format"], time):
            times = ", ".join(_showtimes(state["movie"], state["format"]))
            return f"No {state['format']} showing at {time}. Available: {times}."
        state["time"] = time

    tickets = slots.get("tickets")
    if tickets is not None:
        if tickets > 10:
            return "HANDOFF"  # signal to process_turn
        if tickets < 1:
            return "Ticket count must be at least 1."
        state["tickets"] = tickets

    for key in ("date", "booking_id"):
        if slots.get(key) is not None:
            state[key] = slots[key]

    return None


def _ask_next(state: dict) -> str:
    missing = _missing(state)
    slot = missing[0]
    if slot == "movie":
        titles = ", ".join(m["title"] for m in CATALOG["movies"])
        return SLOT_QUESTIONS["movie"].format(movies=titles)
    if slot == "format":
        m = _movie(state["movie"])
        fmts = ", ".join(m["formats"]) if m else "Standard, IMAX, 3D"
        return SLOT_QUESTIONS["format"].format(formats=fmts)
    if slot == "time":
        times = ", ".join(_showtimes(state["movie"], state["format"]))
        return SLOT_QUESTIONS["time"].format(
            movie=state["movie"], format=state["format"], times=times or "none listed")
    return SLOT_QUESTIONS[slot]


def process_turn(state: dict, slots: dict) -> str:
    """Decide what to reply based on the LLM-extracted slots. Never reads raw text."""
    intent = slots.get("intent", "None")

    # system intents — clear state when appropriate
    if intent == "Handoff":
        state.update(new_state())
        return ("This needs a human team member. "
                "Please call (555) 246-8101 or email help@cinebot.example.")

    if intent == "Cancel":
        had_task = state["task"] is not None
        state.update(new_state())
        return "Cancelled. What else can I help you with?" if had_task else "Nothing to cancel. How can I help?"

    if intent == "Greeting":
        return ("Hi! I'm CineBot. I can book tickets, check showtimes, "
                "or cancel a reservation. What can I do for you?")

    if intent == "Help":
        return ("Here's what I can do:\n"
                "- **Book tickets** — tell me the movie, date, time, seats and format\n"
                "- **Check showtimes** — ask what's playing and when\n"
                "- **Cancel a booking** — share your CB-XXXX reference\n"
                "- Say \"cancel\" at any point to start over")

    # confirmation flow
    if state["awaiting_confirm"]:
        if intent == "Confirm":
            ref = _booking_id()
            summary = _summary(state)
            state.update(new_state())
            return f"Booked! Reference: **{ref}**\n{summary}\n\nEnjoy the film!"
        # anything else (Deny, BookTickets with new slots, etc.) clears confirmation
        # and falls through so the shared merge+route path handles the correction
        state["awaiting_confirm"] = False
        state["task"] = "BookTickets"  # keep the active task

    # set task from detected intent (task intents only)
    if intent in ("BookTickets", "CheckShowtimes", "CancelBooking"):
        state["task"] = intent

    # merge slots regardless of current task (corrections work mid-flow)
    err = _merge_slots(state, slots)
    if err == "HANDOFF":
        state.update(new_state())
        return ("Groups over 10 need our group sales team. "
                "Call (555) 246-8101.")
    if err:
        return err

    # --- route to task handler ---

    if state["task"] == "BookTickets":
        missing = _missing(state)
        if missing:
            return _ask_next(state)
        # re-check time validity now that all slots are present
        if not _valid_showtime(state["movie"], state["format"], state["time"]):
            times = ", ".join(_showtimes(state["movie"], state["format"]))
            state["time"] = None
            return (f"That time isn't available for {state['movie']} in {state['format']}. "
                    f"We have: {times}. Which one?")
        state["awaiting_confirm"] = True
        return f"{_summary(state)}\n\nShall I book it? (yes / no)"

    if state["task"] == "CheckShowtimes":
        movie_title = state["movie"]
        if not movie_title:
            titles = ", ".join(m["title"] for m in CATALOG["movies"])
            return f"Which movie? We're showing: {titles}."
        m = _movie(movie_title)
        lines = [f"**{movie_title}** showtimes:"]
        for fmt, times in m["showtimes"].items():
            lines.append(f"  {fmt}: {', '.join(times)}")
        if state["date"]:
            lines.insert(1, f"_(for {state['date']})_")
        lines.append("\nWant to book seats?")
        return "\n".join(lines)

    if state["task"] == "CancelBooking":
        if not state["booking_id"]:
            return "Please share your booking reference (format: CB-XXXX)."
        ref = state["booking_id"]
        state.update(new_state())
        return f"Booking **{ref}** cancelled. Anything else?"

    # out-of-scope
    state["fail_count"] += 1
    if state["fail_count"] >= 3:
        state.update(new_state())
        return ("I've had trouble a few times. Let me get a human for you — "
                "call (555) 246-8101.")
    return ("I can only help with cinema tickets, showtimes and cancellations. "
            "Anything else I can do?")
