# evaluate.py — runs extraction on a CSV and prints intent + slot metrics
# Usage: python eval/evaluate.py --csv eval/validation.csv
#        python eval/evaluate.py --csv eval/test.csv --runs 3
import argparse
import ast
import csv
import json
import sys
import time
from pathlib import Path

# add project root to path so we can import extraction
sys.path.insert(0, str(Path(__file__).parent.parent))
from extraction import extract, validate  # noqa: E402

try:
    import matplotlib.pyplot as plt
    from sklearn.metrics import (classification_report, confusion_matrix,
                                 ConfusionMatrixDisplay, f1_score)
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False
    print("sklearn/matplotlib not installed — skipping matrix plot")


def load_csv(path: str) -> list[dict]:
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # strip outer quotes that some editors add to the text field
            text = row["text"].strip().strip('"')
            intent = row["expected_intent"].strip()
            try:
                slots = ast.literal_eval(row["expected_slots"].strip())
            except Exception:
                slots = {}
            rows.append({"text": text, "intent": intent, "slots": slots})
    return rows


def run_once(rows: list[dict]) -> tuple[list, list, list[dict], float, dict]:
    """Run extraction on every row. Returns (y_true, y_pred, slot_results, avg_latency, token_totals)."""
    y_true, y_pred, slot_results = [], [], []
    total_prompt, total_completion, total_latency = 0, 0, 0.0

    for row in rows:
        t0 = time.time()
        slots, source = extract(row["text"], [])
        latency = time.time() - t0
        total_latency += latency

        y_true.append(row["intent"])
        y_pred.append(slots["intent"])

        toks = slots.get("_tokens", {})
        total_prompt += toks.get("prompt", 0)
        total_completion += toks.get("completion", 0)

        # slot matching — compare resolved predicted values against expected
        expected = row["slots"]
        slot_names = set(expected) | {
            name for name in slots
            if not name.startswith("_") and name != "intent"
        }
        for slot_name in slot_names:
            exp_val = expected.get(slot_name)
            pred_val = slots.get(slot_name)
            slot_results.append({
                "slot": slot_name,
                "expected": exp_val,
                "predicted": pred_val,
                "match": pred_val == exp_val,
            })

    n = len(rows)
    token_totals = {
        "avg_prompt": total_prompt / n,
        "avg_completion": total_completion / n,
    }
    return y_true, y_pred, slot_results, total_latency / n, token_totals


def slot_f1(slot_results: list[dict]) -> dict:
    tp = sum(1 for r in slot_results if r["match"] and r["expected"] is not None)
    fp = sum(
        1 for r in slot_results
        if not r["match"] and r["predicted"] is not None
    )
    fn = sum(
        1 for r in slot_results
        if not r["match"] and r["expected"] is not None
    )
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"precision": precision, "recall": recall, "f1": f1, "tp": tp, "fp": fp, "fn": fn}


def oos_accuracy(y_true: list, y_pred: list) -> float:
    # Handoff is an in-scope escalation intent, not an out-of-scope response.
    oos_intents = {"None"}
    oos_idx = [i for i, y in enumerate(y_true) if y in oos_intents]
    if not oos_idx:
        return float("nan")
    correct = sum(1 for i in oos_idx if y_pred[i] in oos_intents)
    return correct / len(oos_idx)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, help="path to validation.csv or test.csv")
    parser.add_argument("--runs", type=int, default=1,
                        help="run the test set N times to measure consistency (Track A)")
    parser.add_argument("--out", default=None, help="directory for saved plots")
    args = parser.parse_args()

    rows = load_csv(args.csv)
    print(f"\nLoaded {len(rows)} rows from {args.csv}\n")

    all_preds = []
    for run_i in range(args.runs):
        print(f"--- Run {run_i + 1}/{args.runs} ---")
        y_true, y_pred, slot_results, avg_lat, tokens = run_once(rows)
        all_preds.append(y_pred)

        accuracy = sum(t == p for t, p in zip(y_true, y_pred)) / len(y_true)
        print(f"Intent accuracy: {accuracy:.2%}")
        print(f"OOS accuracy:    {oos_accuracy(y_true, y_pred):.2%}")
        print(f"Avg latency:     {avg_lat:.2f}s")
        print(f"Avg tokens:      prompt={tokens['avg_prompt']:.0f}, "
              f"completion={tokens['avg_completion']:.0f}")

        if HAS_SKLEARN:
            labels = sorted(set(y_true + y_pred))
            macro_f1 = f1_score(
                y_true, y_pred, labels=labels, average="macro", zero_division=0
            )
            print("\nClassification report:")
            print(classification_report(y_true, y_pred, labels=labels, zero_division=0))
            print(f"Intent macro-F1:  {macro_f1:.2%}")

        sf = slot_f1(slot_results)
        print(f"Slot micro-F1:   {sf['f1']:.2%}  "
              f"(precision={sf['precision']:.2%}, recall={sf['recall']:.2%})")
        print(f"  TP={sf['tp']}, FP={sf['fp']}, FN={sf['fn']}\n")

    # consistency across runs
    if args.runs > 1 and all_preds:
        agreements = sum(
            len(set(all_preds[r][i] for r in range(args.runs))) == 1
            for i in range(len(rows))
        )
        print(f"Consistency ({args.runs} runs): {agreements}/{len(rows)} "
              f"= {agreements/len(rows):.2%} rows fully agreed\n")

    # confusion matrix plot
    if HAS_SKLEARN and args.out:
        out_dir = Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        cm = confusion_matrix(y_true, all_preds[-1], labels=sorted(set(y_true + all_preds[-1])))
        disp = ConfusionMatrixDisplay(
            confusion_matrix=cm,
            display_labels=sorted(set(y_true + all_preds[-1]))
        )
        fig, ax = plt.subplots(figsize=(9, 7))
        disp.plot(ax=ax, xticks_rotation=45)
        ax.set_title("Intent confusion matrix")
        plt.tight_layout()
        path = out_dir / "confusion_matrix.png"
        fig.savefig(path, dpi=150)
        print(f"Confusion matrix saved to {path}")


if __name__ == "__main__":
    main()
