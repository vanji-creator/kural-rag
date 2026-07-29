"""
Hunt for wrong-meaning records using embeddings — with a planted control.

THE PROBLEM
-----------
Kurals 524 and 870 carried another kural's Tamil meaning. We only found them
because they happened to be EXACT copies, and the text audit had a duplicate
check. A meaning that is merely wrong, without being copied verbatim, would be
invisible to all eleven checks in src/audit_corpus.py.

THE IDEA
--------
Every kural has an English explanation and a Tamil meaning that should say the
same thing. Embed both. Measure the angle between them. Where a record's two
arrows point in very different directions, the two texts are not saying the
same thing — which is exactly what a mis-assigned meaning looks like.

WHY THE CONTROL MATTERS
-----------------------
A detector nobody has tested is worth nothing. So before trusting any finding,
we deliberately BREAK known-good records and check whether the detector catches
them. If it cannot find errors we planted ourselves, its other findings mean
nothing.

We plant two kinds:
  1. the two historical errors, recreated exactly as they were
  2. a set of random swaps, to measure what fraction of planted errors is caught

WHY TWO MODELS
--------------
We also run the weak model we have been using so far, to see whether model
choice actually changes the outcome — rather than assuming it does.
"""

import json                                    # read the corpus
import random                                  # plant reproducible random errors
from pathlib import Path                       # file paths

import numpy as np                             # vector maths
from sentence_transformers import SentenceTransformer


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CORPUS_PATH = PROJECT_ROOT / "data" / "kurals.json"

# LaBSE is built for deciding "is text A a translation of text B", which is
# exactly the question this audit asks. MiniLM is what we have been using.
MODELS_TO_COMPARE = [
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "sentence-transformers/LaBSE",
]

NUMBER_OF_RANDOM_SWAPS = 20                    # extra planted errors
RANDOM_SEED = 20260729                         # fixed, so runs are repeatable

# The two errors we already found and fixed. We recreate them by copying the
# meaning of the kural whose text had wrongly ended up there.
HISTORICAL_ERRORS = {
    524: 468,      # kural 524 wrongly carried kural 468's meaning
    870: 810,      # kural 870 wrongly carried kural 810's meaning
}


def cosine_similarity_rowwise(first_matrix, second_matrix):
    """Cosine similarity between matching rows of two matrices.

    Same formula built by hand in Phase 0 — dot product divided by the two
    lengths — just applied to every row at once instead of one pair.
    """
    dot_products = np.sum(first_matrix * second_matrix, axis=1)
    first_lengths = np.linalg.norm(first_matrix, axis=1)
    second_lengths = np.linalg.norm(second_matrix, axis=1)
    return dot_products / (first_lengths * second_lengths)


# ---------------------------------------------------------------------------
# load the corpus and build the two sides of the comparison
# ---------------------------------------------------------------------------

kurals = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
meaning_by_number = {record["number"]: record["tamil_meaning_mu_varadarajan"]
                     for record in kurals}

english_texts = [record["english_explanation"] for record in kurals]
tamil_texts = [record["tamil_meaning_mu_varadarajan"] for record in kurals]
kural_numbers = [record["number"] for record in kurals]
position_of_number = {number: index for index, number in enumerate(kural_numbers)}


# ---------------------------------------------------------------------------
# plant the errors
# ---------------------------------------------------------------------------

planted_error_numbers = []

# 1. the two real historical errors, recreated
for damaged_number, source_number in HISTORICAL_ERRORS.items():
    tamil_texts[position_of_number[damaged_number]] = meaning_by_number[source_number]
    planted_error_numbers.append(damaged_number)

# 2. random swaps — take some kurals and rotate their meanings among themselves
random_generator = random.Random(RANDOM_SEED)
candidates = [n for n in kural_numbers if n not in HISTORICAL_ERRORS]
chosen_numbers = random_generator.sample(candidates, NUMBER_OF_RANDOM_SWAPS)

original_meanings = [meaning_by_number[n] for n in chosen_numbers]
rotated_meanings = original_meanings[1:] + original_meanings[:1]   # shift by one
for number, wrong_meaning in zip(chosen_numbers, rotated_meanings):
    tamil_texts[position_of_number[number]] = wrong_meaning
    planted_error_numbers.append(number)

planted_error_set = set(planted_error_numbers)
print(f"planted {len(planted_error_set)} errors "
      f"({len(HISTORICAL_ERRORS)} historical + {NUMBER_OF_RANDOM_SWAPS} random)")
print(f"into a corpus of {len(kurals)} kurals\n")


# ---------------------------------------------------------------------------
# run the detector once per model
# ---------------------------------------------------------------------------

for model_name in MODELS_TO_COMPARE:
    print("=" * 74)
    print("MODEL:", model_name)
    print("=" * 74)

    model = SentenceTransformer(model_name)
    dimensions = model.get_sentence_embedding_dimension()
    print("dimensions:", dimensions)

    # BOTH sides go through the SAME model — that rule still holds inside
    # a single comparison, even though this model differs from the one
    # retrieval will eventually use.
    english_embeddings = model.encode(english_texts, batch_size=32,
                                      show_progress_bar=False)
    tamil_embeddings = model.encode(tamil_texts, batch_size=32,
                                    show_progress_bar=False)

    similarity_scores = cosine_similarity_rowwise(english_embeddings, tamil_embeddings)

    # rank 1 = the LEAST similar pair = the most suspicious record
    order_most_suspicious_first = np.argsort(similarity_scores)
    rank_of_number = {kural_numbers[position]: rank + 1
                      for rank, position in enumerate(order_most_suspicious_first)}

    print(f"\nsimilarity distribution across all {len(kurals)} kurals:")
    for label, value in [
        ("lowest ", similarity_scores.min()),
        ("1st pct", np.percentile(similarity_scores, 1)),
        ("5th pct", np.percentile(similarity_scores, 5)),
        ("median ", np.median(similarity_scores)),
        ("highest", similarity_scores.max()),
    ]:
        print(f"   {label}: {value:.3f}")

    # --- did it catch what we planted ---
    print(f"\nthe two historical errors:")
    for damaged_number in HISTORICAL_ERRORS:
        position = position_of_number[damaged_number]
        print(f"   kural {damaged_number}: similarity {similarity_scores[position]:.3f}"
              f"   suspicion rank {rank_of_number[damaged_number]} of {len(kurals)}")

    print(f"\ncaught, out of {len(planted_error_set)} planted errors:")
    for cutoff in (22, 50, 100, 200):
        flagged = {kural_numbers[position]
                   for position in order_most_suspicious_first[:cutoff]}
        caught = len(flagged & planted_error_set)
        print(f"   in the {cutoff:4} most suspicious: {caught:3} / {len(planted_error_set)}"
              f"   ({caught / len(planted_error_set):.0%})")

    # --- the most suspicious records that we did NOT plant ---
    print("\n15 most suspicious records we did NOT plant "
          "(candidates for real, undiscovered errors):")
    shown = 0
    for position in order_most_suspicious_first:
        number = kural_numbers[position]
        if number in planted_error_set:
            continue
        print(f"   kural {number:4}  similarity {similarity_scores[position]:.3f}")
        shown += 1
        if shown >= 15:
            break
    print()
