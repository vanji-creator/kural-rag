"""Now that the WHOLE pipeline can speak modern English, does it help?

WHY THE FIRST MEASUREMENT DID NOT COUNT

src/measure_corpus_text.py compared three versions of the corpus text and got
170, 173, 174 out of 233 - a spread well inside luck, p = 0.66 and p = 0.48.

The audit afterwards found why. Two parts of the pipeline read the 1880s
English directly and ignored the switch:

    src/rerank.py     the reranker, which picks the final 5 out of 50
    src/hyde_prompt.py  which told the query rewriter to produce
                        "formal or old-fashioned words"

So that run changed stage one, then handed its candidates to a reranker still
reading Victorian prose, using questions deliberately steered toward Victorian
vocabulary. It measured a mismatch, not a hypothesis.

Both are fixed. This runs the comparison that was intended.

WHAT IS COMPARED

Four combinations. Everything else - the corpus, the questions, the chapter
descriptions, the weights, the candidate count - is identical throughout.

    corpus text     what stage one AND the reranker read
    prompt          what the query rewriter is told to reach for

    1. classic + classic prompt   what ships today, 170/233
    2. modern  + classic prompt   corpus moved, question left behind
    3. modern  + modern prompt    both ends moved together
    4. both    + modern prompt    modern text, old vocabulary still indexed

Row 2 is included on purpose even though we expect it to be poor. It is the
control that shows how much of any gain comes from moving BOTH ends rather
than one - and it is the row the previous measurement was accidentally
reporting.

COST

Rows 3 and 4 need the 233 questions rewritten under the modern prompt: 233
calls, about Rs 0.30, cached forever afterwards. Rows 1 and 2 reuse the
rewrites already on disk and cost nothing.

WHAT WOULD END THIS LINE OF WORK

If row 1 still wins, the modern corpus does not ship. CORPUS_TEXT_MODE and
PROMPT_MODE both stay "classic", and the whole exercise is recorded as a
measured negative. That is written here before the run so it cannot be
quietly reinterpreted after it.

Run it:

    venv/bin/python -u src/measure_modern_stack.py
"""

import json
import time
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

from benchmark_chapters import load_questions, mcnemar_exact
from evaluate import normalise_each_row
from hyde_prompt import MAX_NEW_TOKENS, instruction_for
from keyword_search import BM25Index
from llm import HostedModel
from pipeline import (CHAPTER_BLEND_WEIGHT, EMBEDDING_MODEL_NAME,
                      cached_vectors,
                      KEYWORD_WEIGHT, KURALS_PER_CHAPTER,
                      RERANK_CANDIDATE_COUNT, build_chapter_descriptions,
                      searchable_text)
from rerank import RERANKER_MODEL_NAME, Reranker, rerankable_text
from rewrite_hyde import tidy_reply

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLASSIC_REWRITES = PROJECT_ROOT / "data" / "hyde_rewrites_sarvam.json"
REWRITE_FILES = {
    "modern": PROJECT_ROOT / "data" / "hyde_rewrites_modern_prompt.json",
    "in-domain": PROJECT_ROOT / "data" / "hyde_rewrites_indomain_prompt.json",
}
TOP_K = 5

# (label, corpus mode, prompt mode)
COMBINATIONS = [
    ("classic + classic prompt", "classic", "classic"),
    ("modern  + classic prompt", "modern", "classic"),
    ("modern  + modern prompt", "modern", "modern"),
    ("both    + modern prompt", "both", "modern"),
    # Vikash's suggestion: teach the rewriter with examples from THIS book's
    # world instead of cars and plumbing. Added after the modern prompt was
    # seen drifting into self-help language - "recognizing the trigger,
    # pausing before reacting" for a question about anger, which is nowhere
    # in the corpus in any version.
    ("modern  + in-domain prompt", "modern", "in-domain"),
    ("both    + in-domain prompt", "both", "in-domain"),
]


def get_rewrites(questions, prompt_mode):
    """Rewrite every question under one prompt, cached to disk."""
    path = REWRITE_FILES[prompt_mode]
    if path.exists():
        with open(path, encoding="utf-8") as open_file:
            cached = json.load(open_file)
        if len(cached) == len(questions):
            print(f"using {len(cached)} cached {prompt_mode}-prompt rewrites")
            return cached

    model = HostedModel("sarvam")
    instruction = instruction_for(prompt_mode)
    print(f"rewriting {len(questions)} questions, {prompt_mode} prompt...")

    # Resume from a part-finished file. The first attempt at this crashed on
    # a rate limit at question 100 and lost all 100, because it only wrote at
    # the end. Rewrites cost money; a crash should cost the one in flight.
    partial_path = path.with_suffix(".partial.json")
    rewrites = []
    if partial_path.exists():
        with open(partial_path, encoding="utf-8") as open_file:
            rewrites = json.load(open_file)
        print(f"  resuming from {len(rewrites)} already written")

    started_at = time.perf_counter()
    for index, question in enumerate(questions[len(rewrites):],
                                     start=len(rewrites) + 1):
        reply = model.ask(instruction, f"question: {question}",
                          max_output_tokens=MAX_NEW_TOKENS)
        rewrites.append(tidy_reply(reply, question))
        if index % 25 == 0:
            with open(partial_path, "w", encoding="utf-8") as open_file:
                json.dump(rewrites, open_file, ensure_ascii=False)
            print(f"  {index}/{len(questions)}  "
                  f"Rs {model.rupees_spent():.3f}")
    print(f"  done. {model.cost_report()}")

    with open(path, "w", encoding="utf-8") as open_file:
        json.dump(rewrites, open_file, ensure_ascii=False, indent=2)
    partial_path.unlink(missing_ok=True)
    return rewrites


