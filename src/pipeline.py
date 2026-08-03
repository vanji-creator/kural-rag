"""The production retriever. One question in, ranked kurals out.

THIS IS THE ONLY DEFINITION OF HOW A QUESTION IS ANSWERED.

`evaluate.py` imports from here and scores it. `service/app.py` imports from
here and serves it. If the two ever had separate copies of this arithmetic they
would drift, and the measured number would quietly stop describing the thing
users actually get.

Every constant below is a measured decision, not a guess. The number beside it
is what it earned on the 100-question golden set in data/golden_set.json:

    starting point, plain embedding search over kurals          44 / 100
    + rewrite the question (strip "how do I my")                 69
    + blend in the chapter signal at weight 0.5                  +3
    + BM25 keyword search alongside, weight 0.3                  75
    + rerank the top 50 with a cross-encoder                     85
    + hand-written chapter descriptions instead of glued text    90

Set A is close to finished. When stage one hands 50 candidates to the
reranker, only 94 of those 100 questions have a correct kural in the pile at
all, so 90 is 90 out of a reachable 94. Further gains have to come from stage
one, not from anything downstream of it.

The wider 233-question set is where the rewriter was chosen. Same pipeline
throughout, only the rewrite changed:

    word list, strip 111 words (src/rewrite_query.py)          144 / 233
    Qwen3-1.7B running on this laptop                          155 / 233
    Sarvam-105B over the internet                              170 / 233

Sarvam beats the word list with p = 0.0000 - settled. Against the local model
p = 0.0534, just the wrong side of the line, so it is NOT proven better than
Qwen and nothing here claims it is. It ships because the local model needs
about 100 seconds per question on a real host and this needs half a second.

Two of those look obvious and are not:

  - chapter weight 0.5 is right; 0.8 measured WORSE THAN NOTHING (42 against a
    44 baseline). An earlier test said 0.8 was best, but that test defined
    "correct" as "in the right chapter", which is exactly what chapter scores
    optimise for. It was grading its own homework.

  - BM25 was worth ZERO before the rewrite (52 -> 52) and six points after it
    (69 -> 75). Two methods that make the same mistake cannot cover for each
    other; stripping the question words is what made them fail differently.

Run it directly:

    venv/bin/python src/pipeline.py "how do I control my anger?"
"""

import hashlib
import json
import re
import sys
import time
from collections import OrderedDict
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

from keyword_search import BM25Index
from rerank import (RERANKER_MODEL_NAME, Reranker, rerankable_text)
from rewrite_hyde import (REWRITER_FAILED, REWRITER_SKIPPED_TAMIL,
                          HydeRewriter)

# ----------------------------------------------------------------------
# where things live
# ----------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CORPUS_PATH = PROJECT_ROOT / "data" / "kurals.json"

# Embedding 1330 texts takes minutes on a CPU, so the result is kept on disk.
# The .meta.json beside it records WHAT was embedded - see load_or_build_vectors
# for why a cache without that is dangerous.
KURAL_VECTOR_CACHE = PROJECT_ROOT / "data" / "kural_vectors.npy"
CHAPTER_VECTOR_CACHE = PROJECT_ROOT / "data" / "chapter_vectors.npy"

# LaBSE turns text into 768 numbers. It was trained so a sentence and its
# translation land in nearly the same place, which is what lets an English
# question find a Tamil verse at all.
EMBEDDING_MODEL_NAME = "sentence-transformers/LaBSE"

# ----------------------------------------------------------------------
# the measured configuration
# ----------------------------------------------------------------------

KURALS_PER_CHAPTER = 10

# How much of the final meaning-score comes from the CHAPTER rather than the
# kural. 0.0 is kural only, 1.0 is chapter only. Measured: 0.5 best at 52,
# 0.8 at 42, chapter-only at 33.
CHAPTER_BLEND_WEIGHT = 0.5

