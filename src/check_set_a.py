"""Was the modern corpus working all along, hidden inside an average?

WHY THIS RUNS

The six-way comparison reported totals over all 233 questions and we read
those totals. Split by question set, they were disagreeing:

                              set A      set B     all 233
    classic corpus + prompt    90/100     80/133     170
    modern  corpus + prompt    97/100     77/133     174

Set A said +7. Set B said -3. We reported +4, called it not significant, and
moved on - averaging over a disagreement instead of looking at it.

The two sets are not equally trustworthy on this question:

    Set A   100 questions. The answer key is the question's own chapter PLUS
            200 verses from other chapters, each read and judged correct by
            hand. A method cannot score well here just by finding the right
            chapter.

    Set B   133 questions, one per chapter. The answer key is that one
            chapter and nothing else. Any method that leans on chapter-level
            matching is rewarded by the way this set was built, whether or
            not retrieval actually improved.

So Set A is the honest half for anything chapter-shaped, and it is the half
we should have looked at.

WHAT THIS MEASURES

Only the two rows that matter, and it saves the per-question results this
time so no follow-up question needs another hour.

    1. classic corpus, classic prompt   what ships today
    2. modern  corpus, classic prompt   scored highest of the six

McNemar's exact test on Set A alone, on Set B alone, and on all 233.

READ THE CEILING BEFORE READING THE RESULT

If row 1 is at 90 of 100, there are 10 questions left to win on Set A. If row
2 is at 97, there are 3. A set that small cannot measure a small improvement,
and every future change we test on it will come back "not established"
regardless of whether it worked. That is a fact about our test set, not about
the change - and it is the more important thing this script reports.

Run it:

    venv/bin/python -u src/check_set_a.py
"""

import json
from pathlib import Path

from sentence_transformers import SentenceTransformer

from benchmark_chapters import load_questions, mcnemar_exact
from measure_modern_stack import score_combination
from pipeline import EMBEDDING_MODEL_NAME
from rerank import RERANKER_MODEL_NAME, Reranker

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_PATH = PROJECT_ROOT / "data" / "set_a_check_results.json"

ROWS = [
    ("classic corpus", "classic", "hyde_rewrites_sarvam.json"),
    ("modern corpus", "modern", "hyde_rewrites_sarvam.json"),
]


def main():
    kurals = json.load(open(PROJECT_ROOT / "data" / "kurals.json",
                            encoding="utf-8"))
    set_a, set_b = load_questions()
    all_questions = set_a + set_b
    split = len(set_a)

    print("loading the models...")
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    reranker = Reranker(RERANKER_MODEL_NAME)

    results = {}
    for label, corpus_mode, rewrites_file in ROWS:
        with open(PROJECT_ROOT / "data" / rewrites_file,
                  encoding="utf-8") as open_file:
            rewrites = json.load(open_file)
        print(f"scoring {label}...")
        results[label] = score_combination(
            rewrites, all_questions, kurals, model, reranker, corpus_mode)

    with open(RESULTS_PATH, "w", encoding="utf-8") as open_file:
        json.dump({label: [bool(hit) for hit in hits]
                   for label, hits in results.items()}, open_file, indent=2)

    print()
    print("=" * 66)
    print("A 'hit' is a question where a correct verse reached the top 5.")
    print("=" * 66)
    print(f"{'corpus text':16s} {'Set A':>10s} {'Set B':>10s} {'all 233':>11s}")
    for label, _, _ in ROWS:
        hits = results[label]
        print(f"{label:16s} {int(hits[:split].sum()):>6d}/100 "
              f"{int(hits[split:].sum()):>6d}/133 "
              f"{int(hits.sum()):>7d}/233")

    before, after = ROWS[0][0], ROWS[1][0]
    print()
    print("IS THE DIFFERENCE REAL? (McNemar's exact test)")
    print("  It looks only at questions the two versions disagree on.")
    print("  p below 0.05 means a gap that lopsided is unlikely to be luck.")
    for name, lo, hi in (("Set A only (the honest key)", 0, split),
                         ("Set B only (one-chapter key)", split,
                          len(all_questions)),
                         ("all 233 together", 0, len(all_questions))):
        worse, better, p = mcnemar_exact(results[before][lo:hi],
                                         results[after][lo:hi])
        print()
        print(f"  {name}")
        print(f"    classic right, modern wrong : {worse}")
        print(f"    classic wrong, modern right : {better}")
        print(f"    p = {p:.4f}  -> "
              + ("REAL" if p < 0.05 else "NOT ESTABLISHED"))

    print()
    print("=" * 66)
    print("HOW MUCH ROOM IS LEFT ON SET A")
    best = max(int(results[label][:split].sum()) for label, _, _ in ROWS)
    print(f"  best score on Set A: {best} of 100")
    print(f"  questions still failing: {100 - best}")
    print()
    print("  Any future change can win at most that many questions here.")
    print("  When the room left is small, a real improvement and no")
    print("  improvement at all produce the same verdict - 'not established'.")
    print("  At that point the limit is the test set, not the pipeline, and")
    print("  the next useful work is writing more hand-checked questions.")


if __name__ == "__main__":
    main()
