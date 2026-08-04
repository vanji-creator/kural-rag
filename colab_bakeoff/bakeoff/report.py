"""Turn raw hit/miss lists into the table and the verdicts."""

import json

from . import config
from .stats import mcnemar_exact


def write_results(results):
    """Save every arm's per-question results. This file goes home with you."""
    with open(config.RESULTS_PATH, "w", encoding="utf-8") as open_file:
        json.dump({label: {"top5": r["top5"], "rank1": r["rank1"],
                           "ms_per_question": (r["seconds"] * 1000
                                               / max(len(r["top5"]), 1))}
                   for label, r in results.items()}, open_file, indent=1)
    print(f"per-question results saved to {config.RESULTS_PATH}")


def print_report(results, baseline_label, set_a_size, reachable):
    print()
    print("=" * 78)
    print("'top 5' = a correct verse reached the five shown to a reader.")
    print("'rank 1' = the first verse shown was correct.")
    print("'ms' = reranking milliseconds per question on THIS machine.")
    print(f"Perfect reranking of these piles would score {reachable} "
          f"on top-5.")
    print("=" * 78)

    total = len(results[baseline_label]["top5"])
    print(f"{'arm':24s} {'Set A':>8s} {'Set B':>8s} {'all':>9s} "
          f"{'rank-1':>9s} {'ms':>8s}")
    for label, r in results.items():
        top5 = r["top5"]
        rank1 = r["rank1"]
        ms = r["seconds"] * 1000 / max(len(top5), 1)
        print(f"{label:24s} {sum(top5[:set_a_size]):>4d}/{set_a_size:<3d} "
              f"{sum(top5[set_a_size:]):>4d}/{total - set_a_size:<3d} "
              f"{sum(top5):>4d}/{total:<3d} "
              f"{sum(rank1):>4d}/{total:<3d} "
              f"{ms:>8.0f}")

    print()
    print(f"IS ANY DIFFERENCE REAL? (McNemar's exact test, against "
          f"{baseline_label!r})")
    print("  It looks only at questions the two arms disagree on.")
    print("  p below 0.05 means a gap that lopsided is unlikely to be luck.")
    for label, r in results.items():
        if label == baseline_label:
            continue
        for name, field in (("top-5", "top5"), ("rank-1", "rank1")):
            worse, better, p = mcnemar_exact(
                results[baseline_label][field], r[field])
            print()
            print(f"  {label} vs baseline, {name}")
            print(f"    baseline right, this wrong : {worse}")
            print(f"    baseline wrong, this right : {better}")
            print(f"    p = {p:.4f}  -> "
                  + ("REAL" if p < 0.05 else "NOT ESTABLISHED"))