# How much of the final stage-1 score comes from keyword matching rather than
# meaning. Measured: 0.3 best at 75, 0.5 at 67, 0.7 at 49.
KEYWORD_WEIGHT = 0.3

# How many candidates stage 1 hands to the reranker. A reranker can only
# REORDER what it is given, so this sets a hard ceiling. Measured ceilings:
# top-5 75, top-10 85, top-20 88, top-50 94, top-100 99, top-200 99 (flat).
# 50 is the knee of that curve.
RERANK_CANDIDATE_COUNT = 50

DEFAULT_TOP_K = 5

# Repeating a question should not cost another 500 ms of reranking.
QUERY_CACHE_SIZE = 256

# Tamil script occupies one contiguous block of Unicode.
TAMIL_SCRIPT = re.compile(r"[஀-௿]")

# ----------------------------------------------------------------------
# confidence — measured, never assumed
# ----------------------------------------------------------------------
#
# These are set by src/calibrate.py and MUST NOT be edited by hand. Until that
# script shows the top score separates questions the book answers from
# questions it does not, this stays False and the interface is forbidden from
# refusing or from claiming confidence.
#
# The placeholder engine failed exactly this test: "who won the football world
# cup" scored 0.847 while "is it wrong to eat meat" scored 0.283. A threshold
# chosen without measuring would have been decoration.
SCORES_ARE_CALIBRATED = False

# Unreachable while uncalibrated, so "high" can never be claimed.
HIGH_CONFIDENCE_SCORE = 1.01
# Only "did anything come back at all", not a judgement about relevance.
REFUSAL_FLOOR = 0.0


def confidence_for(top_score):
    """high / low / none, honestly.

    While SCORES_ARE_CALIBRATED is False this can only ever say "low": the
    engine ranks well inside one question, but its absolute number carries no
    information about whether Thirukkural addresses the question at all.
    """
    if SCORES_ARE_CALIBRATED and top_score >= HIGH_CONFIDENCE_SCORE:
        return "high"
    if top_score > REFUSAL_FLOOR:
        return "low"
    return "none"


ENGINE_NAME = "Sarvam HyDE + LaBSE + BM25 + cross-encoder rerank"
ENGINE_DESCRIPTION = (
    "Rewrites the question into the vocabulary the verses use with "
    "Sarvam-105B, scores every verse by meaning and by keyword, blends in the "
    "chapter signal, then rereads the top 50 against the original question "
    "with a cross-encoder. Measured at 90 of 100 on a hand-built English "
    "question set, and 170 of 233 on the wider set."
)


# ----------------------------------------------------------------------
# what text we search
# ----------------------------------------------------------------------

MODERN_EXPLANATIONS_PATH = (PROJECT_ROOT / "data"
                            / "modern_explanations.jsonl")

# Which English prose to search each kural by.
#
#   "classic"  the 1880s translation prose the corpus shipped with
#   "modern"   Sarvam's plain-modern-English rewrite instead of it
#   "both"     both, so the archaic vocabulary stays in the keyword index
#
# THIS IS THE ROLLBACK SWITCH. Setting it back to "classic" restores the
# behaviour measured at 170/233 with no files moved and nothing regenerated.
CORPUS_TEXT_MODE = "classic"

_modern_explanations = None


def load_modern_explanations():
    """The plain-modern-English rewrite of each kural, or {} if absent.

    Read once and kept, because searchable_text is called 1330 times per
    process and re-reading a file that often would dominate startup.
    """
    global _modern_explanations
    if _modern_explanations is not None:
        return _modern_explanations

    _modern_explanations = {}
    if MODERN_EXPLANATIONS_PATH.exists():
        with open(MODERN_EXPLANATIONS_PATH, encoding="utf-8") as open_file:
            for line in open_file:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue      # a line cut short by a killed process
                _modern_explanations[entry["number"]] = entry["modern"]
    return _modern_explanations


