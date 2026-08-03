"""Is the hosted model's rewrite actually better, or does it just read better?

WHAT THIS DECIDES

Whether Sarvam-105B replaces the laptop model as the question rewriter.

Three methods go through the IDENTICAL pipeline - same corpus, same chapter
descriptions, same keyword weighting, same reranker, same top-5 cut. The only
thing that changes is the text we search with:

    word list      src/rewrite_query.py deletes a fixed list of question
                   words. Free, no model, and it sometimes destroys the
                   question outright ("should I spend time with people better
                   than me?" becomes "spend time"). Vikash has already
                   decided to drop it; it stays here as the floor to beat.

    Qwen3-1.7B     the model that ran on this laptop. 5.1 s per rewrite.
                   Already cached from 2026-08-02, not re-run.

    Sarvam-105B    hosted, 0.5 s per rewrite, about Rs 0.0012 each.

WHY THIS SCRIPT EXISTS SEPARATELY FROM benchmark_models.py

That one compares two LOCAL models and loads both into memory. This one
compares a hosted model against a cached local one, so it loads nothing and
spends about Rs 0.30.

WHAT WOULD END THIS LINE OF WORK

If Sarvam does not beat Qwen3-1.7B by a margin McNemar's test calls real,
there is no reason to move the rewriter off the laptop for QUALITY. Speed
would still argue for it, but that is a different argument and it must be
made honestly rather than smuggled in behind a number.

Run it:

    venv/bin/python -u src/benchmark_sarvam.py
"""

import json
import time
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

from benchmark_chapters import load_questions, mcnemar_exact
from benchmark_hyde import score_with_queries
from hyde_prompt import EXAMPLE_STATEMENTS, INSTRUCTION, MAX_NEW_TOKENS
from keyword_search import BM25Index
from llm import HostedModel
from pipeline import (EMBEDDING_MODEL_NAME, build_chapter_descriptions,
                      searchable_text)
from rerank import RERANKER_MODEL_NAME, Reranker
from rewrite_query import rewrite as word_list_rewrite
from smoke_test_llm import clean_reply

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOCAL_CACHE_PATH = PROJECT_ROOT / "data" / "hyde_rewrites_neutral.json"
SARVAM_CACHE_PATH = PROJECT_ROOT / "data" / "hyde_rewrites_sarvam.json"
LOCAL_MODEL_NAME = "Qwen3-1.7B"


def fetch_sarvam_rewrites(questions):
    """Rewrite every question with the hosted model, caching to disk.

    Cached because the rewrites cost money and never change - temperature is
    0, so the same question gives the same answer on every run. Re-fetching
    them would spend rupees to learn nothing.
    """
    if SARVAM_CACHE_PATH.exists():
        with open(SARVAM_CACHE_PATH, encoding="utf-8") as open_file:
            cached = json.load(open_file)
        if len(cached) == len(questions):
            print(f"using {len(cached)} cached Sarvam rewrites")
            return cached

    model = HostedModel("sarvam")
    print(f"fetching {len(questions)} rewrites from "
          f"{model.settings['model']}...")

    rewrites = []
    started_at = time.perf_counter()
    for index, question in enumerate(questions, start=1):
        reply = model.ask(INSTRUCTION, f"question: {question}",
                          max_output_tokens=MAX_NEW_TOKENS)
        rewrites.append(clean_reply(reply, question))
        if index % 25 == 0:
            per = (time.perf_counter() - started_at) / index
            print(f"  {index}/{len(questions)}  {per:.2f}s each, "
                  f"Rs {model.rupees_spent():.3f} so far")

    print(f"  done. {model.cost_report()}")
    with open(SARVAM_CACHE_PATH, "w", encoding="utf-8") as open_file:
        json.dump(rewrites, open_file, ensure_ascii=False, indent=2)
    return rewrites


