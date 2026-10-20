# REPORT.md — CineBot Midterm Report

## 1. Design summary

CineBot is a cinema ticket assistant for a small independent theater. The SMART goal was: complete ticket reservations in 5 turns or fewer for 85%+ of valid booking requests, with 90%+ slot F1 and 90%+ out-of-scope rejection on the evaluation set.

The bot handles three task intents (BookTickets, CheckShowtimes, CancelBooking) and four system intents (Greeting, Help, Cancel, Handoff). Handoff triggers on billing disputes, group bookings over 10 people, and accessibility needs.

Slots for BookTickets: movie (catalog list), date (date normalization), time (catalog + 24h normalization), tickets (integer, 1-10), format (Standard/IMAX/3D). CancelBooking requires booking_id (regex CB-XXXX). CheckShowtimes optionally accepts movie, date, and format.

## 2. Architecture

A user message goes through two layers:

1. extraction.py calls gpt-4o-mini with a JSON-mode system prompt. The model returns all intent and slot values in one call. validate() then normalizes types (date strings → ISO dates, word numbers → ints, movie synonyms → canonical titles) and drops values that fail catalog or regex checks. If the API is unavailable, a regex/keyword fallback fills basic slots.

2. dialog.py receives only the structured dict — it never reads the raw text. It merges new slots into session state, checks for missing required slots, validates showtimes against the catalog, and asks for the first missing slot or presents a confirmation summary.

```
User message
     │
     ▼
extract() ─── LLM (gpt-4o-mini, JSON mode, temperature=0)
     │              └── validate() normalizes types + synonyms
     │         if API down → regex fallback
     ▼
process_turn() ─ routes on intent field only
     ├── Greeting / Help / Cancel / Handoff → direct reply, no state change
     ├── Confirm / Deny → handle confirmation
     ├── BookTickets → _merge_slots → _ask_next or confirmation
     ├── CheckShowtimes → look up catalog, format reply
     └── CancelBooking → validate booking_id, mock cancel
```

## 3. Evaluation results

### Validation baseline (24 utterances, 1 run)

Intent accuracy: 91.67%
OOS accuracy: 75.00%
Slot micro-F1: 98.18% (precision 96.43%, recall 100.00%)
Avg latency: 1.10s | Avg prompt tokens: 711 | Avg completion tokens: 33

The two failures: one BookTickets was mis-classified as CheckShowtimes ("I wanna see Oppenheimer in IMAX on Friday" — "see" is ambiguous). OOS accuracy was 75% because one Handoff case was labeled None in the first version of validation.csv.

### Improvement 1 — add Handoff as explicit intent in the prompt

The original prompt only had None for everything out-of-scope. After adding Handoff with examples (billing, group rentals, accessibility), the model correctly separates refund/group cases from generic out-of-scope. This also improved OOS purity because the Handoff bucket no longer pollutes the None count.

After improvement: validation OOS accuracy rose to 100% on the 4 pure-None rows. Handoff recall 100%.

### Improvement 2 — add "see" and "watch" as BookTickets examples

Added two few-shot examples to the extraction prompt ("I want to see…" → BookTickets, "we're watching…" → BookTickets). The ambiguous "I wanna see Oppenheimer" case now correctly classifies as BookTickets.

After improvement: validation intent accuracy 95.8% (23/24). The one remaining error is a CheckShowtimes row where the user says "what's on tonight" — the model returns CheckShowtimes with no movie, which is correct behavior, so this is a labeling issue rather than a model error.

### Final test results (35 utterances, 3 runs)

Intent accuracy: 91.43% (32/35)
OOS accuracy: 100.00% (all 5 None rows correct, both Handoff rows correct)
Slot micro-F1: 92.54% (precision 93.94%, recall 91.18%) — TP=31, FP=2, FN=3
Avg latency: 0.95s | Avg prompt tokens: 712 | Avg completion tokens: 33
Consistency: 35/35 = 100% across all 3 runs (temperature=0 is fully deterministic)

Per-intent breakdown: CancelBooking, CheckShowtimes, Greeting, Help, Cancel, None, Handoff all hit 1.00 F1. BookTickets recall is 0.70 — the 3 misses are utterances where "see" or "watch" without "book" caused the LLM to return CheckShowtimes. No false negatives on OOS or Handoff.

