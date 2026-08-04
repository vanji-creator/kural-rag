"""The big multilingual reranker, measured. bge-reranker-v2-m3, 568M.

WHY THIS RUNS (2026-08-04)

The small-model bake-off ended with no winner: doubling depth bought +3 (not
established), same-size multilingual training cost 9, and Tamil input won
back 8 for the model that could read it. The one candidate that is both LARGE
and genuinely Tamil-capable is this one. 568M parameters against the 22M
that ships - 25 times bigger.

THE ARMS

    E  bge-reranker-v2-m3, reading the same English text arm A reads.
       E vs A = everything at once: depth, training data, capacity.
    F  the same model, reading the Tamil meaning as well.
       F vs E isolates the input text, same as D vs C did.

Arm A's per-question results are loaded from the saved bake-off file, not
re-run - same frozen candidate piles, so the comparison is exact.

STATED BEFORE THE RUN

    what would ship it: beating A's 174/233 with p below 0.05, or a clear
    rank-1 gain at no top-5 cost. Speed does NOT veto: this project is
    exact-only, and a slow accurate reranker beats a fast sloppy one.

    what would end this line: losing to A, or a gap too small to establish.
    Then the reranker conversation moves to the LLM-as-reranker ceiling
    measurement, or stops.

CHECKPOINTING (added 2026-08-04, after losing 40 minutes of compute)

The first version of this script kept every score in memory and wrote one
file at the very end. It was stopped at question ~120 because the laptop
overheated, and everything was lost. The same mistake is already in
EXPERIMENT_LOG.md from the rewrite work: "a crash should cost the one in
flight." Now every 10 questions go to disk, and a restarted run continues
from the last saved question instead of starting over.

THREAD CAP

By default the model grabs every processor core, which is what cooked the
laptop. MAX_THREADS = 2 keeps it cool at the price of speed. Raise it only
on a machine that can take the heat.

Run it:

    venv/bin/python -u src/bakeoff_bge.py
"""

import json
import time
from pathlib import Path

import numpy as np
import torch
from sentence_transformers import SentenceTransformer

from benchmark_chapters import load_questions, mcnemar_exact
from evaluate import normalise_each_row
from keyword_search import BM25Index
from pipeline import (CHAPTER_BLEND_WEIGHT, EMBEDDING_MODEL_NAME,
                      KEYWORD_WEIGHT, KURALS_PER_CHAPTER,
                      RERANK_CANDIDATE_COUNT, build_chapter_descriptions,
                      cached_vectors, searchable_text)
from rerank import (MULTILINGUAL_MODEL_NAME, Reranker, rerankable_text,
                    rerankable_text_with_tamil)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REWRITES_PATH = PROJECT_ROOT / "data" / "hyde_rewrites_sarvam.json"
BASELINE_PATH = PROJECT_ROOT / "data" / "reranker_bakeoff_results.json"
RESULTS_PATH = PROJECT_ROOT / "data" / "bge_bakeoff_results.json"
CHECKPOINT_PATH = PROJECT_ROOT / "data" / "bge_bakeoff_checkpoint.json"

CORPUS_MODE = "modern"
TOP_K = 5
BASELINE_LABEL = "A: L6 english (ships)"

# How many processor cores the model may use. 2 keeps the laptop cool and
# slow; the run survives being stopped either way, so slow is safe now.
MAX_THREADS = 2

# Scores hit the disk this often. A stop costs at most this many questions.
CHECKPOINT_EVERY = 10

ARMS = [
    ("E: bge english", rerankable_text),
    ("F: bge + tamil text", rerankable_text_with_tamil),
]


