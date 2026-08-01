"""Phase 3 — question in, ranked kurals out. No LLM anywhere.

This is deliberately the NAIVE version. The similarity is computed in plain
Python, and the search is a plain for-loop over all 1330 kurals. There is no
FAISS, no vector database, and no numpy in the scoring path.

That is the point. Phase 6 will replace this loop with a real vector index,
and the only way to understand what the index bought us is to have felt the
loop first, and to have a measured time to compare against.

Run it:

    venv/bin/python src/retrieve.py "what does Thirukkural say about anger?"
"""

import json
import math
import sys
import time
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

# ----------------------------------------------------------------------
# where things live
# ----------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CORPUS_PATH = PROJECT_ROOT / "data" / "kurals.json"

# embedding 1330 texts takes minutes on a CPU. we do it once and keep the
# result on disk. .npy files are gitignored — they are regenerable.
VECTOR_CACHE_PATH = PROJECT_ROOT / "data" / "kural_vectors.npy"

# LaBSE gives 768 numbers per piece of text. It was trained so that a sentence
# and its translation land in nearly the same place, which is exactly what an
# English question searching Tamil verses needs.
MODEL_NAME = "sentence-transformers/LaBSE"

DEFAULT_TOP_K = 5


# ----------------------------------------------------------------------
# the similarity, by hand
# ----------------------------------------------------------------------

def cosine_similarity(first_vector, second_vector):
    """How close in DIRECTION are two arrows?

    Returns roughly:
        1.0   pointing the same way   -> same meaning
        0.0   at a right angle        -> unrelated
       -1.0   pointing opposite ways  -> rare in practice for text

    This is the formula derived by hand on paper in Phase 0:
    the dot product on top, divided by the two lengths.

    Dividing by the lengths is what makes it about DIRECTION only. Without
    it, a long piece of text would score higher than a short one just for
    being long, which has nothing to do with meaning.
    """
    dot_product = 0.0
    for first_value, second_value in zip(first_vector, second_vector):
        dot_product += first_value * second_value

    first_length = math.sqrt(sum(value * value for value in first_vector))
    second_length = math.sqrt(sum(value * value for value in second_vector))

    return dot_product / (first_length * second_length)


# ----------------------------------------------------------------------
# the searchable text
# ----------------------------------------------------------------------

def searchable_text(kural_record):
    """The one block of text we search for a given kural.

    Choosing this was the whole Phase 4 field comparison. Measured on 133
    chapter-name questions, precision@5 over the 1330 kurals:

        0.241   this combination (translation + explanation + Tamil meaning)
        0.205   english_translation alone
        0.171   english_explanation alone
        0.091   the Tamil verse itself
        0.012   the transliteration

    Two results worth remembering. The actual verse is one of the WORST
    things to search — it is compressed classical Tamil, and the model has
    barely seen text like it. And the Tamil prose meaning helps even though
    the question is in English, because the model is multilingual.
    """
    return (kural_record["english_translation"] + " "
            + kural_record["english_explanation"] + " "
            + kural_record["tamil_meaning_mu_varadarajan"])


# ----------------------------------------------------------------------
# loading
# ----------------------------------------------------------------------

def load_kurals():
    """Read the 1330 cleaned records built in Phase 1."""
    with open(CORPUS_PATH, encoding="utf-8") as corpus_file:
        return json.load(corpus_file)


def build_kural_vectors(model, kurals):
    """Turn every kural into 768 numbers, reusing the cache when possible.

    Cached as a numpy array purely because saving and loading 1330 lists of
    768 floats as JSON would be slow and huge. The SEARCH still uses plain
    Python — we hand plain lists to cosine_similarity below.
    """
    if VECTOR_CACHE_PATH.exists():
        print(f"loading cached vectors from {VECTOR_CACHE_PATH.name}")
        return np.load(VECTOR_CACHE_PATH)

    print(f"embedding {len(kurals)} kurals — this takes a few minutes, once")
    texts_to_embed = [searchable_text(kural_record) for kural_record in kurals]
    kural_vectors = model.encode(texts_to_embed, batch_size=16,
                                 show_progress_bar=True)

    np.save(VECTOR_CACHE_PATH, kural_vectors)
    print(f"saved to {VECTOR_CACHE_PATH.name}")
    return kural_vectors


# ----------------------------------------------------------------------
# the search itself — the naive loop
# ----------------------------------------------------------------------

def search(question, model, kurals, kural_vectors, top_k=DEFAULT_TOP_K):
    """Score the question against every single kural, then take the best few.

    No shortcuts. We genuinely compare against all 1330, one at a time.
    """
    question_vector = model.encode(question)

    # plain Python lists, so cosine_similarity is doing real Python work
    # rather than secretly falling through to a numpy fast path
    question_values = question_vector.tolist()

    scored_kurals = []
    for kural_record, kural_vector in zip(kurals, kural_vectors):
        score = cosine_similarity(question_values, kural_vector.tolist())
        scored_kurals.append((score, kural_record))

    # highest score first
    scored_kurals.sort(key=lambda pair: pair[0], reverse=True)

    return scored_kurals[:top_k]


def show_results(question, results):
    """Print the ranked kurals in a readable way."""
    print()
    print(f'question: "{question}"')
    print()
    for rank, (score, kural_record) in enumerate(results, start=1):
        print(f"  {rank}.  kural {kural_record['number']}"
              f"   score {score:.3f}"
              f"   [{kural_record['chapter_english']}]")
        print(f"      {kural_record['kural_line1']}")
        print(f"      {kural_record['kural_line2']}")
        print(f"      {kural_record['english_translation']}")
        print()


# ----------------------------------------------------------------------
# a number for Phase 6 to beat
# ----------------------------------------------------------------------

def compare_loop_against_numpy(question, model, kurals, kural_vectors):
    """Time the naive loop, then time the same answer computed with numpy.

    Both produce the SAME ranking. Only the speed differs. Phase 6 replaces
    the loop for real, and this is the baseline it has to improve on.
    """
    question_vector = model.encode(question)
    question_values = question_vector.tolist()

    loop_started = time.perf_counter()
    loop_scores = [cosine_similarity(question_values, kural_vector.tolist())
                   for kural_vector in kural_vectors]
    loop_seconds = time.perf_counter() - loop_started

    numpy_started = time.perf_counter()
    # scale every arrow to length 1, then a dot product IS the cosine
    unit_kural_vectors = kural_vectors / np.linalg.norm(kural_vectors, axis=1,
                                                        keepdims=True)
    unit_question_vector = question_vector / np.linalg.norm(question_vector)
    numpy_scores = unit_kural_vectors @ unit_question_vector
    numpy_seconds = time.perf_counter() - numpy_started

    largest_difference = float(np.max(np.abs(np.array(loop_scores) - numpy_scores)))

    print("timing one question against all 1330 kurals")
    print(f"  plain Python loop   {loop_seconds * 1000:8.1f} ms")
    print(f"  numpy               {numpy_seconds * 1000:8.1f} ms")
    print(f"  numpy is            {loop_seconds / numpy_seconds:8.1f}x faster")
    print(f"  biggest disagreement between the two: {largest_difference:.2e}")
    print()


# ----------------------------------------------------------------------

def main():
    question = (" ".join(sys.argv[1:])
                or "what does Thirukkural say about controlling anger?")

    kurals = load_kurals()
    model = SentenceTransformer(MODEL_NAME)
    kural_vectors = build_kural_vectors(model, kurals)

    compare_loop_against_numpy(question, model, kurals, kural_vectors)

    results = search(question, model, kurals, kural_vectors)
    show_results(question, results)


if __name__ == "__main__":
    main()