def searchable_text(kural_record, mode=None):
    """The one block of text a kural is searched by.

    Measured in Phase 4 against the alternatives - the actual Tamil verse
    scored 0.091 and the transliteration 0.012, both far worse. Compressed
    classical Tamil is one of the WORST things to search: the model has barely
    seen text like it.

    The English prose here is the thing under test as of 2026-08-03. What the
    corpus ships with is 1880s English:

        (A) pleasing (object) to his foes is he who reads not moral works...

    LaBSE was trained on modern text, so a modern question has to reach across
    that gap. HyDE already moves the QUESTION toward the book's vocabulary;
    the modern mode moves the BOOK toward the question's. Which of them
    actually helps is decided by src/measure_corpus_text.py, not here.

    Falls back to the classic text for any kural with no rewrite yet, so a
    half-finished rewrite file degrades one verse at a time instead of
    crashing.

    (src/retrieve.py has an identical copy of the classic version on purpose.
    That file is a frozen teaching artifact - the naive Phase 3 loop - and is
    deliberately self-contained rather than importing from production code.)
    """
    mode = mode or CORPUS_TEXT_MODE
    modern = load_modern_explanations().get(kural_record["number"], "")

    if mode == "modern" and modern:
        prose = modern
    elif mode == "both" and modern:
        prose = kural_record["english_explanation"] + " " + modern
    else:
        prose = kural_record["english_explanation"]

    return (kural_record["english_translation"] + " "
            + prose + " "
            + kural_record["tamil_meaning_mu_varadarajan"])


CHAPTER_DESCRIPTIONS_PATH = PROJECT_ROOT / "data" / "chapter_descriptions.json"

# Which parts of a hand-written chapter description to actually use.
#
#   "glued"        the old stand-in: the chapter's 10 English explanations
#                  concatenated. Not a description at all - the chapter's own
#                  text repeated. This is the baseline to beat.
#   "topic"        the hand-written 2-3 sentence summary.
#   "topic+words"  plus the modern vocabulary bridge. The corpus says sloth,
#                  a reader says lazy - this is where "lazy" gets written in.
#   "all"          plus questions the chapter answers.
#
# The last one is NOT trustworthy and must not be reported as a clean result.
# The questions were written by an author who had already seen the golden set
# in conversation; 121 verbatim copies were found and stripped, but paraphrase
# leakage cannot be stripped. Treat "all" as an optimistic ceiling only.
CHAPTER_TEXT_MODE = "topic+words"


def load_chapter_descriptions():
    """Read the hand-written descriptions, or None if they are not there."""
    if not CHAPTER_DESCRIPTIONS_PATH.exists():
        return None
    with open(CHAPTER_DESCRIPTIONS_PATH, encoding="utf-8") as open_file:
        return json.load(open_file)


def build_chapter_descriptions(kurals, mode=None):
    """One block of text per chapter, in chapter order.

    Falls back to the glued stand-in if the hand-written file is missing, so
    nothing breaks if data/chapter_descriptions.json is deleted.
    """
    mode = mode or CHAPTER_TEXT_MODE

    def glued(chapter_index):
        chapter_start = chapter_index * KURALS_PER_CHAPTER
        block = kurals[chapter_start:chapter_start + KURALS_PER_CHAPTER]
        return " ".join(record["english_explanation"] for record in block)

    chapter_count = len(kurals) // KURALS_PER_CHAPTER
    if mode == "glued":
        return [glued(index) for index in range(chapter_count)]

    written = load_chapter_descriptions()
    if written is None:
        return [glued(index) for index in range(chapter_count)]

    descriptions = []
    for index in range(chapter_count):
        entry = written[str(index + 1)]
        parts = [entry["topic"]]
        if mode in ("topic+words", "all"):
            parts.append(entry["modern_words"])
        if mode == "all":
            parts.extend(entry["questions_clean"])
        descriptions.append(" ".join(parts))
    return descriptions


# ----------------------------------------------------------------------
# combining scores that speak different units
# ----------------------------------------------------------------------

