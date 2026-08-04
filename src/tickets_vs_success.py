"""Does giving the reranker more tickets make it succeed more?

WHAT THIS DECIDES (Vikash's question, 2026-08-04)

Stage one puts 62% of all correct verses into the 50 candidates. Is pushing
that to 70% worth doing BEFORE swapping the reranker model?

    success climbs with ticket count  -> yes: more tickets = more hits,
                                         stage-one enrichment pays first
    success flattens after a few      -> no: the reranker is the wall,
                                         extra tickets are wasted on it

Tickets are recomputed here (cheap - cached vectors, no reranker calls).
The top-5 hit/miss per question comes from data/set_a_check_results.json,
the "modern corpus" row - the live configuration, scored earlier today.

Run it:

    venv/bin/python -u src/tickets_vs_success.py
"""

import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

from benchmark_chapters import load_questions
from evaluate import normalise_each_row
from keyword_search import BM25Index
from pipeline import (CHAPTER_BLEND_WEIGHT, EMBEDDING_MODEL_NAME,
                      KEYWORD_WEIGHT, KURALS_PER_CHAPTER,
                      RERANK_CANDIDATE_COUNT, build_chapter_descriptions,
                      cached_vectors, searchable_text)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REWRITES_PATH = PROJECT_ROOT / "data" / "hyde_rewrites_sarvam.json"
HITS_PATH = PROJECT_ROOT / "data" / "set_a_check_results.json"

CORPUS_MODE = "modern"


def main():
    kurals = json.load(open(PROJECT_ROOT / "data" / "kurals.json",
                            encoding="utf-8"))
    set_a, set_b = load_questions()
    all_questions = set_a + set_b
    with open(REWRITES_PATH, encoding="utf-8") as open_file:
        search_texts = json.load(open_file)
    with open(HITS_PATH, encoding="utf-8") as open_file:
        hits = np.array(json.load(open_file)["modern corpus"])

    print("computing tickets (cached vectors, seconds)...")
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)
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

    tickets = []
    for index, (question, correct) in enumerate(all_questions):
        candidates = np.argsort(stage_one[index])[::-1][:RERANK_CANDIDATE_COUNT]
        tickets.append(sum(1 for p in candidates
                           if kurals[p]["number"] in correct))
    tickets = np.array(tickets)

    print()
    print("=" * 66)
    print("Each row groups questions by how many tickets they sent in.")
    print("'top-5 hit rate' = how often the reranker kept a correct verse")
    print("in the five shown. If more tickets meant more success, this")
    print("column would keep climbing down the table.")
    print("=" * 66)
    print(f"{'tickets':>10s} {'questions':>10s} {'top-5 hits':>11s} "
          f"{'hit rate':>9s}")
    bands = [(0, 0), (1, 1), (2, 3), (4, 6), (7, 9), (10, 50)]
    for low, high in bands:
        chosen = (tickets >= low) & (tickets <= high)
        count = int(chosen.sum())
        if count == 0:
            continue
        won = int(hits[chosen].sum())
        label = f"{low}" if low == high else f"{low}-{high}"
        print(f"{label:>10s} {count:>10d} {won:>11d} {won / count:>8.0%}")

    print()
    without_zero = tickets > 0
    print(f"questions with at least 1 ticket : {int(without_zero.sum())}")
    print(f"the reranker kept one in top 5   : {int(hits[without_zero].sum())}")
    print(f"lost despite having tickets      : "
          f"{int(without_zero.sum() - hits[without_zero].sum())}")


if __name__ == "__main__":
    main()
