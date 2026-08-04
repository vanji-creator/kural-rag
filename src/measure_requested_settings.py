"""Vikash's requested configuration, measured before it is trusted.

WHAT CHANGED, BY HIS DECISION (2026-08-04)

    1. PROMPT_MODE          "classic" -> "modern"
       The query rewriter now reaches for plain modern words, not archaic
       ones.
    2. The poem (the 1880s two-line verse translation) is OUT of the
       embedding vectors. It STAYS in the keyword index.
    3. Meaning weight 0.7, word-list weight 0.3 - unchanged, this was
       already the live setting (KEYWORD_WEIGHT = 0.3).

WHAT IS COMPARED

    row 1  what shipped after run #5: modern corpus, classic prompt,
           poem in both halves. Measured then at 97 / 77 / 174.
    row 2  the requested settings above.

Everything else is identical: same corpus, same weights, same chapter
descriptions, same reranker reading the same text.

WHAT THE RECORD SAYS GOING IN

    modern prompt alone (run #2)                 164/233 vs 174
    poem out of embeddings alone (run #9)        Set A 96, all 173, rank-1 111
    the two together                             never measured

Run it:

    venv/bin/python -u src/measure_requested_settings.py
"""

import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

from benchmark_chapters import load_questions, mcnemar_exact
from evaluate import normalise_each_row
from keyword_search import BM25Index
from pipeline import (CHAPTER_BLEND_WEIGHT, EMBEDDING_MODEL_NAME,
                      KEYWORD_WEIGHT, KURALS_PER_CHAPTER,
                      RERANK_CANDIDATE_COUNT, build_chapter_descriptions,
                      cached_vectors, searchable_text)
from rerank import RERANKER_MODEL_NAME, Reranker, rerankable_text

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_PATH = PROJECT_ROOT / "data" / "requested_settings_results.json"

CORPUS_MODE = "modern"
TOP_K = 5

# (label, rewrites file, poem in the embeddings?)
# The poem stays in the keyword index in BOTH rows - only row 2 pulls it out
# of the vectors, which is exactly what was asked for.
ROWS = [
    ("previous best (classic prompt, poem in)",
     "hyde_rewrites_sarvam.json", True),
    ("requested (modern prompt, poem out of embeddings)",
     "hyde_rewrites_modern_prompt.json", False),
]


def score_row(search_texts, all_questions, kurals, model, reranker,
              poem_in_embeddings):
    """Hit/miss and rank-1 over all questions for one configuration.

    Mirrors KuralRetriever exactly: the embedding half and the keyword half
    each get their own text, the reranker reads the original question against
    the modern corpus text with the poem included.
    """
    embedding_texts = [
        searchable_text(record, CORPUS_MODE,
                        include_couplet=poem_in_embeddings)
        for record in kurals]
    keyword_texts = [
        searchable_text(record, CORPUS_MODE, include_couplet=True)
        for record in kurals]

    cache_name = (f"kurals_{CORPUS_MODE}" if poem_in_embeddings
                  else f"kurals_{CORPUS_MODE}_nopoem")
    kural_vectors = cached_vectors(model, embedding_texts, cache_name)
    chapter_vectors = cached_vectors(model, build_chapter_descriptions(kurals),
                                     "chapters")
    keyword_index = BM25Index(keyword_texts)

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

    hit_top5, hit_rank1 = [], []
    for index, (original_question, correct) in enumerate(all_questions):
        candidates = np.argsort(stage_one[index])[::-1][:RERANK_CANDIDATE_COUNT]
        logits = reranker.score_pairs(
            original_question, [kurals[p] for p in candidates],
            build_text=lambda record: rerankable_text(record, CORPUS_MODE))
        best = candidates[np.argsort(logits)[::-1][:TOP_K]]
        hit_top5.append(any(kurals[p]["number"] in correct for p in best))
        hit_rank1.append(kurals[best[0]]["number"] in correct)
    return np.array(hit_top5), np.array(hit_rank1)


def main():
    kurals = json.load(open(PROJECT_ROOT / "data" / "kurals.json",
                            encoding="utf-8"))
    set_a, set_b = load_questions()
    all_questions = set_a + set_b
    split = len(set_a)

    print("loading the models...")
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    reranker = Reranker(RERANKER_MODEL_NAME)

    top5, rank1 = {}, {}
    for label, rewrites_file, poem_in_embeddings in ROWS:
        with open(PROJECT_ROOT / "data" / rewrites_file,
                  encoding="utf-8") as open_file:
            rewrites = json.load(open_file)
        print(f"scoring: {label}...")
        top5[label], rank1[label] = score_row(
            rewrites, all_questions, kurals, model, reranker,
            poem_in_embeddings)

    with open(RESULTS_PATH, "w", encoding="utf-8") as open_file:
        json.dump({label: {"top5": [bool(h) for h in top5[label]],
                           "rank1": [bool(h) for h in rank1[label]]}
                   for label, _, _ in ROWS}, open_file, indent=2)
    print(f"per-question results saved to {RESULTS_PATH.name}")

    print()
    print("=" * 76)
    print("'top 5' = a correct verse reached the five shown to a reader.")
    print("'rank 1' = the FIRST verse shown was correct.")
    print("Set A is the hand-checked key. Set B rewards chapter matching.")
    print("=" * 76)
    print(f"{'configuration':50s} {'Set A':>7s} {'Set B':>7s} "
          f"{'all':>8s} {'rank-1':>8s}")
    for label, _, _ in ROWS:
        hits = top5[label]
        print(f"{label:50s} {int(hits[:split].sum()):>3d}/100 "
              f"{int(hits[split:].sum()):>3d}/133 "
              f"{int(hits.sum()):>4d}/233 "
              f"{int(rank1[label].sum()):>4d}/233")

    before = ROWS[0][0]
    after = ROWS[1][0]
    print()
    print("IS THE DIFFERENCE REAL? (McNemar's exact test)")
    print("  It looks only at questions the two configurations disagree on.")
    print("  p below 0.05 means a gap that lopsided is unlikely to be luck.")
    for name, results in (("top-5, Set A only", (top5, 0, split)),
                          ("top-5, all 233", (top5, 0, len(all_questions))),
                          ("rank-1, all 233", (rank1, 0,
                                               len(all_questions)))):
        table, lo, hi = results
        worse, better, p = mcnemar_exact(table[before][lo:hi],
                                         table[after][lo:hi])
        print()
        print(f"  {name}")
        print(f"    previous right, requested wrong : {worse}")
        print(f"    previous wrong, requested right : {better}")
        print(f"    p = {p:.4f}  -> "
              + ("REAL" if p < 0.05 else "NOT ESTABLISHED"))


if __name__ == "__main__":
    main()
