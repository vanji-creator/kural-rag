"""How many of a question's correct verses actually reach the 50 candidates?

WHY THIS RUNS (Vikash's question, 2026-08-04)

We know that for 214 of 233 questions AT LEAST ONE correct verse is in the 50
that stage one hands to the reranker. We have never asked how many.

The reranker scores each candidate independently, so every correct verse in
the pile is one more chance - one more ticket - for the top 5 to be right.
A question that sends 6 tickets in is much safer than one that sends 1.

WHAT THIS DECIDES

    most questions send several tickets  -> the pile is healthy, the reranker
                                            model itself is the thing to fix
    most questions send only 1           -> stage one is starving the
                                            reranker, fix stage one first

Configuration: the live one. Modern corpus, classic-prompt rewrites, poem in
both halves, meaning 0.7 / word list 0.3, chapter blend 0.5.

Run it:

    venv/bin/python -u src/count_tickets.py
"""

import json
from collections import Counter
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

CORPUS_MODE = "modern"


def main():
    kurals = json.load(open(PROJECT_ROOT / "data" / "kurals.json",
                            encoding="utf-8"))
    set_a, set_b = load_questions()
    all_questions = set_a + set_b
    split = len(set_a)
    with open(REWRITES_PATH, encoding="utf-8") as open_file:
        search_texts = json.load(open_file)

    print("loading the embedding model...")
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

    # For every question: how many correct verses exist, how many reached
    # the 50, and at what positions inside the 50 they sit.
    tickets_per_question = []
    correct_totals = []
    deepest_positions = []
    for index, (question, correct) in enumerate(all_questions):
        candidates = np.argsort(stage_one[index])[::-1][:RERANK_CANDIDATE_COUNT]
        candidate_numbers = [kurals[p]["number"] for p in candidates]
        in_pile = [pos for pos, number in enumerate(candidate_numbers, start=1)
                   if number in correct]
        tickets_per_question.append(len(in_pile))
        correct_totals.append(len(correct))
        if in_pile:
            deepest_positions.append(max(in_pile))

    tickets = np.array(tickets_per_question)
    totals = np.array(correct_totals)

    print()
    print("=" * 70)
    print("A 'ticket' is one correct verse inside the 50 candidates.")
    print("'correct verses' is how many exist in the answer key at all.")
    print("More tickets in = more chances for the reranker to get it right.")
    print("=" * 70)
    for name, lo, hi in (("Set A (hand-checked key)", 0, split),
                         ("Set B (one-chapter key)", split, len(tickets)),
                         ("all 233", 0, len(tickets))):
        part = tickets[lo:hi]
        part_totals = totals[lo:hi]
        print()
        print(f"{name}")
        print(f"  correct verses per question, average : "
              f"{part_totals.mean():.1f}")
        print(f"  tickets in the 50, average           : {part.mean():.1f}")
        print(f"  share of correct verses that got in  : "
              f"{part.sum() / part_totals.sum():.0%}")

    print()
    print("HOW MANY QUESTIONS SEND IN 0, 1, 2... TICKETS (all 233)")
    spread = Counter(tickets.tolist())
    for count in sorted(spread):
        bar = "#" * spread[count]
        print(f"  {count:>2d} tickets  {spread[count]:>3d} questions  {bar}")

    print()
    print("Questions with 0 tickets can NEVER be answered by any reranker.")
    print("Questions with 1 ticket give the reranker one single chance.")
    lonely = int((tickets == 1).sum())
    none = int((tickets == 0).sum())
    print(f"  0 tickets : {none}")
    print(f"  1 ticket  : {lonely}")

    if deepest_positions:
        deepest = np.array(deepest_positions)
        print()
        print("WHERE THE DEEPEST TICKET SITS (position inside the 50)")
        print("  If most sit past position 25, halving the pile would lose")
        print("  correct verses - the reranker itself ignores position.")
        print(f"  average deepest position : {deepest.mean():.0f}")
        print(f"  past position 25         : {int((deepest > 25).sum())} "
              f"questions")


if __name__ == "__main__":
    main()
