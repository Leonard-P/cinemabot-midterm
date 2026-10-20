# extraction.py — LLM slot extraction + regex fallback + validation
import json
import os
import re
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY")) if os.getenv("OPENAI_API_KEY") else None
MODEL = "gpt-4o-mini"

CATALOG = json.loads((Path(__file__).parent / "catalog.json").read_text())

MOVIE_SYNONYM_MAP = {}
for _m in CATALOG["movies"]:
    MOVIE_SYNONYM_MAP[_m["title"].lower()] = _m["title"]
    for _s in _m["synonyms"]:
        MOVIE_SYNONYM_MAP[_s.lower()] = _m["title"]

FORMAT_SYNONYM_MAP = {}
for _canonical, _syns in CATALOG["format_synonyms"].items():
    FORMAT_SYNONYM_MAP[_canonical.lower()] = _canonical
    for _s in _syns:
        FORMAT_SYNONYM_MAP[_s.lower()] = _canonical

TODAY = date.today()

# The LLM does all understanding. Python only normalizes types afterward.
EXTRACTION_PROMPT = f"""You are the understanding layer of CineBot, a cinema ticket assistant.
For every user message, return a single JSON object with these keys:

  intent     – exactly one of:
                 BookTickets     (user wants to buy/reserve seats)
                 CheckShowtimes  (user wants to know what's playing or when)
                 CancelBooking   (user wants to cancel an existing reservation)
                 Greeting        (hello, hi, good morning, etc.)
                 Help            (asking what the bot can do)
                 Cancel          (abort the current task, start over)
                 Confirm         (user says yes / confirm / book it / go ahead)
                 Deny            (user says no / don't book / change something)
                 Handoff         (billing dispute, refund, group >10, accessibility, or repeated failure)
                 None            (anything else out of scope)
  movie      – movie title exactly as the user said it, or null
  date       – date as the user said it ("today", "tomorrow", "Friday", "2026-10-25"), or null
  time       – showtime as the user said it ("7pm", "9:30", "matinee", "evening"), or null
  tickets    – ticket count as the user said it ("2", "two", "a pair", "me and my friend"), or null
  format     – screening format as the user said it ("IMAX", "3D", "standard"), or null
  booking_id – booking reference code like CB-4829, or null

Rules:
- Return ONLY the JSON object, no other text.
- Use null for slots the user didn't mention.
- Extract raw values; do not resolve dates or convert numbers — Python handles that.
- Today's date is {TODAY.isoformat()}.

Examples:
User: "Two IMAX tickets for Dune tonight at 9:30"
{{"intent":"BookTickets","movie":"Dune","date":"tonight","time":"9:30pm","tickets":"two","format":"IMAX","booking_id":null}}

User: "What times is Oppenheimer playing this Saturday?"
{{"intent":"CheckShowtimes","movie":"Oppenheimer","date":"this Saturday","time":null,"tickets":null,"format":null,"booking_id":null}}

User: "Cancel my booking CB-4829"
{{"intent":"CancelBooking","movie":null,"date":null,"time":null,"tickets":null,"format":null,"booking_id":"CB-4829"}}

User: "yes, book it"
{{"intent":"Confirm","movie":null,"date":null,"time":null,"tickets":null,"format":null,"booking_id":null}}

User: "no wait, make it Saturday instead"
{{"intent":"Deny","movie":null,"date":"Saturday","time":null,"tickets":null,"format":null,"booking_id":null}}

User: "I was double charged on my card, I need a refund"
{{"intent":"Handoff","movie":null,"date":null,"time":null,"tickets":null,"format":null,"booking_id":null}}

User: "what's the capital of France"
{{"intent":"None","movie":null,"date":null,"time":null,"tickets":null,"format":null,"booking_id":null}}
"""


# --- type resolution helpers (Python's job, not LLM's) ---

def _resolve_date(raw: str) -> str | None:
    if not raw:
        return None
    t = raw.lower().strip()
    if t in ("today", "tonight"):
        return TODAY.isoformat()
    if t == "tomorrow":
        return (TODAY + timedelta(days=1)).isoformat()
    day_map = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
               "friday": 4, "saturday": 5, "sunday": 6}
    for day_name, wd in day_map.items():
        if day_name in t:
            delta = (wd - TODAY.weekday()) % 7
            if delta == 0:
                delta = 7
            if "next" in t:
                delta += 7
            return (TODAY + timedelta(days=delta)).isoformat()
    if re.match(r"\d{4}-\d{2}-\d{2}", raw):
        return raw
    return None


def _resolve_time(raw: str) -> str | None:
    if not raw:
        return None
    t = raw.lower().strip()
    if "matinee" in t:
        return "14:00"
    if "morning" in t:
        return "10:00"
    if "afternoon" in t:
        return "15:00"
    if "evening" in t or "tonight" in t:
        return "19:00"
    if m := re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", t):
        return f"{int(m.group(1)):02d}:{m.group(2)}"
    if m := re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", t):
        h, mi, period = int(m.group(1)), int(m.group(2) or 0), m.group(3)
        if period == "pm" and h != 12:
            h += 12
        if period == "am" and h == 12:
            h = 0
        return f"{h:02d}:{mi:02d}"
    return None


