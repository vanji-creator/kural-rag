"""Re-tune the pipeline for a modern corpus, without fooling ourselves.

WHY THIS EXISTS

Every weight in this pipeline was swept against 1880s English. We then
rewrote the corpus into modern English and, unsurprisingly, the old settings
did not suit it: modern corpus + modern prompt scored 164/233 against a
baseline of 170.

That is not evidence the modern corpus is worse. It is evidence that the
settings around it were chosen for something else.

THE DANGER, STATED BEFORE ANY NUMBERS

There are five things to tune here. At four settings each that is over a
thousand combinations. Scored against 233 questions, some combination WILL
beat 170 by luck alone - and it will look exactly like a discovery.

This is the same trap as tuning a model on its own test set. The report comes
back excellent and the thing never reproduces.

THE GUARD

The 233 questions are split in half, ONCE, with a fixed seed:

    TUNE     117 questions - every sweep runs here, as often as we like
    CONFIRM  116 questions - looked at only at the very end, once

A setting that wins on TUNE and holds on CONFIRM is real. One that wins on
TUNE and collapses on CONFIRM was luck, and we will be able to see which.

The split is stratified across set A and set B, because those two have
differently-shaped answer keys - set B has exactly one correct chapter per
question by construction, set A has hand-checked correct verses from other
chapters too. An unbalanced split would tune for one shape of answer key.

WHAT IS SWEPT, IN ORDER OF EXPECTED SIZE

    1. chapter description text   the "modern words" field in each of the 133
                                  descriptions is a bridge TO archaic
                                  vocabulary. Against a modern corpus it may
                                  be a bridge to nowhere. This is half the
                                  meaning score, so it goes first.
    2. KEYWORD_WEIGHT             set to 0.3 when BM25 was being handed words
                                  like "miserliness" that appear in 0 kurals.
    3. CHAPTER_BLEND_WEIGHT       swept on old text.
    4. BM25 k and b               never swept on any text.

One at a time. Each sweep fixes the winner of the previous one, so every
number answers exactly one question.

Run it:

    venv/bin/python -u src/tune_modern.py --sweep chapters
    venv/bin/python -u src/tune_modern.py --sweep keyword
    venv/bin/python -u src/tune_modern.py --sweep blend
    venv/bin/python -u src/tune_modern.py --sweep bm25
    venv/bin/python -u src/tune_modern.py --confirm     # ONCE, at the end
"""

import json
import random
import sys
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

from benchmark_chapters import load_questions, mcnemar_exact
from evaluate import normalise_each_row
from keyword_search import BM25Index
from pipeline import (EMBEDDING_MODEL_NAME, KURALS_PER_CHAPTER, cached_vectors,
                      RERANK_CANDIDATE_COUNT, build_chapter_descriptions,
                      searchable_text)
from rerank import RERANKER_MODEL_NAME, Reranker, rerankable_text

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REWRITES_PATH = PROJECT_ROOT / "data" / "hyde_rewrites_indomain_prompt.json"
CHOICES_PATH = PROJECT_ROOT / "data" / "tuned_modern.json"
TOP_K = 5

# The corpus text being tuned for. Fixed for all of these sweeps.
CORPUS_MODE = "modern"

# Never changed. Changing it would mean the halves were drawn differently for
# different sweeps, and results could not be compared across them.
SPLIT_SEED = 20260804

# The settings we start from - what ships today, chosen for the old corpus.
STARTING_POINT = {
    "chapter_text": "topic+words",
    "keyword_weight": 0.3,
    "chapter_blend": 0.5,
    "bm25_saturation": 1.5,
    "bm25_length_penalty": 0.75,
}


