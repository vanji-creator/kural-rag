"""Phase 5 - the scorecard. Turns opinions into one number.

Before this file existed, "did that change help?" was answered by looking at
five results for one topic and forming a view. That is guessing.

This runs all 100 golden questions through every method we have and reports,
for each, how often a genuinely correct kural showed up in the top 5.
One number per method. Changes either move it or they don't.

Run it:

    venv/bin/python src/evaluate.py
"""

import json
import sys
import time
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

from keyword_search import BM25Index
# Everything below comes from pipeline.py on purpose. That file is the single
# definition of how a question is answered; importing the constants means this
# harness cannot drift away from what the app actually serves.
from pipeline import (CHAPTER_BLEND_WEIGHT, EMBEDDING_MODEL_NAME,
                      KEYWORD_WEIGHT, KURALS_PER_CHAPTER,
                      RERANK_CANDIDATE_COUNT, KuralRetriever,
                      build_chapter_descriptions, normalise, searchable_text)
from rerank import (DEFAULT_CANDIDATE_COUNT, MULTILINGUAL_MODEL_NAME,
                    RERANKER_MODEL_NAME, Reranker, rerankable_text,
                    rerankable_text_with_tamil)
from rewrite_query import rewrite

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CORPUS_PATH = PROJECT_ROOT / "data" / "kurals.json"
GOLDEN_SET_PATH = PROJECT_ROOT / "data" / "golden_set.json"

MODEL_NAME = EMBEDDING_MODEL_NAME
TOP_K = 5


def load_json_file(path):
    """Read one JSON file from disk."""
    with open(path, encoding="utf-8") as open_file:
        return json.load(open_file)


def correct_kural_numbers_for(question_entry):
    """Every kural number that counts as a right answer for this question.

    Two sources, added together:
      1. every kural in the question's own chapters (10 each)
      2. the hand-checked kurals that sit in OTHER chapters but still answer it

    Source 2 is what stops the scorecard punishing a retriever for being
    right - e.g. kural 35 genuinely answers the anger question even though
    it lives in chapter 4, not chapter 31.
    """
    correct_numbers = set()
    for chapter_number in question_entry["correct_chapters"]:
        first_kural_in_chapter = (chapter_number - 1) * KURALS_PER_CHAPTER + 1
        for offset in range(KURALS_PER_CHAPTER):
            correct_numbers.add(first_kural_in_chapter + offset)
    correct_numbers.update(question_entry["correct_extra_kurals"])
    return correct_numbers


def normalise_each_row(score_table):
    """Squash every question's scores onto a 0-to-1 scale.

    Needed because the two methods speak different units. Cosine similarity
    runs about 0.0 to 0.5. BM25 runs about 0 to 20. Adding them raw would let
    BM25 drown out the embeddings completely.

    Rescaling per question - not over the whole table - is deliberate: it means
    "the best match FOR THIS QUESTION" is always 1.0, so a question the model
    is generally unsure about still contributes a full-strength opinion.
    """
    row_minimums = score_table.min(axis=1, keepdims=True)
    row_maximums = score_table.max(axis=1, keepdims=True)
    row_ranges = row_maximums - row_minimums
    # A flat row would divide by zero. Never happens here, but guard anyway.
    row_ranges[row_ranges == 0] = 1.0
    return (score_table - row_minimums) / row_ranges


def reciprocal_rank_fusion(list_of_score_tables, rank_softener=60):
    """Combine methods by RANK instead of by score.

    The alternative to rescaling. Instead of asking "how high did each method
    score this kural", ask "what POSITION did each method put it in", and give
    1/(60 + position) for each. A kural placed 2nd by both methods beats one
    placed 1st by a single method and 900th by the other.

    Being rank-based, it does not care that the two methods use different
    units at all - so nothing has to be rescaled and no weight has to be
    chosen. This is what most production hybrid search actually uses.

    The 60 is the standard value from the original paper. It stops the very
    top rank from dominating everything below it.
    """
    fused_scores = np.zeros_like(list_of_score_tables[0])
    for score_table in list_of_score_tables:
        # argsort twice turns scores into positions: 0 for the best, 1 next...
        descending_order = np.argsort(-score_table, axis=1)
        positions = np.argsort(descending_order, axis=1)
        fused_scores += 1.0 / (rank_softener + positions + 1)
    return fused_scores