def main():
    kurals = json.load(open(PROJECT_ROOT / "data" / "kurals.json",
                            encoding="utf-8"))
    set_a, set_b = load_questions()
    all_questions = set_a + set_b
    split = len(set_a)
    with open(REWRITES_PATH, encoding="utf-8") as open_file:
        search_texts = json.load(open_file)
    with open(BASELINE_PATH, encoding="utf-8") as open_file:
        saved = json.load(open_file)[BASELINE_LABEL]
    baseline = {"top5": np.array(saved["top5"]),
                "rank1": np.array(saved["rank1"]),
                "ms": saved["ms_per_question"]}

    print("computing stage one once...")
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
    piles = [np.argsort(stage_one[index])[::-1][:RERANK_CANDIDATE_COUNT]
             for index in range(len(all_questions))]

    torch.set_num_threads(MAX_THREADS)
    print(f"loading {MULTILINGUAL_MODEL_NAME} (the slow part)...")
    print(f"capped at {MAX_THREADS} processor threads to keep the machine "
          f"cool")
    reranker = Reranker(MULTILINGUAL_MODEL_NAME)

    # Anything already scored by an earlier, interrupted run.
    checkpoint = {}
    if CHECKPOINT_PATH.exists():
        with open(CHECKPOINT_PATH, encoding="utf-8") as open_file:
            checkpoint = json.load(open_file)

    results = {BASELINE_LABEL: baseline}
    for label, build_text in ARMS:
        saved = checkpoint.get(label, {"top5": [], "rank1": [], "seconds": 0})
        top5 = list(saved["top5"])
        rank1 = list(saved["rank1"])
        rerank_seconds = saved["seconds"]
        if top5:
            print(f"{label}: resuming from question {len(top5) + 1}")
        else:
            print(f"scoring {label} over {len(all_questions)} questions...")

        arm_started = time.perf_counter()
        already_done = len(top5)
        for index in range(already_done, len(all_questions)):
            question, correct = all_questions[index]
            candidates = piles[index]
            started_at = time.perf_counter()
            logits = reranker.score_pairs(
                question, [kurals[p] for p in candidates],
                build_text=lambda record: build_text(record, CORPUS_MODE))
            rerank_seconds += time.perf_counter() - started_at
            best = candidates[np.argsort(logits)[::-1][:TOP_K]]
            top5.append(bool(any(kurals[p]["number"] in correct
                                 for p in best)))
            rank1.append(bool(kurals[best[0]]["number"] in correct))

            if (index + 1) % CHECKPOINT_EVERY == 0:
                checkpoint[label] = {"top5": top5, "rank1": rank1,
                                     "seconds": rerank_seconds}
                with open(CHECKPOINT_PATH, "w",
                          encoding="utf-8") as open_file:
                    json.dump(checkpoint, open_file)
                done_this_run = index + 1 - already_done
                pace = (time.perf_counter() - arm_started) / done_this_run
                print(f"  {index + 1}/{len(all_questions)}  saved  "
                      f"{pace:.1f}s per question  "
                      f"~{(len(all_questions) - index - 1) * pace / 60:.0f} "
                      f"min left in this arm", flush=True)

        checkpoint[label] = {"top5": top5, "rank1": rank1,
                             "seconds": rerank_seconds}
        with open(CHECKPOINT_PATH, "w", encoding="utf-8") as open_file:
            json.dump(checkpoint, open_file)
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
    print(f"{'arm':24s} {'Set A':>8s} {'Set B':>8s} {'all':>9s} "
          f"{'rank-1':>9s} {'ms':>8s}")
    for label in results:
        r = results[label]
        print(f"{label:24s} {int(r['top5'][:split].sum()):>4d}/100 "
              f"{int(r['top5'][split:].sum()):>4d}/133 "
              f"{int(r['top5'].sum()):>5d}/233 "
              f"{int(r['rank1'].sum()):>5d}/233 "
              f"{r['ms']:>8.0f}")

    print()
    print("IS ANY DIFFERENCE REAL? (McNemar's exact test, against arm A)")
    print("  It looks only at questions the two arms disagree on.")
    print("  p below 0.05 means a gap that lopsided is unlikely to be luck.")
    for label, _ in ARMS:
        for name, field in (("top-5", "top5"), ("rank-1", "rank1")):
            worse, better, p = mcnemar_exact(results[BASELINE_LABEL][field],
                                             results[label][field])
            print()
            print(f"  {label} vs A, {name}")
            print(f"    A right, this wrong : {worse}")
            print(f"    A wrong, this right : {better}")
            print(f"    p = {p:.4f}  -> "
                  + ("REAL" if p < 0.05 else "NOT ESTABLISHED"))


if __name__ == "__main__":
    main()
