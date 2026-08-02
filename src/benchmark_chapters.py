"""The large benchmark: do hand-written chapter descriptions actually win?

WHY THIS EXISTS

On 100 questions the hand-written descriptions scored 90 against the glued
stand-in's 85. But the correct paired test said p = 0.125 - only 7 questions
disagreed between the two methods, 6 one way and 1 the other. Suggestive, not
proof. The power calculation said 200 questions would settle it.

So this runs 233:

    SET A  the original 100 golden questions. Written BEFORE the chapter
           descriptions existed, so they cannot echo them. Their answer key
           includes 200 hand-checked cross-chapter verses.

    SET B  133 new questions, one per chapter, written from the verses.
           Their answer key is the chapter each was written for - STRICTER
           than set A, because a genuinely correct verse in another chapter
           counts as wrong. That lowers the absolute score for BOTH methods
           equally, so the COMPARISON stays fair.

LEAKAGE CONTROL ON SET B

The same author wrote the chapter descriptions and these questions, so the
questions could unconsciously echo the descriptions. Every new question was
checked: if half or more of its meaningful words also appeared in this
author's description for its own chapter, it was rewritten. 17 were rewritten
once, 3 twice. The final count flagged is zero.

That check cannot prove independence. It only removes the obvious cases.

Run it:

    venv/bin/python src/benchmark_chapters.py
"""

import json
from math import comb
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
MODES = ["glued", "topic+words"]


def mcnemar_exact(hits_a, hits_b):
    """Is the gap between two methods real, or could it be luck?

    Looks ONLY at questions where the two methods disagree. If a change did
    nothing, wins and losses would be about equal. A lopsided split is the
    signal. p below 0.05 means the gap is unlikely to be chance.
    """
    only_a = int(np.sum(hits_a & ~hits_b))
    only_b = int(np.sum(~hits_a & hits_b))
    total = only_a + only_b
    if total == 0:
        return only_a, only_b, 1.0
    smaller = min(only_a, only_b)
    p = 2 * sum(comb(total, i) for i in range(smaller + 1)) / 2 ** total
    return only_a, only_b, min(p, 1.0)


def load_questions():
    """Both question sets, each as (question_text, set_of_correct_numbers)."""
    golden = json.load(open(PROJECT_ROOT / "data" / "golden_set.json",
                            encoding="utf-8"))
    set_a = [(entry["question"], correct_kural_numbers_for(entry))
             for entry in golden]

    new = json.load(open(PROJECT_ROOT / "data" / "benchmark_questions_a.json",
                         encoding="utf-8"))
    set_b = []
    for chapter_text, question in new.items():
        chapter = int(chapter_text)
        first = (chapter - 1) * KURALS_PER_CHAPTER + 1
        set_b.append((question,
                      set(range(first, first + KURALS_PER_CHAPTER))))
    return set_a, set_b


def main():
    kurals = json.load(open(PROJECT_ROOT / "data" / "kurals.json",
                            encoding="utf-8"))
    set_a, set_b = load_questions()
    all_questions = set_a + set_b
    print(f"set A (original golden): {len(set_a)}")
    print(f"set B (new, per chapter): {len(set_b)}")
    print(f"total: {len(all_questions)}")

    model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    reranker = Reranker(RERANKER_MODEL_NAME)

    kural_texts = [searchable_text(record) for record in kurals]
    kural_vectors = model.encode(kural_texts, show_progress_bar=False)
    keyword_index = BM25Index(kural_texts)

    rewritten = [rewrite(question) for question, _ in all_questions]
    question_vectors = model.encode(rewritten, show_progress_bar=False)
    keyword_scores = np.array([keyword_index.scores_for_query(text)
                               for text in rewritten])
    kural_scores = question_vectors @ kural_vectors.T

    hits_per_mode = {}
    for mode in MODES:
        print(f"running {mode}...")
        chapter_vectors = model.encode(
            build_chapter_descriptions(kurals, mode=mode),
            show_progress_bar=False)
        handed_down = np.repeat(question_vectors @ chapter_vectors.T,
                                KURALS_PER_CHAPTER, axis=1)
        blended = (CHAPTER_BLEND_WEIGHT * handed_down
                   + (1 - CHAPTER_BLEND_WEIGHT) * kural_scores)
        stage_one = (KEYWORD_WEIGHT * normalise_each_row(keyword_scores)
                     + (1 - KEYWORD_WEIGHT) * normalise_each_row(blended))

        found = []
        for index, (question, correct) in enumerate(all_questions):
            candidates = np.argsort(
                stage_one[index])[::-1][:RERANK_CANDIDATE_COUNT]
            logits = reranker.score_pairs(
                question, [kurals[p] for p in candidates],
                build_text=rerankable_text)
            best = candidates[np.argsort(logits)[::-1][:TOP_K]]
            found.append(any(kurals[p]["number"] in correct for p in best))
        hits_per_mode[mode] = np.array(found)

    split = len(set_a)
    print()
    print("=" * 62)
    print(f"{'question set':22s} {'glued':>10s} {'topic+words':>14s} "
          f"{'gain':>7s}")
    print("=" * 62)
    for label, lo, hi in [("A  original 100", 0, split),
                          ("B  new 133", split, len(all_questions)),
                          ("A + B  all 233", 0, len(all_questions))]:
        before = int(hits_per_mode["glued"][lo:hi].sum())
        after = int(hits_per_mode["topic+words"][lo:hi].sum())
        count = hi - lo
        print(f"{label:22s} {before:>6d}/{count:<3d} {after:>10d}/{count:<3d} "
              f"{after - before:>+7d}")

    print()
    print("IS IT REAL? (McNemar, on all 233)")
    worse, better, p = mcnemar_exact(hits_per_mode["glued"],
                                     hits_per_mode["topic+words"])
    print(f"  glued right, topic+words wrong: {worse}")
    print(f"  glued wrong, topic+words right: {better}")
    print(f"  p = {p:.4f}  -> "
          + ("REAL, unlikely to be luck" if p < 0.05
             else "STILL NOT ESTABLISHED"))


if __name__ == "__main__":
    main()
