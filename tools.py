# tools.py — tool implementations and the safe execute_tool() allow-list
# Pattern from lab-05: model requests a tool call, Python executes it, result goes back to model.
import json
from pathlib import Path

CATALOG = json.loads((Path(__file__).parent / "catalog.json").read_text())

# build the same synonym map used in extraction.py so check_availability resolves nicknames
_SYNONYM_MAP: dict[str, str] = {}
for _m in CATALOG["movies"]:
    _SYNONYM_MAP[_m["title"].lower()] = _m["title"]
    for _s in _m["synonyms"]:
        _SYNONYM_MAP[_s.lower()] = _m["title"]

ALLOW_LIST = {"check_availability"}
MAX_ITERATIONS = 5


def check_availability(movie: str, fmt: str, date: str | None = None) -> dict:
    """Look up showtimes and price for a movie + format. Returns a dict the model can read."""
    canonical = _SYNONYM_MAP.get(movie.lower().strip())
    for m in CATALOG["movies"]:
        if m["title"] == canonical or m["title"].lower() == movie.lower().strip():
            if fmt not in m["showtimes"]:
                return {
                    "found": False,
                    "reason": f"{m['title']} is not available in {fmt}.",
                    "available_formats": m["formats"],
                }
            return {
                "found": True,
                "movie": m["title"],
                "format": fmt,
                "showtimes": m["showtimes"][fmt],
                "price_per_ticket": m["price"][fmt],
                "date": date or "any date",
            }
    return {
        "found": False,
        "reason": f"We don't currently show '{movie}'.",
        "available_titles": [m["title"] for m in CATALOG["movies"]],
    }


# OpenAI function schema for check_availability
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": (
                "Look up whether a movie is available in a given format and, "
                "if so, return its showtimes and ticket price. "
                "Call this whenever the user asks about availability or pricing."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "movie":  {"type": "string", "description": "Movie title as stated by the user"},
                    "fmt":    {"type": "string", "description": "Screening format: Standard, IMAX, or 3D"},
                    "date":   {"type": "string", "description": "ISO date YYYY-MM-DD or null"},
                },
                "required": ["movie", "fmt"],
            },
        },
    }
]


def execute_tool(tool_name: str, tool_input: dict) -> str:
    """Allow-listed dispatcher. Only names in ALLOW_LIST may run."""
    if tool_name not in ALLOW_LIST:
        return f"Tool '{tool_name}' is not permitted."
    if tool_name == "check_availability":
        result = check_availability(
            movie=tool_input.get("movie", ""),
            fmt=tool_input.get("fmt", "Standard"),
            date=tool_input.get("date"),
        )
        return json.dumps(result)
    return "Unknown tool."