def split_questions(all_questions, set_a_size):
    """Halve the questions, keeping set A and set B balanced in both halves.

    Stratified because the two sets have differently shaped answer keys. A
    split that put most of set B in one half would tune the pipeline for one
    kind of answer key and confirm it on another.
    """
    rng = random.Random(SPLIT_SEED)
    positions_a = list(range(set_a_size))
    positions_b = list(range(set_a_size, len(all_questions)))
    rng.shuffle(positions_a)
    rng.shuffle(positions_b)

    tune = sorted(positions_a[:len(positions_a) // 2]
                  + positions_b[:len(positions_b) // 2])
    confirm = sorted(positions_a[len(positions_a) // 2:]
                     + positions_b[len(positions_b) // 2:])
    return tune, confirm


class Scorer:
    """Holds the models and the corpus so a sweep can re-score cheaply.

    Loading LaBSE and the reranker takes about a minute. A sweep that reloaded
    them for every setting would spend its whole life loading.
    """

    def __init__(self, kurals, all_questions, search_texts):
        self.kurals = kurals
        self.all_questions = all_questions
        print(f"loading {EMBEDDING_MODEL_NAME}...")
        self.model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        print(f"loading {RERANKER_MODEL_NAME}...")
        self.reranker = Reranker(RERANKER_MODEL_NAME)

        print("embedding the corpus and the questions...")
        kural_texts = [searchable_text(record, CORPUS_MODE)
                       for record in kurals]
        self.kural_vectors = cached_vectors(self.model, kural_texts,
                                           f"kurals_{CORPUS_MODE}")
        self.question_vectors = self.model.encode(search_texts,
                                                  show_progress_bar=False)
        self.search_texts = search_texts

        # Chapter vectors and the keyword index depend on settings being
        # swept, so they are built on demand and remembered.
        self._chapter_vectors = {}
        self._keyword_indexes = {}
        self._keyword_scores = {}

    def chapter_vectors_for(self, chapter_text_mode):
        if chapter_text_mode not in self._chapter_vectors:
            descriptions = build_chapter_descriptions(self.kurals,
                                                      chapter_text_mode)
            self._chapter_vectors[chapter_text_mode] = cached_vectors(
                self.model, descriptions, f"chapters_{chapter_text_mode}")
        return self._chapter_vectors[chapter_text_mode]

    def keyword_scores_for(self, saturation, length_penalty):
        key = (saturation, length_penalty)
        if key not in self._keyword_scores:
            import keyword_search
            saved = (keyword_search.TERM_FREQUENCY_SATURATION,
                     keyword_search.LENGTH_PENALTY_STRENGTH)
            keyword_search.TERM_FREQUENCY_SATURATION = saturation
            keyword_search.LENGTH_PENALTY_STRENGTH = length_penalty
            index = BM25Index([searchable_text(record, CORPUS_MODE)
                               for record in self.kurals])
            self._keyword_scores[key] = np.array(
                [index.scores_for_query(text) for text in self.search_texts])
            (keyword_search.TERM_FREQUENCY_SATURATION,
             keyword_search.LENGTH_PENALTY_STRENGTH) = saved
        return self._keyword_scores[key]

    def score(self, settings, positions):
        """Hit/miss for these settings, over these question positions."""
        chapter_vectors = self.chapter_vectors_for(settings["chapter_text"])
        keyword_scores = self.keyword_scores_for(
            settings["bm25_saturation"], settings["bm25_length_penalty"])

        kural_scores = self.question_vectors @ self.kural_vectors.T
        handed_down = np.repeat(self.question_vectors @ chapter_vectors.T,
                                KURALS_PER_CHAPTER, axis=1)
        blended = (settings["chapter_blend"] * handed_down
                   + (1 - settings["chapter_blend"]) * kural_scores)
        stage_one = (settings["keyword_weight"]
                     * normalise_each_row(keyword_scores)
                     + (1 - settings["keyword_weight"])
                     * normalise_each_row(blended))

        found = []
        for position in positions:
            question, correct = self.all_questions[position]
            candidates = (np.argsort(stage_one[position])[::-1]
                          [:RERANK_CANDIDATE_COUNT])
            logits = self.reranker.score_pairs(
                question, [self.kurals[p] for p in candidates],
                build_text=lambda r: rerankable_text(r, CORPUS_MODE))
            best = candidates[np.argsort(logits)[::-1][:TOP_K]]
            found.append(any(self.kurals[p]["number"] in correct
                             for p in best))
        return np.array(found)


SWEEPS = {
    "chapters": ("chapter_text", ["topic", "topic+words", "all", "glued"]),
    "keyword": ("keyword_weight", [0.0, 0.2, 0.3, 0.4, 0.5]),
    # 0.0 is in here on purpose. It answers a question we have never asked:
    # what is the chapter signal worth AT ALL? The content sweep showed that
    # rearranging the description is worth about 1 question out of 116, so the
    # ceiling on any rewrite is set by how much the whole signal contributes.
    # Without this row we would be improving something without knowing its
    # maximum possible value.
    "blend": ("chapter_blend", [0.0, 0.3, 0.4, 0.5, 0.6, 0.7]),
    "bm25": ("bm25_length_penalty", [0.0, 0.4, 0.75, 1.0]),
}


def load_choices():
    """Settings chosen by earlier sweeps, or the starting point."""
    if CHOICES_PATH.exists():
        with open(CHOICES_PATH, encoding="utf-8") as open_file:
            return json.load(open_file)
    return dict(STARTING_POINT)


def main():
    arguments = sys.argv[1:]
    kurals = json.load(open(PROJECT_ROOT / "data" / "kurals.json",
                            encoding="utf-8"))
    set_a, set_b = load_questions()
    all_questions = set_a + set_b
    with open(REWRITES_PATH, encoding="utf-8") as open_file:
        search_texts = json.load(open_file)

    tune, confirm = split_questions(all_questions, len(set_a))
    print(f"{len(tune)} questions to tune on, {len(confirm)} held back")
    print(f"  (the held-back half is looked at ONCE, by --confirm)")
    print()

    settings = load_choices()
    scorer = Scorer(kurals, all_questions, search_texts)

    # ---- confirm: the one honest look at the held-back half -------------
    if "--confirm" in arguments:
        print("=" * 66)
        print("THE HELD-BACK HALF. This runs once.")
        print("=" * 66)
        for label, chosen in (("what ships today", STARTING_POINT),
                              ("tuned for modern", settings)):
            on_tune = scorer.score(chosen, tune)
            on_confirm = scorer.score(chosen, confirm)
            print(f"\n{label}")
            print(f"  settings   {chosen}")
            print(f"  tune half     {int(on_tune.sum())}/{len(tune)}")
            print(f"  CONFIRM half  {int(on_confirm.sum())}/{len(confirm)}")
        print()
        print("A gain that appears on the tune half and vanishes on the")
        print("confirm half was luck. Only a gain on BOTH is real.")
        return

    # ---- one sweep ------------------------------------------------------
    if "--sweep" not in arguments:
        raise SystemExit(f"pick one: --sweep {' | '.join(SWEEPS)}  or --confirm")
    name = arguments[arguments.index("--sweep") + 1]
    if name not in SWEEPS:
        raise SystemExit(f"unknown sweep {name!r}. known: {', '.join(SWEEPS)}")

    field, values = SWEEPS[name]
    print(f"sweeping {field} over {values}")
    print(f"everything else held at: "
          f"{ {k: v for k, v in settings.items() if k != field} }")
    print()

    scores = {}
    for value in values:
        trial = dict(settings, **{field: value})
        hits = scorer.score(trial, tune)
        scores[value] = int(hits.sum())
        marker = "  <- what ships today" if value == STARTING_POINT[field] else ""
        print(f"  {field} = {value!r:14s} {scores[value]:>4d}/{len(tune)}"
              f"{marker}")

    best_value = max(scores, key=lambda v: scores[v])
    print()
    if scores[best_value] <= scores.get(STARTING_POINT[field], -1):
        print(f"nothing beats the current {STARTING_POINT[field]!r}. Keeping it.")
        best_value = STARTING_POINT[field]
    else:
        print(f"best on the tune half: {field} = {best_value!r} "
              f"({scores[best_value]}/{len(tune)})")
        print("  NOT proven yet - it has only seen the tune half.")

    settings[field] = best_value
    with open(CHOICES_PATH, "w", encoding="utf-8") as open_file:
        json.dump(settings, open_file, indent=2)
    print(f"saved to {CHOICES_PATH.name}: {settings}")


if __name__ == "__main__":
    main()
