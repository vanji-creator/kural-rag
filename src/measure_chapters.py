"""Do hand-written chapter descriptions beat the glued stand-in?

Four rows, one change at a time. Everything else in the pipeline is held
fixed - only the text used to describe a chapter changes.

    glued          the chapter's 10 English explanations concatenated.
                   Not a description; the chapter's own text repeated.
                   THIS IS THE BASELINE. It already earns +3 points.
    topic          the hand-written 2-3 sentence summary.
    topic+words    plus the modern vocabulary bridge (sloth -> lazy).
    all            plus questions the chapter answers.

READ THE LAST ROW WITH SUSPICION. Those questions were written by an author
who had already seen the 100 golden questions in conversation. 121 verbatim
copies were found and removed, but paraphrase leakage cannot be removed. The
"all" row is an optimistic ceiling, not a result to publish.

The rows that CAN be trusted are glued, topic and topic+words - those were
written from each chapter's 10 verses.

Run it:

    venv/bin/python src/measure_chapters.py
"""

import json
import sys
import time
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

from evaluate import correct_kural_numbers_for, normalise_each_row
from keyword_search import BM25Index
from pipeline import (CHAPTER_BLEND_WEIGHT, EMBEDDING_MODEL_NAME,
                      KEYWORD_WEIGHT, KURALS_PER_CHAPTER,
                      RERANK_CANDIDATE_COUNT, build_chapter_descriptions,
                      searchable_text)
from rerank import RERANKER_MODEL_NAME, Reranker, rerankable_text
from rewrite_query import rewrite

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TOP_K = 5

MODES = ["glued", "topic", "topic+words", "all"]

# Set by --significance: run only these two and test whether the gap is real.
SIGNIFICANCE_MODES = ["glued", "topic+words"]


def mcnemar_exact(hits_a, hits_b):
    """Is the difference between two methods real, or could it be noise?

    The right test when the SAME 100 questions are run two ways. It ignores
    every question both methods agree on and looks only where they disagree:

        only_a  = A got it right and B got it wrong
        only_b  = A got it wrong and B got it right

    If a change were doing nothing, those two counts would be about equal.
    A lopsided split is the signal. Returns the two counts and a p-value -
    below 0.05 means the gap is unlikely to be luck.
    """
    from math import comb
    only_a = int(np.sum(hits_a & ~hits_b))
    only_b = int(np.sum(~hits_a & hits_b))
    disagreements = only_a + only_b
    if disagreements == 0:
        return only_a, only_b, 1.0
    smaller = min(only_a, only_b)
    p_value = 2 * sum(comb(disagreements, i)
                      for i in range(smaller + 1)) / 2 ** disagreements
    return only_a, only_b, min(p_value, 1.0)


def main():
    kurals = json.load(open(PROJECT_ROOT / "data" / "kurals.json",
                            encoding="utf-8"))
    golden = json.load(open(PROJECT_ROOT / "data" / "golden_set.json",
                            encoding="utf-8"))

    model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    reranker = Reranker(RERANKER_MODEL_NAME)

    kural_texts = [searchable_text(record) for record in kurals]
    kural_vectors = model.encode(kural_texts, show_progress_bar=False)
    keyword_index = BM25Index(kural_texts)

    rewritten = [rewrite(entry["question"]) for entry in golden]
    question_vectors = model.encode(rewritten, show_progress_bar=False)
    keyword_scores = np.array([keyword_index.scores_for_query(question)
                               for question in rewritten])
    kural_scores = question_vectors @ kural_vectors.T

    testing_significance = "--significance" in sys.argv
    modes = SIGNIFICANCE_MODES if testing_significance else MODES
    hits_per_mode = {}

    print()
    print(f"{'chapter text':16s} {'hits/100':>9s} {'avg in top5':>12s} "
          f"{'trust':>10s}")
    print("=" * 52)

    for mode in modes:
        chapter_vectors = model.encode(
            build_chapter_descriptions(kurals, mode=mode),
            show_progress_bar=False)
        handed_down = np.repeat(question_vectors @ chapter_vectors.T,
                                KURALS_PER_CHAPTER, axis=1)
        blended = (CHAPTER_BLEND_WEIGHT * handed_down
                   + (1 - CHAPTER_BLEND_WEIGHT) * kural_scores)
        stage_one = (KEYWORD_WEIGHT * normalise_each_row(keyword_scores)
                     + (1 - KEYWORD_WEIGHT) * normalise_each_row(blended))

        found_per_question = []
        total_correct = 0
        for question_index, entry in enumerate(golden):
            correct = correct_kural_numbers_for(entry)
            candidates = np.argsort(
                stage_one[question_index])[::-1][:RERANK_CANDIDATE_COUNT]
            logits = reranker.score_pairs(
                entry["question"], [kurals[p] for p in candidates],
                build_text=rerankable_text)
            best = candidates[np.argsort(logits)[::-1][:TOP_K]]
            found = [kurals[p]["number"] for p in best
                     if kurals[p]["number"] in correct]
            found_per_question.append(bool(found))
            total_correct += len(found)

        hits_per_mode[mode] = np.array(found_per_question)
        trust = "SUSPECT" if mode == "all" else "clean"
        print(f"{mode:16s} {sum(found_per_question):9d} "
              f"{total_correct / len(golden):12.2f} {trust:>10s}")

    print()
    print("  glued = the old stand-in. Anything above it is a real gain.")
    print("  SUSPECT = written after seeing the golden set; ceiling only.")

    if testing_significance:
        # Is the gap real, or could 100 questions have landed this way by luck?
        before, after = SIGNIFICANCE_MODES
        only_before, only_after, p_value = mcnemar_exact(
            hits_per_mode[before], hits_per_mode[after])
        print()
        print("IS THE DIFFERENCE REAL? (McNemar, the correct paired test)")
        print(f"  questions {before} got right and {after} got wrong: "
              f"{only_before}")
        print(f"  questions {before} got wrong and {after} got right: "
              f"{only_after}")
        print(f"  p = {p_value:.4f}  -> "
              + ("REAL, unlikely to be luck" if p_value < 0.05
                 else "COULD BE NOISE, do not claim it"))


if __name__ == "__main__":
    main()