def normalise(scores):
    """Squash one question's scores onto a 0-to-1 scale.

    Needed because the two methods speak different units. Cosine similarity
    runs about 0.0 to 0.5; BM25 runs about 0 to 20. Added raw, BM25 would
    drown the embeddings out completely.
    """
    lowest = float(np.min(scores))
    highest = float(np.max(scores))
    if highest == lowest:
        # every kural scored identically - no opinion to express
        return np.zeros_like(scores)
    return (scores - lowest) / (highest - lowest)


def looks_like_tamil_script(text):
    """True when the text contains Tamil letters."""
    return bool(TAMIL_SCRIPT.search(text))


# ----------------------------------------------------------------------
# loading, with a cache that knows what it holds
# ----------------------------------------------------------------------

def load_kurals():
    """Read the 1330 cleaned records built in Phase 1."""
    with open(CORPUS_PATH, encoding="utf-8") as corpus_file:
        return json.load(corpus_file)


def fingerprint(model_name, texts):
    """A short string that changes if the model OR the text changes.

    This is what makes the vector cache safe. A cache keyed to nothing is a
    silent-wrong-answer machine: edit the corpus or swap the model, and the
    stale .npy keeps being loaded with no error anywhere. Nothing in the
    scorecard would catch it either - the numbers would just quietly be about
    a corpus that no longer exists.
    """
    digest = hashlib.sha256()
    digest.update(model_name.encode("utf-8"))
    for text in texts:
        digest.update(text.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()[:16]


def load_or_build_vectors(model, texts, cache_path, label):
    """Embed these texts, reusing the cache only if it holds the same thing."""
    meta_path = cache_path.with_suffix(".meta.json")
    wanted = fingerprint(EMBEDDING_MODEL_NAME, texts)

    if cache_path.exists() and meta_path.exists():
        with open(meta_path, encoding="utf-8") as meta_file:
            stored = json.load(meta_file)
        if stored.get("fingerprint") == wanted:
            return np.load(cache_path)
        print(f"  {label}: cache is stale, rebuilding")

    print(f"  {label}: embedding {len(texts)} texts (this is the slow part)")
    vectors = model.encode(texts, batch_size=16, show_progress_bar=False)
    np.save(cache_path, vectors)
    with open(meta_path, "w", encoding="utf-8") as meta_file:
        json.dump({"fingerprint": wanted,
                   "model": EMBEDDING_MODEL_NAME,
                   "count": len(texts)}, meta_file, indent=2)
    return vectors


# ----------------------------------------------------------------------
# the retriever
# ----------------------------------------------------------------------

class KuralRetriever:
    """Loads every model ONCE. One instance serves every request.

    Loading LaBSE takes seconds and about a gigabyte of memory, so a process
    that built this per request would be unusable. That single fact is why
    there is a long-running Python service rather than a script the web app
    shells out to.
    """

    def __init__(self, use_reranker=True, use_rewriter=True):
        self.kurals = load_kurals()
        self.use_reranker = use_reranker

        # The only part of this pipeline that leaves the machine. If the key
        # is missing the whole retriever would refuse to start, which would
        # take the site down over an optional improvement - so a missing key
        # degrades to searching the question as typed, loudly.
        self.rewriter = None
        if use_rewriter:
            try:
                self.rewriter = HydeRewriter()
                print(f"rewriter ready: "
                      f"{self.rewriter.model_name}, "
                      f"{len(self.rewriter.cache)} rewrites already cached")
            except Exception as error:
                print(f"NO REWRITER: {error}")
                print("  searches will use the question as typed. Measured "
                      "cost of that: 170/233 becomes about 144/233.")

        print(f"loading {EMBEDDING_MODEL_NAME}...")
        self.embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)

        kural_texts = [searchable_text(record) for record in self.kurals]
        self.kural_vectors = load_or_build_vectors(
            self.embedding_model, kural_texts, KURAL_VECTOR_CACHE, "kurals")
        self.chapter_vectors = load_or_build_vectors(
            self.embedding_model, build_chapter_descriptions(self.kurals),
            CHAPTER_VECTOR_CACHE, "chapters")

        print("building the BM25 keyword index...")
        self.keyword_index = BM25Index(kural_texts)

        self.reranker = None
        if use_reranker:
            print(f"loading {RERANKER_MODEL_NAME}...")
            self.reranker = Reranker(RERANKER_MODEL_NAME)

        # question text -> finished results, most recently used last
        self.query_cache = OrderedDict()
        # Filled in by rank_everything on every search, read by search().
        self.last_timing_ms = {}
        print("retriever ready")

    # ------------------------------------------------------------------

    def stage_one_scores(self, search_text):
        """Score all 1330 kurals cheaply. Returns one number per kural.

        Three signals combined, in the order they were measured into the
        pipeline. Everything here compares FROZEN vectors - each kural was
        turned into numbers before any question existed - which is what makes
        it fast enough to run over the whole corpus.
        """
        question_vector = self.embedding_model.encode(search_text)

        # LaBSE returns unit-length vectors (measured: all 1330 at exactly
        # 1.0000), so a plain dot product already IS the cosine.
        kural_scores = self.kural_vectors @ question_vector

        # One score per chapter, then handed down to each of its 10 kurals so
        # both arrays are 1330 long and can be blended directly.
        chapter_scores = self.chapter_vectors @ question_vector
        handed_down = np.repeat(chapter_scores, KURALS_PER_CHAPTER)

        meaning_scores = (CHAPTER_BLEND_WEIGHT * handed_down
                          + (1 - CHAPTER_BLEND_WEIGHT) * kural_scores)

        keyword_scores = np.array(
            self.keyword_index.scores_for_query(search_text))

        return (KEYWORD_WEIGHT * normalise(keyword_scores)
                + (1 - KEYWORD_WEIGHT) * normalise(meaning_scores))

    def rank_everything(self, question):
        """Score all 1330 kurals the way this pipeline really ranks them.

        Returns five things:
          ranking_scores  - order by these. Reranked candidates are lifted
                            above every non-candidate.
          display_scores  - what a number MEANS to a reader: stage-1 score
                            for most kurals, the reranker's 0-to-1 reading
                            for the ones it looked at.
          search_text     - what was actually searched for, after rewriting.
          is_tamil        - was the question typed in Tamil script.
          rewritten_by    - what produced search_text, in plain words. This
                            travels to the browser so a degraded search can
                            never quietly pass for a full one.

        search() shows the top few of this; evaluate.py grades the whole
        ordering. Both call THIS, so neither can drift from the other.
        """
        # Our 170/233 is an English-only number. The rewrite instruction is
        # written in English and was measured on English questions only, so a
        # Tamil question is searched exactly as typed and says so. Sarvam is
        # an Indian-language model and may well rewrite Tamil beautifully -
        # that is a reason to MEASURE it, not a reason to assume it.
        # Each stage is timed separately. A single total tells you a search
        # was slow; it cannot tell you WHICH part was slow, and those need
        # completely different fixes - a slow rewrite is the network, a slow
        # rerank is this machine's processor.
        self.last_timing_ms = {}

        is_tamil = looks_like_tamil_script(question)
        started_at = time.perf_counter()
        if is_tamil:
            search_text, rewritten_by = question, REWRITER_SKIPPED_TAMIL
        elif self.rewriter is None:
            search_text, rewritten_by = question, REWRITER_FAILED
        else:
            search_text, rewritten_by = self.rewriter.rewrite(question)
        self.last_timing_ms["rewrite"] = round(
            (time.perf_counter() - started_at) * 1000, 1)

        started_at = time.perf_counter()
        stage_one = self.stage_one_scores(search_text)
        self.last_timing_ms["searchAll1330"] = round(
            (time.perf_counter() - started_at) * 1000, 1)

        ranking_scores = stage_one.copy()
        display_scores = stage_one.copy()

        started_at = time.perf_counter()
        if self.reranker is not None:
            candidate_positions = (
                np.argsort(stage_one)[::-1][:RERANK_CANDIDATE_COUNT])
            candidate_records = [self.kurals[position]
                                 for position in candidate_positions]
            # The cross-encoder reads the ORIGINAL question, not the rewrite:
            # it sees both texts together, so the full sentence helps it.
            logits = self.reranker.score_pairs(question, candidate_records,
                                               build_text=rerankable_text)
            # A cross-encoder trained on binary relevance emits a logit; the
            # sigmoid turns it back into a 0-to-1 reading. That is the model's
            # own scale, NOT a calibrated probability - src/calibrate.py
            # measures whether it separates on-topic from off-topic at all.
            reranked = 1.0 / (1.0 + np.exp(-logits))

            display_scores[candidate_positions] = reranked
            # stage-1 scores are a weighted sum of two 0-to-1 arrays, so they
            # never exceed 1. Adding 1 puts every reranked candidate above
            # every kural the reranker never looked at.
            ranking_scores[candidate_positions] = 1.0 + reranked

        self.last_timing_ms["rerank"] = round(
            (time.perf_counter() - started_at) * 1000, 1)

        return (ranking_scores, display_scores, search_text, is_tamil,
                rewritten_by)

    def search(self, question, top_k=DEFAULT_TOP_K):
        """The whole pipeline. Returns a dict shaped like RetrievalOutcome."""
        question = question.strip()
        cache_key = (question.lower(), top_k)
        if cache_key in self.query_cache:
            self.query_cache.move_to_end(cache_key)
            cached = dict(self.query_cache[cache_key])
            cached["cached"] = True
            return cached

        started_at = time.perf_counter()

        ranking_scores, display_scores, search_text, is_tamil, rewritten_by = (
            self.rank_everything(question))

        best_positions = np.argsort(ranking_scores)[::-1][:top_k]
        results = [{"kural": self.kurals[position],
                    "score": float(display_scores[position])}
                   for position in best_positions]

        top_score = results[0]["score"] if results else 0.0
        confidence = confidence_for(top_score)

        outcome = {
            "query": question,
            "queryLanguage": "ta" if is_tamil else "en",
            "searchedFor": search_text,
            "rewrittenBy": rewritten_by,
            # Refusing means refusing: below the floor, nothing is listed.
            "results": [] if confidence == "none" else results,
            "topScore": top_score,
            "confidence": confidence,
            "calibrated": SCORES_ARE_CALIBRATED,
            "engine": ENGINE_NAME,
            # Where the time went, stage by stage. The log records this, and
            # src/read_logs.py reads it back to say which stage to work on.
            "timingMs": dict(self.last_timing_ms),
            "elapsedMs": round((time.perf_counter() - started_at) * 1000, 1),
            "cached": False,
        }

        self.query_cache[cache_key] = outcome
        if len(self.query_cache) > QUERY_CACHE_SIZE:
            self.query_cache.popitem(last=False)
        return outcome


# ----------------------------------------------------------------------

def main():
    question = (" ".join(sys.argv[1:])
                or "how do I control my anger?")

    retriever = KuralRetriever()
    outcome = retriever.search(question)

    print()
    print(f'question:     "{outcome["query"]}"')
    print(f'searched for: "{outcome["searchedFor"]}"')
    print(f'rewritten by: {outcome["rewrittenBy"]}')
    print(f'read as:      {outcome["queryLanguage"]}   '
          f'in {outcome["elapsedMs"]} ms')
    print()
    for rank, result in enumerate(outcome["results"], start=1):
        record = result["kural"]
        print(f"  {rank}.  kural {record['number']}"
              f"   score {result['score']:.3f}"
              f"   [{record['chapter_english']}]")
        print(f"      {record['english_translation']}")
        print()


if __name__ == "__main__":
    main()
