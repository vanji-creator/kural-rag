"""The numbers printed on the /method page come from here.

evaluate.py compares every method we ever tried, which takes minutes. This
scores ONLY the pipeline that ships, so the figures on the website can be
regenerated in about a minute and checked against what is published.

If a number on /method does not match this output, the website is wrong.

Run it:

    venv/bin/python src/report_metrics.py
"""

import json
import time
from pathlib import Path

import numpy as np

from evaluate import correct_kural_numbers_for, score_one_method
from pipeline import KuralRetriever

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GOLDEN_SET_PATH = PROJECT_ROOT / "data" / "golden_set.json"
CORPUS_PATH = PROJECT_ROOT / "data" / "kurals.json"


def main():
    kurals = json.load(open(CORPUS_PATH, encoding="utf-8"))
    golden_questions = json.load(open(GOLDEN_SET_PATH, encoding="utf-8"))

    retriever = KuralRetriever(use_reranker=True)

    all_scores = np.zeros((len(golden_questions), len(kurals)))
    total_seconds = 0.0
    for question_index, question_entry in enumerate(golden_questions):
        started_at = time.perf_counter()
        ranking_scores, _, _, _, _ = retriever.rank_everything(
            question_entry["question"])
        total_seconds += time.perf_counter() - started_at
        all_scores[question_index] = ranking_scores

    result = score_one_method(all_scores, kurals, golden_questions)
    question_count = len(golden_questions)

    print()
    print("=" * 62)
    print("  MEASURED — the pipeline that ships, on the golden set")
    print("=" * 62)
    print(f"  n (labelled questions)      {question_count}")
    print()
    print(f"  recall@5                    "
          f"{result['hits'] / question_count:.2f}"
          f"    ({result['hits']} of {question_count} questions had a")
    print(f"                                        correct verse in the top 5)")
    print(f"  precision@5                 "
          f"{result['avg_correct_in_top_k'] / 5:.2f}"
          f"    ({result['avg_correct_in_top_k']:.2f} of the 5 returned")
    print(f"                                        verses are correct, on average)")
    print(f"  MRR                         {result['mrr']:.2f}"
          f"    (1.00 would mean the very first")
    print(f"                                        result is always correct)")
    print(f"  median rank of first hit    {result['median_first_rank']}")
    print()
    print(f"  latency                     "
          f"{total_seconds / question_count * 1000:.0f} ms per question")
    print("=" * 62)
    print()
    print("  citation validity is NOT measurable yet - nothing generates")
    print("  answers, so there are no citations to check. Phase 7.")


if __name__ == "__main__":
    main()
