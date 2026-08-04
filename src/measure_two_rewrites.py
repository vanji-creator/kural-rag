"""One question, two rewrites - one aimed at verses, one aimed at chapters.

THE PROBLEM

Every question is compared against two different kinds of text:

     133 chapter descriptions   ~44 words, a topic summary plus a word list
    1330 verse texts            ~47 words, a verse plus what it means

Today one rewrite is compared against both. It cannot be a good match for
both, because they are different shapes of writing. A verse says what happens
in one situation; a chapter description says what an area of life is about.

WHY THIS IS WORTH TRYING NOW

Reading the 8 questions the modern corpus fixed, every one was fixed the same
way: the right CHAPTER was found.

    "how do I stop being scared of speaking in public"
        old corpus  -> Evil Friendship, Power of Speech, Not Backbiting
        new corpus  -> three verses from "Not to dread the Council"

The chapter match is doing the work. So aim at it directly.

WHAT IS COMPARED

    one rewrite   what ships: the verse-shaped rewrite is used for BOTH the
                  verse score and the chapter score
    two rewrites  the verse-shaped rewrite scores verses; a chapter-shaped
                  rewrite scores chapters

Everything else is identical - same corpus, same weights, same reranker.

WHY THE RESULT WILL BE HARD TO READ, STATED IN ADVANCE

On Set A - the question set whose answer key we hand-checked - we are already
at 97 of 100. Three questions are left. A change that genuinely helps and a
change that does nothing will both come back "not established", because there
is not enough room left to tell them apart.

Set B has 133 questions and more room, but its answer key is one chapter per
question. Anything that improves chapter matching is rewarded by the way that
set was built, whether or not retrieval got better.

So neither set can settle this on its own. The honest reading will have to
combine three things: the number, whether the mechanism holds, and reading
the questions that changed.

Run it:

    venv/bin/python -u src/measure_two_rewrites.py
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
from pipeline import (EMBEDDING_MODEL_NAME, KEYWORD_WEIGHT,
                      KURALS_PER_CHAPTER, RERANK_CANDIDATE_COUNT,
                      build_chapter_descriptions, cached_vectors,
                      searchable_text)
from rerank import RERANKER_MODEL_NAME, Reranker, rerankable_text
from rewrite_hyde import tidy_reply

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VERSE_REWRITES = PROJECT_ROOT / "data" / "hyde_rewrites_sarvam.json"
CHAPTER_REWRITES = PROJECT_ROOT / "data" / "hyde_rewrites_chapter_prompt.json"
RESULTS_PATH = PROJECT_ROOT / "data" / "two_rewrite_results.json"

CORPUS_MODE = "modern"
TOP_K = 5

# Swept here rather than fixed, because the whole point of a chapter-shaped
# rewrite is that the chapter half should become more trustworthy. If it does,
# the best weight moves - and reading one weight would hide that.
BLENDS = (0.5, 0.6, 0.65, 0.7)


def get_chapter_rewrites(questions):
    """Rewrite every question as a subject-area description, cached to disk."""
    if CHAPTER_REWRITES.exists():
        with open(CHAPTER_REWRITES, encoding="utf-8") as open_file:
            cached = json.load(open_file)
        if len(cached) == len(questions):
            print(f"using {len(cached)} cached chapter-shaped rewrites")
            return cached

    model = HostedModel("sarvam")
    instruction = instruction_for("chapter")
    print(f"rewriting {len(questions)} questions, chapter-shaped...")

    partial = CHAPTER_REWRITES.with_suffix(".partial.json")
    rewrites = []
    if partial.exists():
        with open(partial, encoding="utf-8") as open_file:
            rewrites = json.load(open_file)
        print(f"  resuming from {len(rewrites)}")

    for index, question in enumerate(questions[len(rewrites):],
                                     start=len(rewrites) + 1):
        # 90 tokens, not 60: this one writes a sentence AND a word list.
        reply = model.ask(instruction, f"question: {question}",
                          max_output_tokens=90)
        rewrites.append(tidy_reply(reply, question))
        if index % 25 == 0:
            with open(partial, "w", encoding="utf-8") as open_file:
                json.dump(rewrites, open_file, ensure_ascii=False)
            print(f"  {index}/{len(questions)}  Rs {model.rupees_spent():.3f}")

    print(f"  done. {model.cost_report()}")
    with open(CHAPTER_REWRITES, "w", encoding="utf-8") as open_file:
        json.dump(rewrites, open_file, ensure_ascii=False, indent=2)
    partial.unlink(missing_ok=True)
    return rewrites


def main():
    kurals = json.load(open(PROJECT_ROOT / "data" / "kurals.json",
                            encoding="utf-8"))
    set_a, set_b = load_questions()
    all_questions = set_a + set_b
    split = len(set_a)
    questions = [question for question, _ in all_questions]

    with open(VERSE_REWRITES, encoding="utf-8") as open_file:
        verse_texts = json.load(open_file)
    chapter_texts = get_chapter_rewrites(questions)

    print()
    print("THE TWO REWRITES, SIDE BY SIDE")
    for index in (0, 60, 140, 200):
        print(f"  Q        {questions[index]}")
        print(f"  verse    {verse_texts[index]}")
        print(f"  chapter  {chapter_texts[index]}")
        print()

    print("loading the models...")
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    reranker = Reranker(RERANKER_MODEL_NAME)

    kural_texts = [searchable_text(record, CORPUS_MODE) for record in kurals]
    kural_vectors = cached_vectors(model, kural_texts, f"kurals_{CORPUS_MODE}")
    chapter_vectors = cached_vectors(
        model, build_chapter_descriptions(kurals), "chapters")
    keyword_index = BM25Index(kural_texts)

    verse_question_vectors = model.encode(verse_texts, show_progress_bar=False)
    chapter_question_vectors = model.encode(chapter_texts,
                                            show_progress_bar=False)
    keyword_scores = np.array([keyword_index.scores_for_query(text)
                               for text in verse_texts])

    verse_scores = verse_question_vectors @ kural_vectors.T
    chapter_from_verse = np.repeat(
        verse_question_vectors @ chapter_vectors.T, KURALS_PER_CHAPTER, axis=1)
    chapter_from_chapter = np.repeat(
        chapter_question_vectors @ chapter_vectors.T,
        KURALS_PER_CHAPTER, axis=1)

    def score(chapter_side, blend):
        """Rank with this chapter-score source at this blend."""
        blended = blend * chapter_side + (1 - blend) * verse_scores
        stage_one = (KEYWORD_WEIGHT * normalise_each_row(keyword_scores)
                     + (1 - KEYWORD_WEIGHT) * normalise_each_row(blended))
        found = []
        for index, (question, correct) in enumerate(all_questions):
            candidates = (np.argsort(stage_one[index])[::-1]
                          [:RERANK_CANDIDATE_COUNT])
            logits = reranker.score_pairs(
                question, [kurals[p] for p in candidates],
                build_text=lambda r: rerankable_text(r, CORPUS_MODE))
            best = candidates[np.argsort(logits)[::-1][:TOP_K]]
            found.append(any(kurals[p]["number"] in correct for p in best))
        return np.array(found)

    results = {}
    for label, chapter_side in (("one rewrite", chapter_from_verse),
                                ("two rewrites", chapter_from_chapter)):
        for blend in BLENDS:
            print(f"scoring {label}, blend {blend}...")
            results[(label, blend)] = score(chapter_side, blend)

    with open(RESULTS_PATH, "w", encoding="utf-8") as open_file:
        json.dump({f"{label} @ {blend}": [bool(h) for h in hits]
                   for (label, blend), hits in results.items()},
                  open_file, indent=2)

    print()
    print("=" * 70)
    print("A 'hit' is a question where a correct verse reached the top 5.")
    print("Set A answer keys include verses from other chapters - trustworthy.")
    print("Set B answer keys are one chapter only - rewards chapter matching.")
    print("=" * 70)
    print(f"{'method':14s} {'blend':>6s} {'Set A':>10s} {'Set B':>10s} "
          f"{'all 233':>10s}")
    for (label, blend), hits in results.items():
        print(f"{label:14s} {blend:>6.2f} "
              f"{int(hits[:split].sum()):>6d}/100 "
              f"{int(hits[split:].sum()):>6d}/133 "
              f"{int(hits.sum()):>7d}/233")

    baseline = results[("one rewrite", 0.5)]
    print()
    print("AGAINST WHAT SHIPS (one rewrite, blend 0.50), Set A only")
    print("  Set A is the half whose answer key cannot be gamed by chapter")
    print("  matching. Only 3 questions of room remain on it.")
    for (label, blend), hits in results.items():
        if (label, blend) == ("one rewrite", 0.5):
            continue
        worse, better, p = mcnemar_exact(baseline[:split], hits[:split])
        print(f"  {label:14s} @ {blend:.2f}   "
              f"lost {worse}, gained {better}, p = {p:.4f}"
              + ("  REAL" if p < 0.05 else ""))


if __name__ == "__main__":
    main()
