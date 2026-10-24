# CineBot

This is a cinema ticket assistant. We built it as midterm for STAT 5350. It is a Track A (LLM hybrid) via Streamlit and gpt-4o-mini. LLM handles slot extraction, Python manages state and catalog validation.

## Setup

```bash
# create an isolated environment for this project
python3 -m venv .venv
source .venv/bin/activate

# install the application, voice, and evaluation dependencies
python -m pip install --upgrade pip
python -m pip install -r 5350-chatbot/requirements.txt

# copy the sample environment file and add your key
cp 5350-chatbot/.env.sample .env
# edit .env and set OPENAI_API_KEY=sk-...
```

The commands above create `.venv/` inside this project; no shared or
personal virtual environment is required. On Windows, activate it with:

```powershell
.\.venv\Scripts\Activate.ps1
```

The `.env` file must be in the `midterm/` directory (next to `app.py`).

## Run the bot

```bash
python -m streamlit run app.py
```

Opens at http://localhost:8501. The sidebar shows intent, slots, and dialog state for each turn.

## Run evaluation

```bash
# validation set (tune prompts/synonyms from these results)
python -m eval.evaluate --csv eval/validation.csv --out eval/results

# test set — run once only at the end
python -m eval.evaluate --csv eval/test.csv --runs 3 --out eval/results
```

Results print to stdout. `eval/results/confusion_matrix.png` is saved when sklearn is available.

## Dependencies

The setup installs the following packages:

- `openai` — OpenAI API client for extraction and tools
- `streamlit` — web application UI
- `python-dotenv` — loads `OPENAI_API_KEY` from `.env`
- `streamlit-mic-recorder` — manual start and stop voice input
- `pytest` and `hypothesis` — test dependencies from the course bundle
- `scikit-learn` and `matplotlib` — evaluation metrics and confusion matrix

The core, voice, test, and evaluation packages are declared in
`requirements.txt`.
The microphone package must be installed in the same environment used to
start Streamlit. Verify it with:

```bash
python -c "import streamlit_mic_recorder; print(streamlit_mic_recorder.__file__)"
```

## Project structure

```
midterm/
├── app.py          main Streamlit app
├── extraction.py   LLM call, regex fallback, validate()
├── dialog.py       slot state, confirmation, routing
├── catalog.json    movies, showtimes, formats, prices
├── eval/
│   ├── validation.csv
│   ├── test.csv
│   ├── evaluate.py
│   └── results/    confusion matrix and printed output
├── redteam.md      8 adversarial test cases
├── DESIGN.md       checkpoint document
└── REPORT.md       final report
```