def score_one_method(all_question_scores, kurals, golden_questions):
    """Grade one method.

    all_question_scores: a 100 x 1330 table. One row per question, one score
    per kural. Every method must produce this same shape so the numbers are
    directly comparable.
    """
    questions_with_a_hit = 0
    total_correct_in_top_k = 0
    ranks_of_first_correct = []

    for question_index, question_entry in enumerate(golden_questions):
        correct_numbers = correct_kural_numbers_for(question_entry)
        best_positions = np.argsort(all_question_scores[question_index])[::-1]

        top_k_numbers = [kurals[position]["number"]
                         for position in best_positions[:TOP_K]]
        correct_hits = [number for number in top_k_numbers
                        if number in correct_numbers]

        if correct_hits:
            questions_with_a_hit += 1
        total_correct_in_top_k += len(correct_hits)

        # Where did the FIRST correct answer land in the full ranking?
        # This says how far off we were when we missed, not just that we did.
        for rank, position in enumerate(best_positions, start=1):
            if kurals[position]["number"] in correct_numbers:
                ranks_of_first_correct.append(rank)
                break

    question_count = len(golden_questions)
    # MRR - mean reciprocal rank. For each question take 1/(rank of the first
    # correct verse), then average. First place scores 1.0, second 0.5, tenth
    # 0.1. It rewards being right at the TOP, not merely being right somewhere,
    # which is what matters when a reader only looks at the first result.
    reciprocal_ranks = [1.0 / rank for rank in ranks_of_first_correct]
    return {
        "hits": questions_with_a_hit,
        "avg_correct_in_top_k": total_correct_in_top_k / question_count,
        "median_first_rank": int(np.median(ranks_of_first_correct)),
        "mrr": sum(reciprocal_ranks) / question_count,
    }