def copying_report(label, rewrites):
    """Did this model score by parroting the examples inside the prompt?

    The instruction in src/hyde_prompt.py uses examples about cars, code and
    plumbing precisely so that copying them cannot help with Thirukkural. A
    model that reproduces them is mimicking a format, not understanding a
    question, and we found out the hard way that an automatic word-match
    check cannot tell those two apart.
    """
    copied = sum(1 for text in rewrites
                 if any(example.lower() in text.lower()
                        for example in EXAMPLE_STATEMENTS))
    unchanged = sum(1 for text, question in zip(rewrites, QUESTIONS_FOR_CHECK)
                    if text.strip().lower() == question.strip().lower())
    distinct = len({text.lower() for text in rewrites})
    print(f"  {label:14s} copied-example {copied:3d}   "
          f"handed-back-unchanged {unchanged:3d}   "
          f"distinct {distinct:3d}/{len(rewrites)}")


def main():
    global QUESTIONS_FOR_CHECK

    kurals = json.load(open(PROJECT_ROOT / "data" / "kurals.json",
                            encoding="utf-8"))
    set_a, set_b = load_questions()
    all_questions = set_a + set_b
    questions = [question for question, _ in all_questions]
    QUESTIONS_FOR_CHECK = questions
    print(f"{len(questions)} questions "
          f"({len(set_a)} golden + {len(set_b)} per-chapter)")

    sarvam_rewrites = fetch_sarvam_rewrites(questions)

    with open(LOCAL_CACHE_PATH, encoding="utf-8") as open_file:
        local_rewrites = json.load(open_file)[LOCAL_MODEL_NAME]

    methods = {
        "word list": [word_list_rewrite(question) for question in questions],
        LOCAL_MODEL_NAME: local_rewrites,
        "Sarvam-105B": sarvam_rewrites,
    }

    print()
    print("HONESTY CHECKS (a rewrite that copies or gives up is not a rewrite)")
    for label, rewrites in methods.items():
        copying_report(label, rewrites)

    print()
    print("THE SAME QUESTIONS, ALL THREE METHODS")
    for index in (0, 60, 140, 200):
        print(f"  Q            {questions[index]}")
        for label, rewrites in methods.items():
            print(f"  {label:13s}{rewrites[index]}")
        print()

    print("loading the retrieval stack...")
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    reranker = Reranker(RERANKER_MODEL_NAME)
    kural_texts = [searchable_text(record) for record in kurals]
    kural_vectors = model.encode(kural_texts, show_progress_bar=False)
    chapter_vectors = model.encode(build_chapter_descriptions(kurals),
                                   show_progress_bar=False)
    keyword_index = BM25Index(kural_texts)

    results = {}
    for label, rewrites in methods.items():
        print(f"scoring {label}...")
        results[label] = score_with_queries(
            rewrites, all_questions, kurals, model, reranker,
            kural_vectors, chapter_vectors, keyword_index)

    # ---- the scorecard -------------------------------------------------
    # A "hit" means at least one correct kural landed in the top 5. Set A is
    # the hand-built golden set and is the better-made of the two. Set B has
    # one question per chapter and its answer key is single-chapter, which
    # structurally favours methods that lean on the chapter signal - so a win
    # on B alone is weaker evidence than a win on A.
    split = len(set_a)
    print()
    print("=" * 68)
    print(f"{'method':14s} {'set A':>10s} {'set B':>10s} {'all 233':>11s}")
    print("=" * 68)
    for label, hits in results.items():
        print(f"{label:14s} {int(hits[:split].sum()):>6d}/100 "
              f"{int(hits[split:].sum()):>6d}/133 "
              f"{int(hits.sum()):>7d}/233")

    print()
    print("IS THE DIFFERENCE REAL? (McNemar's exact test, all 233)")
    print("  It looks ONLY at questions where the two methods disagree.")
    print("  p below 0.05 means a gap this lopsided is unlikely to be luck.")
    for other in ("word list", LOCAL_MODEL_NAME):
        worse, better, p = mcnemar_exact(results[other], results["Sarvam-105B"])
        print()
        print(f"  Sarvam-105B vs {other}")
        print(f"    {other} right, Sarvam wrong : {worse}")
        print(f"    {other} wrong, Sarvam right : {better}")
        print(f"    p = {p:.4f}  -> "
              + ("REAL" if p < 0.05 else "NOT ESTABLISHED - do not claim it"))


if __name__ == "__main__":
    main()
