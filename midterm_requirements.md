STAT 5350/4350 Midterm Project: Build and Evaluate a Task-Oriented Chatbot
Weight: [X]% of the course grade · Points: 100 (+10 bonus) Design checkpoint due: [date, about 1 week before the final due date] Final due: [date and time] · Work: individual [or pairs: choose one]

1. Overview
You've now built chatbots two different ways:

Track A: LLM hybrid	Track B: intents and entities
Starting code	This repo (5350-chatbot), Labs 3–5	iportilla/azure-chatbotLinks to an external site., simple-chatbot/
How it understands the user	An LLM (gpt-4o-mini) extracts intent and details as JSON	A recognizer scores the message against example utterances and extracts list and regex entities
How it decides what to do	Your code: validation, slot filling, confirmation	Your code: intent handlers, slot filling in conversation state
UI	Streamlit (localhost:8501)	Microsoft 365 Agents Playground (localhost:3978)
Needs	OpenAI API key, which costs a few cents	Python 3.10+ and Node.js. Runs offline and free
Closest lab	Lab 4 Part B (hybrid PizzaBot) + Lab 3 (persona)	simple-chatbot/LAB.md Parts 1–5
For the midterm you'll build a task-oriented chatbot for a domain of your choice using ONE track, then evaluate it like a machine learning model on data it has never seen. Both tracks use the same evaluation (Section 5), so their results can be compared. The final report asks you to argue what the other approach would have done better or worse.

The core question of this project: How well does my bot understand sentences it was never designed for, and what does that tell me about rule-based versus learned language understanding?
2. Choose your domain
Pick a real, narrow task a business might automate. For example:

🎬 Cinema tickets (movie, showtime, seats)

🏋️ Gym class booking (class, day, time, membership ID)

🚗 Car service appointments (service type, vehicle, date)

📚 Library help (renew, reserve, hours)

🩺 Clinic front desk scheduling only. No medical advice: route those questions to a human.

🎓 Course registration help (course, section, term)

Not allowed: pizza, flowers, travel/flights or math. Those are the worked examples and solutions already in the repos.

Use resources/Planning_Your_First_Chatbot.md to plan.

3. Design checkpoint (10 points, due 10/23/26)
Submit a 1–2 page DESIGN.md. You'll get feedback before you build.

Business goal and one SMART goal. For example: "Book a gym class in 4 turns or fewer for 90% of booking requests."

Scope. What the bot does, what it does not do, and when a human takes over.

Intents. At least 3 task intents (plus Greeting, Help, Cancel and None or out-of-scope). For each intent, give 4 or more example utterances.

Slots and entities. At least 4 slots in total. For each: its type (list, regex, free text, date…), allowed values and synonyms, and whether it's required.

At least one slot must be validated against a catalog (like menu.json in Lab 4).

At least one slot must need resolution or normalization, for example "next friday" → 2026-10-30, "two" → 2, "NYC" → New York.

Dialog flow. A diagram (Mermaid is fine) of the main task: slot filling, confirmation, and the fallback or handoff.

Track choice and why. Two or three sentences.

4. Build requirements (35 points)
4.1 Requirements for both tracks
Your bot must:

R1 Recognize your 3+ task intents and route each one to its own handler or flow.
R2 Fill required slots over multiple turns, asking for the first missing one.
R3 Fill several slots from one sentence when the user gives them together.
R4 Handle a correction: "actually, make it Tuesday" changes only that slot.
R5 Validate catalog slots. Reject or clarify values that aren't in the catalog.
R6 Confirm before completing the task ("…Shall I book it?"), and handle yes and no.
R7 Handle out-of-scope messages with a polite fallback, and hand off to a human for the cases in your scope definition.
R8 Support Cancel at any point, which clears the task in progress.
R9 Have a debug view that shows the recognized intent, confidence (if available) and slots. Track B: /debug. Track A: a sidebar panel, as in Lab 4.
R10 Keep secrets out of code and Git. Use .env only. Do not submit .env.
4.2 Track A: LLM hybrid (OpenAI + Streamlit)
Start from the pattern in labs/lab-04-pizza-bot/starter/app_pizza_bot_llm.py, but in your domain, with your own prompts and catalog. Don't copy solutions/.