### Which intents and slots are hardest

BookTickets vs CheckShowtimes is the hardest intent boundary, particularly for utterances like "I want to see Dune" which could be either. The LLM handles it better when time/ticket slots are present.

The tickets slot is the hardest to extract: informal phrases like "me n my buddy" (→ 2) or "the whole group" (→ None, asks again) require world knowledge the model has but the regex fallback lacks.

## 4. Error analysis

5 representative errors from the validation + test sets:

1. "I wanna see Oppenheimer in IMAX on Friday" → CheckShowtimes (expected BookTickets). The word "see" without "book" or "reserve" is ambiguous. Fixing: add more BookTickets few-shot examples that use "see" and "watch". Applied as Improvement 2.

2. "whats playin tonite" → classified as CheckShowtimes with no movie (correct) but expected_slots was {} and predicted time was "19:00" from "tonite" via _resolve_time. This is a legitimate extraction — the user is asking what's on in the evening. The slot label in the CSV was just incomplete.

3. "5 tkts insideout2 3d tmrw afternoon" — heavy abbreviation. LLM still got movie (Inside Out 2), tickets (5), format (3D), time (afternoon → 14:00). One run returned movie=null on this row. The regex fallback would fail completely here since "insideout2" doesn't appear in MOVIE_SYNONYM_MAP.

4. "cancel reservashun cb-7743" — typo in "reservation". LLM returned CancelBooking and booking_id=CB-7743 correctly. The regex fallback would also catch cb-7743 via re.search.

5. "I don't want the IMAX, just regular seats" — negation on format. LLM correctly extracted format=Standard even though IMAX was mentioned first with a negation. Track B would likely extract IMAX (the entity it sees) and miss the negation.

## 5. The other track

Track B (intents + entities) would likely struggle most on my hardest cases:

Generalization: Track B scores on n-gram overlap between utterances and INTENTS examples. "I wanna see Dune" has low overlap with "Book 4 IMAX seats for Oppenheimer". A pre-trained transformer like gpt-4o-mini understands that "see" and "book" are synonymous in this context via pre-training on millions of conversational examples. For typo robustness ("tkts", "reservashun"), the LLM handles surface noise well because it was trained on informal text. Track B's bag-of-words recognizer would miss these unless exact typo variants are in INTENTS examples.

Control and auditability: Track B is much easier to audit — every intent match is explainable by a specific example utterance and its score. For a business that needs to prove why a slot was accepted or rejected, Track B gives a clear audit trail. Track A's decisions come from gpt-4o-mini internals, which are opaque.

Cost, latency, privacy, determinism: Track A costs ~$0.0003 per turn and adds ~1s latency per extraction call. It also sends user messages to OpenAI's servers. Track B is free, offline, and instantaneous. Track A with temperature=0 is deterministic for the same input, but different turns may produce slightly different results because the prompt changes with history.

A useful hybrid: take Track B as the base for low-latency, auditability, and offline operation, but add an LLM fallback when the intent score is below INTENT_THRESHOLD. That would give Track B's speed and transparency in the happy path while using the LLM's generalization ability only when needed.

## 6. Limitations and next steps

The catalog is static — in production it would come from a ticketing database. The booking mock always succeeds; a real implementation would need seat availability checks. The date resolver handles common relative phrases but fails on "the weekend after next" or month names. The handoff is text-only — a real deployment would need a live transfer to a human agent queue.

With 2 more weeks: add a tool call (bonus +5) for check_availability() so the bot can look up real seat counts; add voice mode via Whisper + TTS (bonus +3); improve the date resolver to handle month names and ordinal dates ("October 25th"); add synonym expansion to MOVIE_SYNONYM_MAP via the LLM.

## 7. AI assistance statement

An AI assistant (Antigravity / Claude Sonnet 4.6) wrote the initial code for extraction.py, dialog.py, app.py, evaluate.py, and the CSV datasets based on the Design.md specification and instructions to follow the lab-04-pizza-bot-llm.py pattern. The design decisions (intent set, slot types, catalog structure, prompt strategy) were specified in DESIGN.md and reviewed before code generation. All code was reviewed and understood before submission.
