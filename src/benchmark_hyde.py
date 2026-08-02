"""Does rewriting the question with a language model actually improve search?

THE QUESTION THIS ANSWERS

Everything so far says the rewrites LOOK right. Asked "how do I keep my
temper?", the model produced "controlling anger, temper, wrath and
irritation" - bridging temper to wrath, which is exactly the vocabulary gap
that accounts for seven of our fifteen remaining failures.

"Looks right" is what the scorecard exists to overrule.

WHAT IS COMPARED

    word list   src/rewrite_query.py - deletes a fixed list of question words.
                This is what ships today. It took retrieval 44 -> 69 and it
                also destroyed two questions outright ("should I spend time
                with people better than me?" became "spend time").

    HyDE        a language model rewrites the question as a STATEMENT of what
                the answer would say, so we search for an answer instead of
                matching a rhetorical question.

Everything else is held fixed. Same corpus, same chapter descriptions, same
keyword weighting, same reranker. Only the query text changes.

SPEED IS NOT MEASURED HERE, ON PURPOSE

This laptop has 8 cores; the free host we were considering has 2. Any timing
taken here would be optimistic and would not transfer. What DOES transfer is
whether the rewrites help - the same model produces the same text anywhere.

So this runs slowly and does not care. If HyDE does not help, the hosting
question never needs answering.

Run it:

    venv/bin/python src/benchmark_hyde.py
"""

import json
import time
from math import comb
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

from benchmark_chapters import load_questions, mcnemar_exact
from evaluate import normalise_each_row
from keyword_search import BM25Index
from pipeline import (CHAPTER_BLEND_WEIGHT, EMBEDDING_MODEL_NAME,
                      KEYWORD_WEIGHT, KURALS_PER_CHAPTER,
                      RERANK_CANDIDATE_COUNT, build_chapter_descriptions,
                      searchable_text)
from rerank import RERANKER_MODEL_NAME, Reranker, rerankable_text
from rewrite_query import rewrite as word_list_rewrite

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TOP_K = 5
HYDE_CACHE_PATH = PROJECT_ROOT / "data" / "hyde_rewrites.json"


def get_hyde_rewrites(questions):
    """Rewrite every question with the language model, caching to disk.

    Cached because it takes 15+ seconds each on this machine and the result
    for a given question never changes (temperature is 0).
    """
    cache = {}
    if HYDE_CACHE_PATH.exists():
        with open(HYDE_CACHE_PATH, encoding="utf-8") as open_file:
            cache = json.load(open_file)

    missing = [q for q in questions if q not in cache]
    if missing:
        print(f"rewriting {len(missing)} questions with the language model...")
        # Use llama.cpp only if the model file is ALREADY on disk. It is a
        # speed optimisation and speed is not what this script measures - the
        # timing on this laptop would not transfer to the host anyway.
        gguf = list(Path.home().glob(
            ".cache/huggingface/hub/**/Qwen3-1.7B-BF16.gguf"))
        if gguf:
            from hyde_fast import FastHydeRewriter
            rewriter = FastHydeRewriter()
        else:
            print("  (no llama.cpp model on disk; using transformers - "
                  "slower, identical output)")
            from hyde import HydeRewriter
            rewriter = HydeRewriter()

        started_at = time.perf_counter()
        for index, question in enumerate(missing, start=1):
            cache[question] = rewriter.rewrite(question)
            if index % 10 == 0 or index == len(missing):
                per = (time.perf_counter() - started_at) / index
                left = (len(missing) - index) * per
                print(f"  {index}/{len(missing)}  "
                      f"{per:.1f}s each, ~{left / 60:.0f} min left")
        with open(HYDE_CACHE_PATH, "w", encoding="utf-8") as open_file:
            json.dump(cache, open_file, ensure_ascii=False, indent=2)

    return [cache[q] for q in questions]


def score_with_queries(search_texts, all_questions, kurals, model, reranker,
                       kural_vectors, chapter_vectors, keyword_index):
    """Run the whole pipeline with these query strings. Returns hit/miss."""
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

    found = []
    for index, (original_question, correct) in enumerate(all_questions):
        candidates = np.argsort(stage_one[index])[::-1][:RERANK_CANDIDATE_COUNT]
        # The reranker always reads the ORIGINAL question, never the rewrite -
        # it sees both texts together, so the full sentence helps it.
        logits = reranker.score_pairs(original_question,
                                      [kurals[p] for p in candidates],
                                      build_text=rerankable_text)
        best = candidates[np.argsort(logits)[::-1][:TOP_K]]
        found.append(any(kurals[p]["number"] in correct for p in best))
    return np.array(found)


def main():
    kurals = json.load(open(PROJECT_ROOT / "data" / "kurals.json",
                            encoding="utf-8"))
    set_a, set_b = load_questions()
    all_questions = set_a + set_b
    questions = [q for q, _ in all_questions]
    print(f"{len(all_questions)} questions "
          f"({len(set_a)} golden + {len(set_b)} per-chapter)")

    hyde_texts = get_hyde_rewrites(questions)
    word_list_texts = [word_list_rewrite(q) for q in questions]

    print()
    print("a few rewrites, side by side:")
    for index in (0, 40, 100, 160):
        print(f"  Q     {questions[index]}")
        print(f"  list  {word_list_texts[index]}")
        print(f"  hyde  {hyde_texts[index]}")
        print()

    model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    reranker = Reranker(RERANKER_MODEL_NAME)
    kural_texts = [searchable_text(record) for record in kurals]
    kural_vectors = model.encode(kural_texts, show_progress_bar=False)
    chapter_vectors = model.encode(build_chapter_descriptions(kurals),
                                   show_progress_bar=False)
    keyword_index = BM25Index(kural_texts)

    results = {}
    for label, texts in [("word list (ships today)", word_list_texts),
                         ("HyDE (language model)", hyde_texts)]:
        print(f"running {label}...")
        results[label] = score_with_queries(
            texts, all_questions, kurals, model, reranker,
            kural_vectors, chapter_vectors, keyword_index)

    split = len(set_a)
    before_key, after_key = list(results)
    print()
    print("=" * 66)
    print(f"{'question set':22s} {'word list':>12s} {'HyDE':>10s} {'gain':>7s}")
    print("=" * 66)
    for label, lo, hi in [("A  golden 100", 0, split),
                          ("B  per-chapter 133", split, len(all_questions)),
                          ("A + B  all 233", 0, len(all_questions))]:
        before = int(results[before_key][lo:hi].sum())
        after = int(results[after_key][lo:hi].sum())
        print(f"{label:22s} {before:>8d}/{hi - lo:<3d} {after:>6d}/{hi - lo:<3d} "
              f"{after - before:>+7d}")

    worse, better, p = mcnemar_exact(results[before_key], results[after_key])
    print()
    print("IS IT REAL? (McNemar, on all 233)")
    print(f"  word list right, HyDE wrong: {worse}")
    print(f"  word list wrong, HyDE right: {better}")
    print(f"  p = {p:.4f}  -> "
          + ("REAL, unlikely to be luck" if p < 0.05
             else "NOT ESTABLISHED - do not claim it"))


if __name__ == "__main__":
    main()