A1 Structured extraction: one LLM call per turn returns JSON containing intent and all slots (response_format={"type": "json_object"}, temperature=0). The intent field is required so you can be evaluated the same way as Track B.
A2 Validation: a validate() function checks every field against your catalog (a .json file) and drops invalid values or unexpected keys.
A3 Code decides: completion and confirmation logic lives in Python, not in the prompt.
A4 Fallback: if the API call fails or returns invalid JSON, a regex or keyword fallback still fills basic slots, and the bot doesn't crash.
A5 Persona and scope: a system prompt with identity, goal, rules and format, plus at least one few-shot example (Lab 3).
A6 Memory control: the chat history is trimmed (Lab 2), and the system prompt is never trimmed.
4.3 Track B: intents and entities (Microsoft 365 Agents SDK)
Copy simple-chatbot/ from azure-chatbot into your own folder and follow the LAB.md patterns in your domain. Remove the travel intents (BookFlight, GetWeather) and their handlers and tests.

B1 Intents: 3+ task intents in INTENTS, each with 8 or more varied example utterances that use @entity placeholders.
B2 Entities: at least one list entity with synonyms, one regex entity, and one entity with a role (e.g. from_date/to_date) or resolution (e.g. a date).
B3 Slot filling: handlers that save the task in progress in conversation state and ask follow-up questions (the on_book_flight pattern).
B4 Threshold: pick INTENT_THRESHOLD using your validation data (Section 5.2), not the test set, and justify the choice.
B5 Unit tests: tests/test_my_bot.py with 5 or more tests, run with python -m unittest.
5. Evaluation (25 points): the same for both tracks
Treat your bot's language understanding like a model: train → validate → test.

5.1 Build three data sets
Set	Size	Written by	Used for
Examples ("training")	Your prompts, few-shot examples or INTENTS	You	Building the bot
Validation	20+ utterances	You	Tuning prompts, synonyms, threshold
Test	30+ utterances	A classmate, who has seen only your DESIGN.md scope and not your examples	Final numbers only, run once at the end
The test set must include at least 6 out-of-scope sentences, at least 6 multi-slot sentences, at least 3 with typos or slang, and at least 2 negations ("I don't want…").

Store each set as a CSV, eval/validation.csv and eval/test.csv:

text,expected_intent,expected_slots
"two seats for Dune tonight at 7",BookTickets,"{""movie"": ""Dune"", ""seats"": 2, ""time"": ""19:00""}"
"what's the capital of France",None,"{}"
⚠️ Never copy test sentences into your prompts, few-shot examples or INTENTS. That measures memory, not understanding. Peeking at the test set while tuning gets an automatic −10 points on Section 5. Say honestly in your report how you kept the sets separate.
5.2 Write eval/evaluate.py
It reads a CSV, runs only the understanding step of your bot (Track A: your extraction plus validate(). Track B: recognize()), and reports:

Intent accuracy and macro-F1 across intents.

A confusion matrix of intents. Print it, or save it as an image.

Slot precision, recall and F1 (micro-averaged). A slot counts as correct only if its resolved value exactly matches the expected one.

Out-of-scope handling: of the out-of-scope sentences, the percentage correctly sent to None or the fallback.

Track A only:

Consistency: run the test set 3 times and report how often the 3 outputs agree.

Cost and latency: average prompt and completion tokens per turn, and average seconds per turn.

Track B only: a threshold sweep on the validation set, with INTENT_THRESHOLD from 0.2 to 0.8 in steps of 0.1. Plot accuracy and out-of-scope recall against the threshold.

You may use scikit-learn (classification_report, confusion_matrix) and matplotlib.

5.3 Improve, then test once
Run on validation and record the baseline.

Make at least two improvements, guided by validation errors only: prompt wording, more examples or synonyms, a better regex, the threshold, validation rules. Record validation scores after each change in a small table.

Run on test once, and report those numbers as your final results.

6. Robustness and red-teaming (10 points)
Write at least 8 adversarial inputs, run them, and record what happened in a table: input, expected behavior, actual behavior, pass or fail.

Include at least: a prompt injection ("ignore your instructions…"), an off-catalog request ("seats for a movie you don't show"), a mid-task topic switch ("wait, what are your hours?" while the bot is waiting for a slot), a negation, a very long message, and two slots in conflict ("Tuesday… no, Wednesday").

For each failure, explain why it happened, citing a specific line of code or prompt, and either fix it or explain what fixing it would take.

7. Report (20 points)
Write REPORT.md, 4–6 pages including tables and figures, with these sections:

Design summary: goal, scope, intents and slots (updated from your checkpoint).

Architecture: one diagram of how a message flows through your bot.

Evaluation results: validation baseline → improvements → final test results, with the confusion matrix and your tables. Which intents and slots are hardest, and why?

Error analysis: pick 5 test errors and explain each at the level of the mechanism. Track B: word overlap, a synonym list, the threshold. Track A: prompt ambiguity, JSON schema, validation, sampling.

