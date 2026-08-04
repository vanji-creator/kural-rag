"""Freeze everything the Colab bake-off needs into plain data files.

WHY THE PILES ARE FROZEN HERE AND NOT RECOMPUTED THERE

Stage one is arithmetic over embedding vectors. A different machine computes
those vectors with tiny differences in the last decimal places, and one
verse at position 50 versus 51 is enough to change what the reranker is
given. Every arm of every bake-off so far reordered THE SAME piles - the
Colab arms must too, or the comparison is void. So the piles travel as data.

WHAT IS WRITTEN, into colab_bakeoff/data/

    piles.json     one entry per question: the question text, the correct
                   kural numbers, and the 50 candidate numbers in stage-one
                   order
    texts.json     for every kural number: the English text the reranker
                   reads, and the English+Tamil version
    baseline.json  arm A's per-question top-5 and rank-1 results, copied
                   from the saved bake-off

SELF-CHECK BEFORE WRITING

The piles are recomputed by the same code that fed every previous run, and
checked against two numbers already on the record: 214 questions reachable,
and arm A scoring 174/233 on these exact piles. If either check fails,
nothing is written.

Run it:

    venv/bin/python -u src/export_bakeoff_package.py
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
from rerank import rerankable_text, rerankable_text_with_tamil

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BASELINE_SOURCE = PROJECT_ROOT / "data" / "reranker_bakeoff_results.json"
PACKAGE_DATA = PROJECT_ROOT / "colab_bakeoff" / "data"

CORPUS_MODE = "modern"
BASELINE_LABEL = "A: L6 english (ships)"

# Facts already on the record that the frozen piles must reproduce.
EXPECTED_REACHABLE = 214
EXPECTED_BASELINE_TOP5 = 174


def main():
    kurals = json.load(open(PROJECT_ROOT / "data" / "kurals.json",
                            encoding="utf-8"))
    set_a, set_b = load_questions()
    all_questions = set_a + set_b
    with open(PROJECT_ROOT / "data" / "hyde_rewrites_sarvam.json",
              encoding="utf-8") as open_file:
        search_texts = json.load(open_file)

    print("computing stage one (the same code every bake-off used)...")
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

    print("freezing the piles...")
    piles = []
    for index, (question, correct) in enumerate(all_questions):
        candidate_positions = (np.argsort(stage_one[index])[::-1]
                               [:RERANK_CANDIDATE_COUNT])
        piles.append({
            "question": question,
            "correct": sorted(int(number) for number in correct),
            "pile": [int(kurals[p]["number"]) for p in candidate_positions],
        })

    # ---- self-check 1: the piles must show the known reachability -------
    reachable = sum(1 for entry in piles
                    if set(entry["pile"]) & set(entry["correct"]))
    print(f"  reachable questions in these piles: {reachable} "
          f"(expected {EXPECTED_REACHABLE})")
    if reachable != EXPECTED_REACHABLE:
        raise SystemExit("PILES DO NOT MATCH THE RECORD. Nothing written.")

    # ---- self-check 2: arm A's saved results must fit these piles -------
    with open(BASELINE_SOURCE, encoding="utf-8") as open_file:
        baseline = json.load(open_file)[BASELINE_LABEL]
    baseline_top5 = sum(baseline["top5"])
    print(f"  baseline arm A top-5 on these piles: {baseline_top5} "
          f"(expected {EXPECTED_BASELINE_TOP5})")
    if (len(baseline["top5"]) != len(piles)
            or baseline_top5 != EXPECTED_BASELINE_TOP5):
        raise SystemExit("BASELINE DOES NOT MATCH. Nothing written.")

    print("freezing the reranker texts...")
    texts = {}
    for record in kurals:
        texts[str(record["number"])] = {
            "english": rerankable_text(record, CORPUS_MODE),
            "with_tamil": rerankable_text_with_tamil(record, CORPUS_MODE),
        }

    PACKAGE_DATA.mkdir(parents=True, exist_ok=True)
    with open(PACKAGE_DATA / "piles.json", "w",
              encoding="utf-8") as open_file:
        json.dump({"set_a_size": len(set_a), "questions": piles},
                  open_file, ensure_ascii=False, indent=1)
    with open(PACKAGE_DATA / "texts.json", "w",
              encoding="utf-8") as open_file:
        json.dump(texts, open_file, ensure_ascii=False, indent=1)
    with open(PACKAGE_DATA / "baseline.json", "w",
              encoding="utf-8") as open_file:
        json.dump({"label": BASELINE_LABEL,
                   "top5": baseline["top5"],
                   "rank1": baseline["rank1"],
                   "ms_per_question": baseline["ms_per_question"]},
                  open_file, indent=1)

    for name in ("piles.json", "texts.json", "baseline.json"):
        size_kb = (PACKAGE_DATA / name).stat().st_size / 1024
        print(f"  wrote data/{name}  ({size_kb:.0f} KB)")
    print("package data frozen. Both self-checks passed.")


if __name__ == "__main__":
    main()