def main():
    kurals = load_json_file(CORPUS_PATH)
    golden_questions = load_json_file(GOLDEN_SET_PATH)
    print(f"{len(kurals)} kurals, {len(golden_questions)} golden questions")

    model = SentenceTransformer(MODEL_NAME)

    print("embedding the corpus...")
    kural_vectors = model.encode(
        [searchable_text(record) for record in kurals],
        show_progress_bar=False)

    print("embedding the chapter descriptions...")
    chapter_vectors = model.encode(build_chapter_descriptions(kurals),
                                   show_progress_bar=False)

    print("embedding the questions...")
    question_vectors = model.encode(
        [entry["question"] for entry in golden_questions],
        show_progress_bar=False)

    # LaBSE vectors already have length 1, so a dot product IS cosine.
    # 100 questions x 1330 kurals, in one matrix multiply.
    kural_level_scores = question_vectors @ kural_vectors.T

    # 100 questions x 133 chapters, then each chapter's score is handed down
    # to all 10 of its kurals so both tables end up 100 x 1330 and can be
    # compared - and blended - directly.
    chapter_level_scores = question_vectors @ chapter_vectors.T
    handed_down_scores = np.repeat(chapter_level_scores,
                                   KURALS_PER_CHAPTER, axis=1)

    # The blend knob. weight 0.0 is pure kural, weight 1.0 is pure chapter.
    # 0.5 measured best last run; keep the neighbours so we can see the shape.
    best_blend_weight = CHAPTER_BLEND_WEIGHT
    blended_scores = (best_blend_weight * handed_down_scores
                      + (1 - best_blend_weight) * kural_level_scores)

    print("building the BM25 keyword index...")
    keyword_index = BM25Index([searchable_text(record)
                               for record in kurals])
    keyword_scores = np.array([
        keyword_index.scores_for_query(entry["question"])
        for entry in golden_questions])

    methods = [
        ("kural only (BASELINE)", kural_level_scores),
        ("chapter only", handed_down_scores),
        (f"blend  chapter={best_blend_weight:.1f}", blended_scores),
        ("keyword only (BM25)", keyword_scores),
    ]

    # Hybrid, way 1: rescale both to 0-1 and add with a weight.
    normalised_meaning = normalise_each_row(blended_scores)
    normalised_keyword = normalise_each_row(keyword_scores)
    for keyword_weight in [0.2, 0.3, 0.5, 0.7]:
        hybrid_scores = (keyword_weight * normalised_keyword
                         + (1 - keyword_weight) * normalised_meaning)
        methods.append((f"hybrid rescaled kw={keyword_weight:.1f}",
                        hybrid_scores))

    # Hybrid, way 2: combine by rank instead. No weight to choose.
    methods.append(("hybrid RRF (rank-based)",
                    reciprocal_rank_fusion([blended_scores, keyword_scores])))

    # ------------------------------------------------------------------
    # Everything above, but with the QUESTION rewritten first.
    # Only the question side changes. The corpus and the scoring are
    # untouched, so any movement is caused by the rewrite and nothing else.
    # ------------------------------------------------------------------
    print("re-running everything with rewritten questions...")
    rewritten_questions = [rewrite(entry["question"])
                           for entry in golden_questions]
    rewritten_vectors = model.encode(rewritten_questions,
                                     show_progress_bar=False)

    rewritten_kural_scores = rewritten_vectors @ kural_vectors.T
    rewritten_chapter_scores = np.repeat(
        rewritten_vectors @ chapter_vectors.T, KURALS_PER_CHAPTER, axis=1)
    rewritten_blend = (best_blend_weight * rewritten_chapter_scores
                       + (1 - best_blend_weight) * rewritten_kural_scores)
    rewritten_keyword_scores = np.array([
        keyword_index.scores_for_query(question)
        for question in rewritten_questions])

    methods.append(("REWRITE kural only", rewritten_kural_scores))
    methods.append((f"REWRITE blend={best_blend_weight:.1f}", rewritten_blend))
    methods.append(("REWRITE keyword only", rewritten_keyword_scores))

    rewritten_normalised_meaning = normalise_each_row(rewritten_blend)
    rewritten_normalised_keyword = normalise_each_row(rewritten_keyword_scores)
    for keyword_weight in [0.3, 0.5]:
        methods.append((
            f"REWRITE hybrid kw={keyword_weight:.1f}",
            keyword_weight * rewritten_normalised_keyword
            + (1 - keyword_weight) * rewritten_normalised_meaning))

    methods.append(("REWRITE hybrid RRF",
                    reciprocal_rank_fusion([rewritten_blend,
                                            rewritten_keyword_scores])))

    # ------------------------------------------------------------------
    # LLM rewrites, read from disk.
    #
    # WARNING - these were written by an LLM that had the chapter list in
    # front of it, so some rewrites echo the correct chapter's title. That is
    # leakage. Treat these rows as an optimistic CEILING, not a fair score.
    # ------------------------------------------------------------------
    llm_rewrite_file = load_json_file(PROJECT_ROOT / "data"
                                      / "llm_rewrites.json")
    llm_rewrite_lookup = llm_rewrite_file["rewrites"]
    llm_rewritten = [llm_rewrite_lookup[entry["question"]]
                     for entry in golden_questions]

    print("re-running everything with LLM rewrites...")
    llm_vectors = model.encode(llm_rewritten, show_progress_bar=False)
    llm_kural_scores = llm_vectors @ kural_vectors.T
    llm_chapter_scores = np.repeat(llm_vectors @ chapter_vectors.T,
                                   KURALS_PER_CHAPTER, axis=1)
    llm_blend = (best_blend_weight * llm_chapter_scores
                 + (1 - best_blend_weight) * llm_kural_scores)
    llm_keyword_scores = np.array([keyword_index.scores_for_query(question)
                                   for question in llm_rewritten])

    methods.append(("LLM* kural only", llm_kural_scores))
    methods.append((f"LLM* blend={best_blend_weight:.1f}", llm_blend))
    methods.append(("LLM* keyword only", llm_keyword_scores))
    for keyword_weight in [0.3, 0.5]:
        methods.append((
            f"LLM* hybrid kw={keyword_weight:.1f}",
            keyword_weight * normalise_each_row(llm_keyword_scores)
            + (1 - keyword_weight) * normalise_each_row(llm_blend)))

    # ------------------------------------------------------------------
    # STAGE 2 - rerank the top candidates from our best honest stage 1.
    # ------------------------------------------------------------------
    stage_one_scores = (0.3 * rewritten_normalised_keyword
                        + 0.7 * rewritten_normalised_meaning)

    def run_reranker(label, reranker, build_text):
        """Rerank every question's top candidates and time it.

        Everything not in the candidate list keeps its -1e9 and can never
        reach the top 5. That is the point: a reranker only REORDERS.
        """
        reranked_scores = np.full_like(stage_one_scores, -1e9)
        total_seconds = 0.0
        for question_index, question_entry in enumerate(golden_questions):
            candidate_positions = np.argsort(
                stage_one_scores[question_index])[::-1][:RERANK_CANDIDATE_COUNT]
            candidate_records = [kurals[position]
                                 for position in candidate_positions]

            started_at = time.time()
            pair_scores = reranker.score_pairs(question_entry["question"],
                                               candidate_records,
                                               build_text=build_text)
            total_seconds += time.time() - started_at

            for candidate_index, position in enumerate(candidate_positions):
                reranked_scores[question_index][position] = \
                    pair_scores[candidate_index]

        milliseconds = total_seconds / len(golden_questions) * 1000
        print(f"  {label}: {milliseconds:.0f} ms per question")
        methods.append((label, reranked_scores))

    print(f"reranking {RERANK_CANDIDATE_COUNT} candidates x "
          f"{len(golden_questions)} questions...")

    english_reranker = Reranker(RERANKER_MODEL_NAME)
    run_reranker("RERANK en-only top-50", english_reranker, rerankable_text)

    # The multilingual challenger, measured two ways so the model change and
    # the text change are separated. If only the second row moves, Tamil is
    # what mattered. If both move together, the model is what mattered.
    # The multilingual reranker was measured and REJECTED: 91 of 100 for 24x
    # the latency (11,840 ms per question against 498 ms), and the Tamil
    # variant cost another 5.6 seconds to gain exactly nothing. Running it
    # again takes about 40 minutes, so it is off unless asked for. The code
    # stays so the claim can be re-checked rather than taken on trust.
    if "--full" in sys.argv:
        multilingual_reranker = Reranker(MULTILINGUAL_MODEL_NAME,
                                         max_length=1024)
        run_reranker("RERANK bge en-only", multilingual_reranker,
                     rerankable_text)
        run_reranker("RERANK bge en+tamil", multilingual_reranker,
                     rerankable_text_with_tamil)
    else:
        print("  (skipping the rejected multilingual reranker; "
              "pass --full to include it)")

    # ------------------------------------------------------------------
    # THE ONE THAT MATTERS: the actual production pipeline, end to end.
    #
    # Every row above is this harness reimplementing the steps in batched
    # form. This row calls src/pipeline.py itself - the same object the web
    # service holds - so it measures what a user really gets, not a
    # description of it. If this disagrees with "RERANK en-only top-50",
    # production and the harness have drifted and one of them is wrong.
    # ------------------------------------------------------------------
    print("running the production pipeline end to end...")
    retriever = KuralRetriever(use_reranker=True)

    production_scores = np.zeros_like(stage_one_scores)
    production_seconds = 0.0
    for question_index, question_entry in enumerate(golden_questions):
        started_at = time.time()
        ranking_scores, _, _, _ = retriever.rank_everything(
            question_entry["question"])
        production_seconds += time.time() - started_at
        production_scores[question_index] = ranking_scores

    print(f"  pipeline.py: "
          f"{production_seconds / len(golden_questions) * 1000:.0f} ms "
          f"per question")
    methods.append(("PIPELINE (what ships)", production_scores))

    print()
    print("=" * 70)
    print(f"{'method':26s} {'hits/100':>9s} {'avg in top5':>12s} "
          f"{'median rank':>12s} {'MRR':>7s}")
    print("=" * 78)
    for method_name, all_question_scores in methods:
        result = score_one_method(all_question_scores, kurals, golden_questions)
        print(f"{method_name:26s} {result['hits']:9d} "
              f"{result['avg_correct_in_top_k']:12.2f} "
              f"{result['median_first_rank']:12d} "
              f"{result['mrr']:7.3f}")


if __name__ == "__main__":
    main()