def _resolve_tickets(raw) -> int | None:
    if raw is None:
        return None
    t = str(raw).lower().strip()
    if m := re.match(r"^(\d+)$", t):
        return int(m.group(1))
    word_map = {
        "me and my friend": 2, "my friend and i": 2, "my friend and me": 2,
        "both of us": 2, "the two of us": 2,
        "one": 1, "a ticket": 1, "a seat": 1,
        "two": 2, "a pair": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    }
    for phrase, num in sorted(word_map.items(), key=lambda x: -len(x[0])):
        if phrase in t:
            return num
    return None


def _resolve_movie(raw: str) -> str | None:
    if not raw:
        return None
    return MOVIE_SYNONYM_MAP.get(raw.lower().strip())


def _resolve_format(raw: str) -> str | None:
    if not raw:
        return None
    return FORMAT_SYNONYM_MAP.get(raw.lower().strip())


def _resolve_booking_id(raw: str) -> str | None:
    if not raw:
        return None
    raw = raw.upper().strip()
    return raw if re.match(r"^CB-\d{4}$", raw) else None


VALID_INTENTS = {
    "BookTickets", "CheckShowtimes", "CancelBooking",
    "Greeting", "Help", "Cancel", "Confirm", "Deny", "Handoff", "None",
}


def validate(data: dict) -> dict:
    """Normalize raw LLM output: resolve types, check catalog, drop unknown keys."""
    out = {}
    out["intent"] = data.get("intent") if data.get("intent") in VALID_INTENTS else "None"
    out["movie"] = _resolve_movie(data.get("movie"))
    out["date"] = _resolve_date(data.get("date"))
    out["time"] = _resolve_time(data.get("time"))
    out["tickets"] = _resolve_tickets(data.get("tickets"))
    out["format"] = _resolve_format(data.get("format"))
    out["booking_id"] = _resolve_booking_id(data.get("booking_id"))
    return out


def extract_slots_llm(text: str, history: list[dict]) -> dict:
    # trim to last 10 turns so the system prompt is never squeezed out (A6)
    trimmed = history[-10:]
    messages = [{"role": "system", "content": EXTRACTION_PROMPT}] + trimmed + \
               [{"role": "user", "content": text}]
    resp = client.chat.completions.create(
        model=MODEL,
        temperature=0,  # deterministic output for evaluation consistency
        response_format={"type": "json_object"},
        messages=messages,
    )
    raw = json.loads(resp.choices[0].message.content)
    result = validate(raw)
    result["_tokens"] = {
        "prompt": resp.usage.prompt_tokens,
        "completion": resp.usage.completion_tokens,
    }
    return result


def extract_slots_regex(text: str) -> dict:
    """Fallback when the API is down — basic keyword + regex, never crashes (A4)."""
    t = text.lower()
    out = {"intent": "None", "movie": None, "date": None, "time": None,
           "tickets": None, "format": None, "booking_id": None}

    if any(k in t for k in ["never mind", "forget it", "start over", "abort"]):
        out["intent"] = "Cancel"
    elif any(k in t for k in ["yes", "yeah", "confirm", "book it", "go ahead"]):
        out["intent"] = "Confirm"
    elif any(k in t for k in ["no", "nope", "don't", "dont"]):
        out["intent"] = "Deny"
    elif any(k in t for k in ["refund", "double charged", "billing", "wheelchair", "private event"]):
        out["intent"] = "Handoff"
    elif any(k in t for k in ["hi", "hello", "hey", "good morning", "good evening"]):
        out["intent"] = "Greeting"
    elif any(k in t for k in ["help", "what can you"]):
        out["intent"] = "Help"
    elif re.search(r"\bcb-\d{4}\b", t) and "cancel" in t:
        out["intent"] = "CancelBooking"
    elif any(k in t for k in ["showing", "showtimes", "playing", "when is", "what times", "what's on"]):
        out["intent"] = "CheckShowtimes"
    elif any(k in t for k in ["book", "reserve", "ticket", "seat", "get me"]):
        out["intent"] = "BookTickets"

    for title_lower, canonical in MOVIE_SYNONYM_MAP.items():
        if title_lower in t:
            out["movie"] = canonical
            break

    for token in ["today", "tonight", "tomorrow", "monday", "tuesday", "wednesday",
                  "thursday", "friday", "saturday", "sunday"]:
        if token in t:
            out["date"] = _resolve_date(token)
            break
    if m := re.search(r"\d{4}-\d{2}-\d{2}", t):
        out["date"] = m.group(0)

    if m := re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", t):
        out["time"] = _resolve_time(m.group(0))
    elif m := re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", t):
        out["time"] = _resolve_time(m.group(0))

    out["tickets"] = _resolve_tickets(t)

    for syn, canonical in FORMAT_SYNONYM_MAP.items():
        if syn in t:
            out["format"] = canonical
            break

    if m := re.search(r"\bCB-\d{4}\b", text, re.IGNORECASE):
        out["booking_id"] = m.group(0).upper()

    return out


def extract(text: str, history: list[dict]) -> tuple[dict, str]:
    """Returns (slots_dict, source) where source is 'LLM' or 'regex'."""
    if client:
        try:
            return extract_slots_llm(text, history), "LLM"
        except Exception:
            pass
    return extract_slots_regex(text), "regex"
