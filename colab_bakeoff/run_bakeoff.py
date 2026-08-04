"""The Kural reranker bake-off, portable edition. One command, no setup.

    python run_bakeoff.py

Everything it needs travels with it in data/: the frozen 50-candidate piles
(computed once, on the home machine, so every arm everywhere reorders the
IDENTICAL piles), the verse texts, and the shipping reranker's results as
the baseline. This machine only runs the challenger model.

Progress is saved every few questions. If the session dies, run the same
command again and it continues where it stopped.

For a quick plumbing test without the big model:

    python run_bakeoff.py --model cross-encoder/ms-marco-MiniLM-L-6-v2 --limit 20
"""

import argparse

from bakeoff import config
from bakeoff.checkpointing import load_checkpoint
from bakeoff.loading import load_and_validate
from bakeoff.model import Reranker
from bakeoff.report import print_report, write_results
from bakeoff.scoring import score_arm


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=config.MODEL_NAME,
                        help="reranker to test (default: the big bge)")
    parser.add_argument("--limit", type=int, default=None,
                        help="score only the first N questions (smoke test)")
    arguments = parser.parse_args()

    piles, texts, baseline, set_a_size = load_and_validate()
    reranker = Reranker(arguments.model)
    checkpoint = load_checkpoint()

    question_count = (len(piles) if arguments.limit is None
                      else min(arguments.limit, len(piles)))
    reachable = sum(1 for entry in piles[:question_count]
                    if set(entry["pile"]) & set(entry["correct"]))

    results = {
        baseline["label"]: {
            "top5": baseline["top5"][:question_count],
            "rank1": baseline["rank1"][:question_count],
            "seconds": (baseline["ms_per_question"] * question_count / 1000),
        }
    }
    for label, text_field in config.ARMS:
        results[label] = score_arm(label, text_field, piles, texts,
                                   reranker, checkpoint,
                                   limit=arguments.limit)

    write_results(results)
    print_report(results, baseline["label"],
                 min(set_a_size, question_count), reachable)

    if arguments.limit is not None:
        print()
        print(f"NOTE: this was a smoke test over {question_count} questions. "
              "Delete data/checkpoint.json before the real run.")


if __name__ == "__main__":
    main()
