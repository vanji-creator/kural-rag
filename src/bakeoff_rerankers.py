"""Three rerankers, one question set, one variable at a time.

WHY THIS RUNS (2026-08-04)

The reranker is convicted: given 7 correct verses out of 50 on average, it
still fails rank-1 on more than half the questions, and handing it MORE
correct verses made it worse (50 vs 75 pile, p = 0.0352). The model is the
wall. Now we choose its replacement by measurement.

THE ARMS, AND WHAT EACH COMPARISON ISOLATES

    A  ms-marco-MiniLM-L-6-v2          what ships. 6 layers, English only,
                                       trained on web-search clicks.
    B  ms-marco-MiniLM-L-12-v2         SAME training data, twice the layers.
                                       A vs B isolates DEPTH.
    C  mmarco-mMiniLMv2-L12-H384-v1    12 layers, trained on the same
                                       questions machine-translated into 13
                                       languages. B vs C isolates LANGUAGE
                                       TRAINING at matched depth.
    D  arm C's model, but reading the Tamil meaning as well as the English.
                                       C vs D isolates the INPUT TEXT.

Honesty notes, written before the numbers:
  - mmarco's 13 translated languages do NOT include Tamil. But the model it
    grew from (XLM-RoBERTa, then shrunk) read 100 languages including Tamil.
    So arm D tests inferred Tamil ability, not declared.
  - C changes both data and base model relative to B - matched depth is the
    control, but this is not as clean as A vs B.

Everything else is frozen: modern corpus, classic-prompt rewrites, pile of
50, meaning 0.7 / word list 0.3. Stage one is computed once and shared.

Run it:

    venv/bin/python -u src/bakeoff_rerankers.py
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
                      RERANK_CANDIDATE_COUNT, build_chapter_descriptions,
                      cached_vectors, searchable_text)
from rerank import (RERANKER_MODEL_NAME, Reranker, rerankable_text,
                    rerankable_text_with_tamil)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REWRITES_PATH = PROJECT_ROOT / "data" / "hyde_rewrites_sarvam.json"
RESULTS_PATH = PROJECT_ROOT / "data" / "reranker_bakeoff_results.json"

CORPUS_MODE = "modern"
TOP_K = 5

# (label, model name, build_text for the kural side)
ARMS = [
    ("A: L6 english (ships)", RERANKER_MODEL_NAME, rerankable_text),
    ("B: L12 english", "cross-encoder/ms-marco-MiniLM-L-12-v2",
     rerankable_text),
    ("C: L12 multilingual", "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",
     rerankable_text),
    ("D: C + tamil text", "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",
     rerankable_text_with_tamil),
]


def main():
    kurals = json.load(open(PROJECT_ROOT / "data" / "kurals.json",
                            encoding="utf-8"))
    set_a, set_b = load_questions()
    all_questions = set_a + set_b
    split = len(set_a)
    with open(REWRITES_PATH, encoding="utf-8") as open_file:
        search_texts = json.load(open_file)

    print("computing stage one once (shared by every arm)...")
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

    # The 50 candidates per question are fixed BEFORE any reranker runs, so
    # every arm reorders exactly the same pile.
    piles = [np.argsort(stage_one[index])[::-1][:RERANK_CANDIDATE_COUNT]
             for index in range(len(all_questions))]

    results = {}
    loaded = {}
    for label, model_name, build_text in ARMS:
        if model_name not in loaded:
            print(f"loading {model_name}...")
            loaded[model_name] = Reranker(model_name)
        reranker = loaded[model_name]

        print(f"scoring {label}...")
        top5, rank1 = [], []
        rerank_seconds = 0.0
        for index, (question, correct) in enumerate(all_questions):
            candidates = piles[index]
            started_at = time.perf_counter()
            logits = reranker.score_pairs(
                question, [kurals[p] for p in candidates],
                build_text=lambda record: build_text(record, CORPUS_MODE))
            rerank_seconds += time.perf_counter() - started_at
            best = candidates[np.argsort(logits)[::-1][:TOP_K]]
            top5.append(any(kurals[p]["number"] in correct for p in best))
            rank1.append(kurals[best[0]]["number"] in correct)
        results[label] = {"top5": np.array(top5), "rank1": np.array(rank1),
                          "ms": rerank_seconds / len(all_questions) * 1000}

    with open(RESULTS_PATH, "w", encoding="utf-8") as open_file:
        json.dump({label: {"top5": [bool(h) for h in r["top5"]],
                           "rank1": [bool(h) for h in r["rank1"]],
                           "ms_per_question": r["ms"]}
                   for label, r in results.items()}, open_file, indent=2)
    print(f"per-question results saved to {RESULTS_PATH.name}")

    print()
    print("=" * 78)
    print("'top 5' = a correct verse reached the five shown to a reader.")
    print("'rank 1' = the first verse shown was correct.")
    print("'ms' = reranking milliseconds per question. Smaller is faster.")
    print("Perfect reranking of this pile would score 214/233 on top-5.")
    print("=" * 78)
    print(f"{'arm':26s} {'Set A':>8s} {'Set B':>8s} {'all':>9s} "
          f"{'rank-1':>9s} {'ms':>7s}")
    for label, _, _ in ARMS:
        r = results[label]
        print(f"{label:26s} {int(r['top5'][:split].sum()):>4d}/100 "
              f"{int(r['top5'][split:].sum()):>4d}/133 "
              f"{int(r['top5'].sum()):>5d}/233 "
              f"{int(r['rank1'].sum()):>5d}/233 "
              f"{r['ms']:>7.0f}")

    baseline = ARMS[0][0]
    print()
    print("IS ANY DIFFERENCE REAL? (McNemar's exact test, against arm A)")
    print("  It looks only at questions the two arms disagree on.")
    print("  p below 0.05 means a gap that lopsided is unlikely to be luck.")
    for label, _, _ in ARMS[1:]:
        for name, field in (("top-5", "top5"), ("rank-1", "rank1")):
            worse, better, p = mcnemar_exact(results[baseline][field],
                                             results[label][field])
            print()
            print(f"  {label} vs A, {name}")
            print(f"    A right, this wrong : {worse}")
            print(f"    A wrong, this right : {better}")
            print(f"    p = {p:.4f}  -> "
                  + ("REAL" if p < 0.05 else "NOT ESTABLISHED"))


if __name__ == "__main__":
    main()
