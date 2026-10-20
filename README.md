# README.md — CineBot

CineBot is a cinema ticket assistant built for STAT 5350/4350 midterm using Track A (LLM hybrid). It runs on Streamlit with gpt-4o-mini handling slot extraction, while Python manages state and catalog validation.

## Setup

```bash
# activate the shared venv from the project root
source ../../university/bin/activate

# copy the sample env and add your key
cp 5350-chatbot/.env.sample .env
# edit .env and set OPENAI_API_KEY=sk-...
```

The `.env` file must be in the `midterm/` directory (next to `app.py`).

## Run the bot

```bash
streamlit run app.py
```

Opens at http://localhost:8501. The sidebar shows intent, slots, and dialog state for each turn.

## Run evaluation

```bash
# validation set (tune prompts/synonyms from these results)
python eval/evaluate.py --csv eval/validation.csv --out eval/results

# test set — run once only at the end
python eval/evaluate.py --csv eval/test.csv --runs 3 --out eval/results
```

Results print to stdout. `eval/results/confusion_matrix.png` is saved when sklearn is available.

## Dependencies

All dependencies come from `5350-chatbot/requirements.txt`. If sklearn and matplotlib are not installed:

```bash
pip install scikit-learn matplotlib
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
