"""Does a fatter candidate pile turn into real wins? 50 vs 75.

WHY THIS RUNS (2026-08-04)

The ticket table said success climbs with ticket count and never flattens.
But that table is a correlation - easy questions may simply be easy for both
stages. This is the intervention that separates the two readings: hand EVERY
question more tickets and see whether the wins follow.

    top-5 rises          -> tickets cause wins, stage-one enrichment is real
    top-5 flat or down   -> the climb was "easy is easy everywhere";
                            the reranker model is the wall

Vikash chose 75 before trying 100. The cost is reranker time - 75 pairs
per question instead of 50, so about 1.5x - and it is measured below, not
guessed.

Both arms are otherwise identical to the live pipeline: modern corpus,
classic-prompt rewrites, poem in both halves, meaning 0.7 / word list 0.3.

Run it:

    venv/bin/python -u src/measure_candidate_count.py
"""

import json
import time
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

from benchmark_chapters import load_questions, mcnemar_exact
from evaluate import normalise_each_row
from keyword_search import BM25Index
from pipeline import (CHAPTER_BLEND_WEIGHT, EMBEDDING_MODEL_NAME,
                      KEYWORD_WEIGHT, KURALS_PER_CHAPTER,
                      build_chapter_descriptions, cached_vectors,
                      searchable_text)
from rerank import RERANKER_MODEL_NAME, Reranker, rerankable_text

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REWRITES_PATH = PROJECT_ROOT / "data" / "hyde_rewrites_sarvam.json"
RESULTS_PATH = PROJECT_ROOT / "data" / "candidate_count_results.json"

CORPUS_MODE = "modern"
TOP_K = 5
PILE_SIZES = [50, 75]


def main():
    kurals = json.load(open(PROJECT_ROOT / "data" / "kurals.json",
                            encoding="utf-8"))
    set_a, set_b = load_questions()
    all_questions = set_a + set_b
    split = len(set_a)
    with open(REWRITES_PATH, encoding="utf-8") as open_file:
        search_texts = json.load(open_file)

    print("loading the models...")
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    reranker = Reranker(RERANKER_MODEL_NAME)

    kural_texts = [searchable_text(record, CORPUS_MODE) for record in kurals]
    kural_vectors = cached_vectors(model, kural_texts, f"kurals_{CORPUS_MODE}")
    chapter_vectors = cached_vectors(model, build_chapter_descriptions(kurals),
                                     "chapters")
    keyword_index = BM25Index(kural_texts)

    question_vectors = model.encode(search_texts, show_progress_bar=False)
    keyword_scores = np.array([keyword_index.scores_for_query(text)
                               for text in search_texts])
    kural_scores = question_vectors @ kural_vectors.T
    handed_down = np.repeat(question_vectors @ chapter_vectors.T,
                            KURALS_PER_CHAPTER, axis=1)
    blended = (CHAPTER_BLEND_WEIGHT * handed_down
               + (1 - CHAPTER_BLEND_WEIGHT) * kural_scores)
    stage_one = (KEYWORD_WEIGHT * normalise_each_row(keyword_scores)
                 + (1 - KEYWORD_WEIGHT) * normalise_each_row(blended))

    results = {}
    for pile_size in PILE_SIZES:
        print(f"scoring with a pile of {pile_size}...")
        top5, rank1, tickets = [], [], []
        rerank_seconds = 0.0
        for index, (question, correct) in enumerate(all_questions):
            candidates = np.argsort(stage_one[index])[::-1][:pile_size]
            tickets.append(sum(1 for p in candidates
                               if kurals[p]["number"] in correct))
            started_at = time.perf_counter()
            logits = reranker.score_pairs(
                question, [kurals[p] for p in candidates],
                build_text=lambda record: rerankable_text(record,
                                                          CORPUS_MODE))
            rerank_seconds += time.perf_counter() - started_at
            best = candidates[np.argsort(logits)[::-1][:TOP_K]]
            top5.append(any(kurals[p]["number"] in correct for p in best))
            rank1.append(kurals[best[0]]["number"] in correct)
        results[pile_size] = {
            "top5": np.array(top5), "rank1": np.array(rank1),
            "tickets": np.array(tickets),
            "ms_per_question": rerank_seconds / len(all_questions) * 1000}

    with open(RESULTS_PATH, "w", encoding="utf-8") as open_file:
        json.dump({str(size): {"top5": [bool(h) for h in r["top5"]],
                               "rank1": [bool(h) for h in r["rank1"]],
                               "tickets": [int(t) for t in r["tickets"]]}
                   for size, r in results.items()}, open_file, indent=2)

    print()
    print("=" * 74)
    print("'tickets' = correct verses in the pile, average per question.")
    print("'top 5' = a correct verse reached the five shown to a reader.")
    print("'rank 1' = the first verse shown was correct.")
    print("'rerank ms' = milliseconds the reranker takes per question.")
    print("=" * 74)
    print(f"{'pile':>6s} {'tickets':>8s} {'Set A':>8s} {'Set B':>8s} "
          f"{'all':>9s} {'rank-1':>9s} {'rerank ms':>10s}")
    for size in PILE_SIZES:
        r = results[size]
        print(f"{size:>6d} {r['tickets'].mean():>8.1f} "
              f"{int(r['top5'][:split].sum()):>4d}/100 "
              f"{int(r['top5'][split:].sum()):>4d}/133 "
              f"{int(r['top5'].sum()):>5d}/233 "
              f"{int(r['rank1'].sum()):>5d}/233 "
              f"{r['ms_per_question']:>10.0f}")

    small, large = PILE_SIZES
    print()
    print(f"IS THE DIFFERENCE REAL? ({small} vs {large}, McNemar's exact test)")
    print("  It looks only at questions the two pile sizes disagree on.")
    print("  p below 0.05 means a gap that lopsided is unlikely to be luck.")
    for name, field in (("top-5, all 233", "top5"),
                        ("rank-1, all 233", "rank1")):
        worse, better, p = mcnemar_exact(results[small][field],
                                         results[large][field])
        print()
        print(f"  {name}")
        print(f"    {small} right, {large} wrong : {worse}")
        print(f"    {small} wrong, {large} right : {better}")
        print(f"    p = {p:.4f}  -> "
              + ("REAL" if p < 0.05 else "NOT ESTABLISHED"))


if __name__ == "__main__":
    main()
