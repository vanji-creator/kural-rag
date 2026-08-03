"""Can a smaller model do the rewriting, or does it only look like it can?

WHAT MAKES THIS A FAIR TEST

1. NEITHER MODEL CAN COPY ITS WAY TO A SCORE.
   The instruction in src/hyde_prompt.py teaches the format with examples about
   cars, code and plumbing. Nothing in it overlaps with Thirukkural's subjects,
   so no sentence in the prompt helps answer a question about anger, poverty or
   friendship. The previous prompt failed this: Qwen3-0.6B reproduced an anger
   example verbatim and scored for it.

2. BOTH MODELS GET THE IDENTICAL PROMPT.
   Comparing a model on one prompt against a model on another measures the
   prompts, not the models.

3. COPYING IS DETECTED, NOT ASSUMED ABSENT.
   Every output is checked against the example statements. Any match is
   reported rather than silently counted as a success.

4. THE JUDGE IS THE SCORECARD, NOT MY READING.
   233 questions, the full pipeline, and McNemar's test. Whether a rewrite
   "looks good" has already fooled us once today.

Speed is reported but is NOT the deciding number - this laptop has 8 cores and
the free host has 2, so timings here do not transfer.

Run it:

    venv/bin/python -u src/benchmark_models.py
"""

import json
import time
from pathlib import Path

import numpy as np
from huggingface_hub import hf_hub_download
from llama_cpp import Llama
from sentence_transformers import SentenceTransformer

from benchmark_chapters import load_questions, mcnemar_exact
from benchmark_hyde import score_with_queries
from hyde_prompt import EXAMPLE_STATEMENTS, INSTRUCTION, MAX_NEW_TOKENS
from keyword_search import BM25Index
from pipeline import (EMBEDDING_MODEL_NAME, build_chapter_descriptions,
                      searchable_text)
from rerank import RERANKER_MODEL_NAME, Reranker
from rewrite_query import rewrite as word_list_rewrite

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_PATH = PROJECT_ROOT / "data" / "hyde_rewrites_neutral.json"

CANDIDATES = [
    ("Qwen3-0.6B", "unsloth/Qwen3-0.6B-GGUF", "Qwen3-0.6B-BF16.gguf"),
    ("Qwen3-1.7B", "unsloth/Qwen3-1.7B-GGUF", "Qwen3-1.7B-BF16.gguf"),
]


def rewrite_all(label, repo, filename, questions, cache):
    """Rewrite every question with one model, caching results to disk."""
    if label in cache and len(cache[label]) == len(questions):
        print(f"{label}: using cached rewrites")
        return cache[label], 0.0

    path = hf_hub_download(repo, filename)
    model = Llama(model_path=path, n_ctx=768, n_threads=8, verbose=False)

    outputs = []
    started = time.perf_counter()
    for index, question in enumerate(questions, start=1):
        response = model.create_chat_completion(
            messages=[{"role": "system", "content": INSTRUCTION},
                      {"role": "user",
                       "content": f"question: {question} /no_think"}],
            max_tokens=MAX_NEW_TOKENS, temperature=0.0)
        text = response["choices"][0]["message"]["content"].strip()
        if "</think>" in text:
            text = text.split("</think>")[-1].strip()
        text = text.split("\n")[0].strip()
        if text.lower().startswith("statement:"):
            text = text[len("statement:"):].strip()
        outputs.append(text or question)
        if index % 25 == 0:
            per = (time.perf_counter() - started) / index
            print(f"  {label}: {index}/{len(questions)}  {per:.1f}s each")

    seconds = (time.perf_counter() - started) / len(questions)
    del model
    cache[label] = outputs
    with open(CACHE_PATH, "w", encoding="utf-8") as open_file:
        json.dump(cache, open_file, ensure_ascii=False, indent=2)
    return outputs, seconds


def copying_report(label, outputs):
    """Did this model pass by reproducing the prompt's examples?"""
    copied = [text for text in outputs
              if any(example.lower() in text.lower()
                     for example in EXAMPLE_STATEMENTS)]
    distinct = len(set(text.lower() for text in outputs))
    print(f"  {label}: {len(copied)} outputs copy a prompt example, "
          f"{distinct} distinct rewrites of {len(outputs)}")
    return len(copied)


def main():
    kurals = json.load(open(PROJECT_ROOT / "data" / "kurals.json",
                            encoding="utf-8"))
    set_a, set_b = load_questions()
    all_questions = set_a + set_b
    questions = [q for q, _ in all_questions]
    print(f"{len(questions)} questions, identical prompt for every model")

    cache = {}
    if CACHE_PATH.exists():
        with open(CACHE_PATH, encoding="utf-8") as open_file:
            cache = json.load(open_file)

    rewrites, speeds = {}, {}
    for label, repo, filename in CANDIDATES:
        rewrites[label], speeds[label] = rewrite_all(
            label, repo, filename, questions, cache)

    print()
    print("COPYING CHECK")
    for label in rewrites:
        copying_report(label, rewrites[label])

    print()
    print("SAME QUESTIONS, BOTH MODELS")
    for index in (0, 60, 140, 200):
        print(f"  Q     {questions[index]}")
        for label in rewrites:
            print(f"  {label:11s} {rewrites[label][index]}")
        print()

    model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    reranker = Reranker(RERANKER_MODEL_NAME)
    kural_texts = [searchable_text(record) for record in kurals]
    kural_vectors = model.encode(kural_texts, show_progress_bar=False)
    chapter_vectors = model.encode(build_chapter_descriptions(kurals),
                                   show_progress_bar=False)
    keyword_index = BM25Index(kural_texts)

    results = {}
    for label, texts in ([("word list", [word_list_rewrite(q)
                                         for q in questions])]
                         + [(k, v) for k, v in rewrites.items()]):
        print(f"scoring {label}...")
        results[label] = score_with_queries(
            texts, all_questions, kurals, model, reranker,
            kural_vectors, chapter_vectors, keyword_index)

    split = len(set_a)
    print()
    print("=" * 70)
    print(f"{'method':14s} {'set A':>9s} {'set B':>9s} {'all 233':>10s} "
          f"{'s/question':>12s}")
    print("=" * 70)
    for label, hits in results.items():
        print(f"{label:14s} {int(hits[:split].sum()):>6d}/100 "
              f"{int(hits[split:].sum()):>6d}/133 "
              f"{int(hits.sum()):>7d}/233 "
              f"{speeds.get(label, 0):>12.1f}")

    print()
    print("IS THE SMALL MODEL AS GOOD AS THE BIG ONE? (McNemar)")
    small, big = CANDIDATES[0][0], CANDIDATES[1][0]
    worse, better, p = mcnemar_exact(results[small], results[big])
    print(f"  {small} right, {big} wrong: {worse}")
    print(f"  {small} wrong, {big} right: {better}")
    print(f"  p = {p:.4f}  -> "
          + ("the two DIFFER" if p < 0.05
             else "no measurable difference between them"))


if __name__ == "__main__":
    main()