def score_combination(search_texts, all_questions, kurals, model, reranker,
                      corpus_mode):
    """Run the whole pipeline with this corpus mode. Returns hit/miss.

    Everything here mirrors KuralRetriever.rank_everything exactly, with the
    corpus mode threaded through BOTH halves - the vectors and keyword index
    that stage one uses, and the text the reranker reads. Missing the second
    of those is what made the previous measurement meaningless.
    """
    # Cached on disk, keyed by a fingerprint of the model name and every text.
    # Without this every run re-embedded 1330 verses for three minutes to get
    # numbers identical to the last run's.
    kural_texts = [searchable_text(record, corpus_mode) for record in kurals]
    kural_vectors = cached_vectors(model, kural_texts, f"kurals_{corpus_mode}")
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

    found = []
    for index, (original_question, correct) in enumerate(all_questions):
        candidates = np.argsort(stage_one[index])[::-1][:RERANK_CANDIDATE_COUNT]
        # The reranker reads the ORIGINAL question - it sees both texts
        # together, so the full sentence helps it - but the kural text it is
        # shown now follows the corpus mode.
        logits = reranker.score_pairs(
            original_question, [kurals[p] for p in candidates],
            build_text=lambda record: rerankable_text(record, corpus_mode))
        best = candidates[np.argsort(logits)[::-1][:TOP_K]]
        found.append(any(kurals[p]["number"] in correct for p in best))
    return np.array(found)


def main():
    kurals = json.load(open(PROJECT_ROOT / "data" / "kurals.json",
                            encoding="utf-8"))
    set_a, set_b = load_questions()
    all_questions = set_a + set_b
    questions = [question for question, _ in all_questions]

    with open(CLASSIC_REWRITES, encoding="utf-8") as open_file:
        classic_rewrites = json.load(open_file)
    rewrites_by_prompt = {"classic": classic_rewrites}
    for prompt_mode in ("modern", "in-domain"):
        rewrites_by_prompt[prompt_mode] = get_rewrites(questions, prompt_mode)

    print()
    print("THE SAME QUESTIONS UNDER ALL THREE PROMPTS")
    for index in (0, 60, 140, 200):
        print(f"  Q          {questions[index]}")
        for prompt_mode in ("classic", "modern", "in-domain"):
            print(f"  {prompt_mode:10s} "
                  f"{rewrites_by_prompt[prompt_mode][index]}")
        print()

    print("loading the retrieval stack...")
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    reranker = Reranker(RERANKER_MODEL_NAME)

    results = {}
    for label, corpus_mode, prompt_mode in COMBINATIONS:
        print(f"scoring {label}...")
        results[label] = score_combination(
            rewrites_by_prompt[prompt_mode], all_questions, kurals, model,
            reranker, corpus_mode)

    # Keep the per-question hit/miss, not just the totals.
    #
    # The first run of this saved only the six totals. The moment the table
    # raised a follow-up question - is the Set A jump from 90 to 97 real? -
    # answering it needed another hour of scoring, because the arrays that
    # McNemar's test reads had been thrown away. An experiment that cannot be
    # re-questioned without re-running is an experiment half kept.
    results_path = PROJECT_ROOT / "data" / "modern_stack_results.json"
    with open(results_path, "w", encoding="utf-8") as open_file:
        json.dump({label: [bool(hit) for hit in hits]
                   for label, hits in results.items()},
                  open_file, indent=2)
    print(f"per-question results saved to {results_path.name}")

    split = len(set_a)
    baseline = COMBINATIONS[0][0]
    print()
    print("=" * 72)
    print("A 'hit' means at least one correct verse landed in the top 5.")
    print("Set A is the hand-built golden 100 and is the better-made set.")
    print("=" * 72)
    print(f"{'combination':26s} {'set A':>9s} {'set B':>9s} {'all 233':>10s}")
    print("=" * 72)
    for label, _, _ in COMBINATIONS:
        hits = results[label]
        print(f"{label:26s} {int(hits[:split].sum()):>5d}/100 "
              f"{int(hits[split:].sum()):>5d}/133 "
              f"{int(hits.sum()):>6d}/233")

    print()
    print("IS ANY DIFFERENCE REAL? (McNemar's exact test, against row 1)")
    for label, _, _ in COMBINATIONS[1:]:
        worse, better, p = mcnemar_exact(results[baseline], results[label])
        print()
        print(f"  {label} vs {baseline}")
        print(f"    baseline right, this wrong : {worse}")
        print(f"    baseline wrong, this right : {better}")
        print(f"    p = {p:.4f}  -> "
              + ("REAL" if p < 0.05 else "NOT ESTABLISHED - do not claim it"))

    best = max(results, key=lambda label: int(results[label].sum()))
    print()
    print("=" * 72)
    if best == baseline:
        print("WHAT SHIPS TODAY STILL WINS.")
        print("  Leave CORPUS_TEXT_MODE and PROMPT_MODE on \"classic\".")
        print("  Record it in LEARNING_LOG.md as a measured negative result.")
    else:
        print(f"HIGHEST: {best} at {int(results[best].sum())}/233")
        print("  Change nothing until the p value above says REAL.")


if __name__ == "__main__":
    main()
