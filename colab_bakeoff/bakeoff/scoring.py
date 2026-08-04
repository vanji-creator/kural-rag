"""Run one arm: rerank every pile, checkpointing as it goes."""

import time

from . import config
from .checkpointing import save_checkpoint


def score_arm(label, text_field, piles, texts, reranker, checkpoint,
              limit=None):
    """Rerank every question's pile with this arm's text. Resumable.

    Returns {"top5": [...], "rank1": [...], "seconds": float} where top5[i]
    is True when a correct verse survived into the top 5 of question i, and
    rank1[i] is True when the very first verse was correct.
    """
    question_count = len(piles) if limit is None else min(limit, len(piles))

    saved = checkpoint.get(label, {"top5": [], "rank1": [], "seconds": 0.0})
    top5 = list(saved["top5"])
    rank1 = list(saved["rank1"])
    seconds = saved["seconds"]

    if len(top5) >= question_count:
        print(f"{label}: already complete ({len(top5)} questions)")
        return {"top5": top5[:question_count],
                "rank1": rank1[:question_count], "seconds": seconds}
    if top5:
        print(f"{label}: resuming from question {len(top5) + 1}")
    else:
        print(f"{label}: scoring {question_count} questions...")

    arm_started = time.perf_counter()
    resumed_at = len(top5)
    for index in range(resumed_at, question_count):
        entry = piles[index]
        verse_texts = [texts[str(number)][text_field]
                       for number in entry["pile"]]

        started_at = time.perf_counter()
        scores = reranker.score_pairs(entry["question"], verse_texts)
        seconds += time.perf_counter() - started_at

        # Highest score first. Ties broken by pile order, which is fixed,
        # so a rerun produces the identical ranking.
        order = sorted(range(len(scores)),
                       key=lambda position: -scores[position])
        best_numbers = [entry["pile"][position]
                        for position in order[:config.TOP_K]]

        correct = set(entry["correct"])
        top5.append(bool(correct.intersection(best_numbers)))
        rank1.append(best_numbers[0] in correct)

        finished = index + 1
        if finished % config.CHECKPOINT_EVERY == 0 or finished == question_count:
            checkpoint[label] = {"top5": top5, "rank1": rank1,
                                 "seconds": seconds}
            save_checkpoint(checkpoint)
            pace = (time.perf_counter() - arm_started) / (finished - resumed_at)
            remaining_minutes = (question_count - finished) * pace / 60
            print(f"  {finished}/{question_count}  saved  "
                  f"{pace:.1f}s per question  "
                  f"~{remaining_minutes:.0f} min left in this arm",
                  flush=True)

    return {"top5": top5, "rank1": rank1, "seconds": seconds}