The other track (key section, one page or more): using your test set as evidence, argue how the other approach would likely have done on your hardest cases. Address:

Generalization: bag-of-words scoring over example utterances versus a pre-trained transformer. Why might one handle paraphrase, typos or negation better?

Control and auditability: which design makes it easier to guarantee business rules?

Cost, latency, privacy and determinism.

What a hybrid would look like: for example, Track B with an LLM fallback for low-confidence messages, or Track A with a rule-based fast path.

Limitations and next steps: what you'd do with 2 more weeks.

AI assistance statement: which tools you used and for what (see Section 9).

8. Demo video and code quality
Demo (required, part of Functionality): a 3–5 minute screen recording that shows R1–R9: a happy path, a one-sentence multi-slot request, a correction, a validation rejection, confirmation, out-of-scope handling, cancel, and the debug view. Narrate briefly.

Code: readable and minimal, in the style of the starter code, with a README.md that says exactly how to run your bot and evaluate.py.

9. Rules
Starting code: you must start from the course repos. You may not copy files from 5350-chatbot/solutions/ or azure-chatbot/simple-chatbot-lab-solution/. Reading them to learn is fine; submitting their code is not.

AI assistants: allowed for explanations and debugging, as in the Student Guide. If an assistant writes code, say so in REPORT.md. You must be able to explain every line: you may be asked to walk through your code live for 10 minutes. AI-written code you can't explain gets no credit.

Keys and data: never commit or submit .env or API keys. A leaked key is an automatic −25% and must be rotated right away. Don't type real personal or medical data into the bot.

Cost (Track A): use gpt-4o-mini. A full evaluation run (3 passes of about 30 sentences) costs well under $1. Use a test set of reasonable size and don't loop the API.

10. What to submit
A private GitHub repo shared with [instructor GitHub username], or a zip on [LMS], with:

my-chatbot/
├── README.md            # how to run the bot, tests and evaluation
├── DESIGN.md            # checkpoint (updated)
├── REPORT.md            # Section 7
├── src/ … or app.py     # your bot
├── catalog.json         # Track A (or your entity lists, Track B)
├── tests/               # Track B: 5+ unit tests (Track A: optional bonus)
├── eval/
│   ├── validation.csv
│   ├── test.csv
│   ├── evaluate.py
│   └── results/         # printed outputs, confusion matrix, plots
├── redteam.md           # Section 6 table
└── demo.mp4             # or a link to the video
Before submitting, check:

git status doesn't show .env
A fresh clone runs by following your README
11. Grading rubric (100 points)
Area	Points	Exemplary	Proficient	Developing
Design checkpoint (§3)	10	Clear SMART goal, sharp scope, every required element, feedback acted on	All elements present	Vague scope or missing elements
Functionality (§4, demo)	35	All of R1–R10 and every track requirement work in the demo	1–2 requirements weak	Several missing, or crashes
Evaluation (§5)	25	Clean validation/test separation; all metrics; at least 2 improvements backed by evidence; correct metrics code	Minor gaps in metrics or process	Test leakage, missing metrics, or no improvement loop
Robustness (§6)	10	8+ cases, failures explained mechanistically, some fixed	8 cases, explanations shallow	Fewer cases, no analysis
Report and reflection (§7)	20	Specific, evidence-based error analysis; thoughtful comparison of the two tracks, grounded in test results	Correct but general	Generic, no evidence
Bonus (up to +10):

Bonus	Points
Track A: add a tool the agent calls (Lab 5 pattern), e.g. check_availability(), with a safe execute_tool() allow-list and max_iterations	+5
Track A: add a voice mode (Lab 6) and report its latency	+3
Track B: replace recognize() with Azure AI Language (CLU) trained on the same examples, and compare both on your test set	+10
Track B: deploy to Azure Bot Service (AZURE_README.md) and show it in Web Chat	+5
Either track: build a minimal version of the other track's understanding step and run it on the same test.csv	+10
Bonus is capped at +10 in total.

Deductions: leaked API key −25%; test-set leakage −10 on §5; late submission [policy].

12. Suggested timeline
Week	Milestone
1	Choose your domain and track; write and submit DESIGN.md; swap scope documents with a classmate and write each other's test sets
2	Build R1–R6 and the track requirements; write validation.csv
3	evaluate.py; validation baseline → improvements; red-team; final test run; report and demo
Getting help: run python run.py check (Track A) or check that python3 --version shows 3.10+ (Track B) before asking. Post the command, the step and the error in the forum, never your key.