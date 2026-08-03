"""Does modern English on the CORPUS side help, hurt, or do nothing?

THE HYPOTHESIS

Vikash, 2026-08-03: the English we search is 1880s English, LaBSE was trained
on modern English, so the question cannot reach the text.

WHAT IS COMPARED

Three versions of the text each kural is searched by. Everything else is held
identical - same questions, same chapter descriptions, same keyword weight,
same chapter blend, same reranker, same top-5 cut.

    classic   english_translation + the 1880s prose + tamil meaning
    modern    english_translation + Sarvam's rewrite + tamil meaning
    both      english_translation + BOTH proses + tamil meaning

`both` exists because of a specific worry. BM25 ranks on rare, specific
words. If the rewrite flattens "avarice" into "being greedy", keyword search
gets worse even where meaning search gets better. `both` keeps the old
vocabulary in the index and lets the scorecard say whether that matters.

WHAT THIS DELIBERATELY DOES NOT DO

It does not touch the HyDE prompt, which currently instructs the query
rewriter to produce "formal or old-fashioned words" - an instruction aimed
squarely at the classic text. Running modern text against that prompt is a
deliberate mismatch, and it will UNDERSELL the modern version.

That is on purpose. One change, one number. If the corpus text and the prompt
and the weights all moved together and the score went up, we would not know
which one earned it - and if it went down, we would not know which one to
undo. Re-tuning the prompt is the next experiment, not part of this one.

WHAT WOULD END THIS LINE OF WORK

If `classic` wins, the rewrite does not ship, CORPUS_TEXT_MODE stays
"classic", and the Rs 6 bought a recorded negative result. That is written
here in advance so it cannot be quietly reinterpreted afterwards.

Run it:

    venv/bin/python -u src/measure_corpus_text.py
"""

import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

from benchmark_chapters import load_questions, mcnemar_exact
from benchmark_hyde import score_with_queries
from keyword_search import BM25Index
from pipeline import (EMBEDDING_MODEL_NAME, build_chapter_descriptions,
                      load_modern_explanations, searchable_text)
from rerank import RERANKER_MODEL_NAME, Reranker

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SARVAM_REWRITES = PROJECT_ROOT / "data" / "hyde_rewrites_sarvam.json"
MODES = ("classic", "modern", "both")


def vocabulary_report(kurals):
    """How much rarer or blander did the text get?

    BM25 ranks a word by how rare it is across the corpus, so the SIZE of the
    vocabulary is not a curiosity - it is the raw material keyword search
    works from. A rewrite that says the same things in fewer distinct words
    has quietly taken away what BM25 ranks on.
    """
    print("VOCABULARY")
    print("  Key: 'distinct words' is how many different words appear across")
    print("  all 1330 texts. Fewer means blander, and BM25 has less to work")
    print("  with. 'avg words' is the length of one kural's search text.")
    print()
    print(f"  {'mode':10s} {'distinct words':>15s} {'avg words':>11s}")
    for mode in MODES:
        texts = [searchable_text(record, mode) for record in kurals]
        words = set()
        total = 0
        for text in texts:
            pieces = text.lower().split()
            words.update(pieces)
            total += len(pieces)
        print(f"  {mode:10s} {len(words):>15d} {total / len(texts):>11.1f}")
    print()


def main():
    kurals = json.load(open(PROJECT_ROOT / "data" / "kurals.json",
                            encoding="utf-8"))
    modern = load_modern_explanations()
    print(f"{len(modern)} of {len(kurals)} kurals have a modern rewrite")
    if len(modern) < len(kurals):
        print(f"  the other {len(kurals) - len(modern)} fall back to the "
              f"classic text, so this run UNDERSTATES the modern modes")
    print()

    set_a, set_b = load_questions()
    all_questions = set_a + set_b
    questions = [question for question, _ in all_questions]

    # The exact rewrites that produced 170/233. Re-fetching them would spend
    # money to receive strings we already have, and any drift in what the
    # provider returns would land in this measurement as if it were the
    # corpus change.
    with open(SARVAM_REWRITES, encoding="utf-8") as open_file:
        search_texts = json.load(open_file)
    if len(search_texts) != len(questions):
        raise SystemExit(f"{len(questions)} questions but "
                         f"{len(search_texts)} cached rewrites")

    vocabulary_report(kurals)

    print("loading the retrieval stack...")
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    reranker = Reranker(RERANKER_MODEL_NAME)
    chapter_vectors = model.encode(build_chapter_descriptions(kurals),
                                   show_progress_bar=False)

    results = {}
    for mode in MODES:
        print(f"scoring {mode}...")
        kural_texts = [searchable_text(record, mode) for record in kurals]
        kural_vectors = model.encode(kural_texts, show_progress_bar=False)
        keyword_index = BM25Index(kural_texts)
        results[mode] = score_with_queries(
            search_texts, all_questions, kurals, model, reranker,
            kural_vectors, chapter_vectors, keyword_index)

    split = len(set_a)
    print()
    print("=" * 68)
    print("A 'hit' means at least one correct verse landed in the top 5.")
    print("Set A is the hand-built golden 100 and is the better-made set.")
    print("=" * 68)
    print(f"{'corpus text':12s} {'set A':>10s} {'set B':>10s} {'all 233':>11s}")
    print("=" * 68)
    for mode in MODES:
        hits = results[mode]
        print(f"{mode:12s} {int(hits[:split].sum()):>6d}/100 "
              f"{int(hits[split:].sum()):>6d}/133 "
              f"{int(hits.sum()):>7d}/233")

    print()
    print("IS ANY DIFFERENCE REAL? (McNemar's exact test, all 233)")
    print("  It looks only at questions where the two versions disagree.")
    print("  p below 0.05 means a gap that lopsided is unlikely to be luck.")
    for mode in ("modern", "both"):
        worse, better, p = mcnemar_exact(results["classic"], results[mode])
        print()
        print(f"  {mode} vs classic")
        print(f"    classic right, {mode} wrong : {worse}")
        print(f"    classic wrong, {mode} right : {better}")
        print(f"    p = {p:.4f}  -> "
              + ("REAL" if p < 0.05 else "NOT ESTABLISHED - do not claim it"))

    best = max(MODES, key=lambda mode: int(results[mode].sum()))
    print()
    print("=" * 68)
    if best == "classic":
        print("CLASSIC WINS. The modern rewrite does not ship.")
        print("  Leave CORPUS_TEXT_MODE = \"classic\" in src/pipeline.py.")
        print("  This is a real result and it goes in LEARNING_LOG.md as one.")
    else:
        print(f"{best.upper()} scored highest at "
              f"{int(results[best].sum())}/233.")
        print("  Read the p value above before changing anything. A higher")
        print("  score that fails the test is a score, not a finding - the")
        print("  same wall that stopped us claiming Sarvam beat Qwen.")


if __name__ == "__main__":
    main()
