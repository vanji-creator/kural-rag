"""Stage 2 - read the question and the kural TOGETHER, then score.

Everything up to now compared the question and the kural SEPARATELY. Each was
turned into 768 numbers on its own, and the two lists of numbers were compared.

The catch: the kural's numbers were computed this morning, before any question
existed. So one fixed summary has to serve every question anyone might ask.
That is how kural 251 - a verse about eating meat - answered 26 of our 100
questions. Its frozen summary said "this text asks a rhetorical question", and
26 question-shaped queries matched that.

A cross-encoder removes the problem by never freezing anything:

    question + kural, in one input  ->  [model]  ->  one score

It reads both texts side by side and answers "does this kural answer this
question?". Much harder to fool with surface shape.

The price: nothing can be cached. Change the question and every score is void.
Scoring all 1330 kurals this way would mean 1330 model runs per question.

So it only ever sees the top 50 from stage 1. 50 runs, not 1330.

Measured ceiling for a top-50 cutoff: 94 of 100. The reranker can never beat
that, because it only reorders what stage 1 handed it.
"""

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

# Small, fast, English-only, and the standard baseline reranker. About 90 MB.
#
# English-only is a real limitation here: we feed it the English translation
# and explanation and drop the Tamil. If Tamil turns out to carry signal the
# English does not, a bigger multilingual reranker is the next thing to try -
# and it gets measured on the scorecard like everything else.
RERANKER_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# The multilingual challenger. 568M parameters against our 22M, so expect it
# to be far slower.
#
# gte-multilingual-reranker-base was the first choice - it is the only
# candidate that DECLARES Tamil ('ta') in its own metadata. It was abandoned
# because it ships custom model code (trust_remote_code=True) written against
# an older transformers, and under transformers 5.x it reads an uninitialised
# position_ids buffer, then produces NaN even after that is patched.
#
# Lesson kept on purpose: a model needing trust_remote_code carries code that
# rots when the library moves under it.
#
# bge-reranker-v2-m3 uses the stock XLM-RoBERTa architecture instead, so there
# is no custom code to rot. Its Tamil support is INFERRED (XLM-RoBERTa declares
# 94 languages including Tamil) rather than declared by the reranker itself.
MULTILINGUAL_MODEL_NAME = "BAAI/bge-reranker-v2-m3"

# What production actually loads. Vikash's decision, 2026-08-04, after run
# #14 of the experiment log: bge reading the same English text beat the
# small model where the reader lives - rank-1 105 -> 131 of 233, p = 0.0001,
# with top-5 rising 174 -> 182. Set A rank-1 went 68 -> 80.
#
# THE COST, KNOWN AND ACCEPTED: ~15-25 s per uncached search on a laptop
# CPU, 875 ms on a T4 GPU. Exact-only (CLAUDE.md 3.5): accuracy outranks
# speed. The quantization experiment may buy the speed back and must prove
# zero accuracy loss first.
#
# RERANKER_MODEL_NAME above stays pointing at the small model on purpose:
# benchmark scripts use it to reproduce baseline arm A.
PRODUCTION_RERANKER_MODEL = MULTILINGUAL_MODEL_NAME

DEFAULT_CANDIDATE_COUNT = 50


def rerankable_prose(kural_record, mode=None):
    """The prose the reranker reads about one kural.

    WHY THIS TAKES A MODE, AS OF 2026-08-03

    This function used to hand the reranker `english_explanation` and nothing
    else - the 1880s prose. That was invisible when the corpus had only one
    English text. It stopped being invisible the moment we added a modern one.

    The audit that found it: we measured three versions of the CORPUS text
    (classic / modern / both) and got 170, 173, 174 out of 233 - a difference
    well inside luck. The reason is here. The mode switch changed stage one,
    which picks 50 candidates; this function feeds the RERANKER, which picks
    the final 5 out of those 50. So the step that decides what a reader
    actually sees was reading 1880s English in all three runs.

    A measurement that only reaches half the pipeline is not a measurement of
    the pipeline.
    """
    from pipeline import CORPUS_TEXT_MODE, load_modern_explanations

    mode = mode or CORPUS_TEXT_MODE
    modern = load_modern_explanations().get(kural_record["number"], "")

    if mode == "modern" and modern:
        return modern
    if mode == "both" and modern:
        return kural_record["english_explanation"] + " " + modern
    return kural_record["english_explanation"]


# Does the reranker see the verse couplet as well as the prose?
#
# The couplet is compressed Victorian verse - "Anger against the weak is wrong
# It is futile against the strong". It is not a sentence, and a cross-encoder
# trained on ordinary web passages has never seen text shaped like it.
#
# Worse, it is accidental keyword bait. Asked "how do I stay strong when
# things go wrong?", the reranker scored that anger verse 0.406 and the
# correct verse about enduring trouble 0.016 - 25 times higher - because the
# couplet contains the words "strong" and "wrong" and the question does too.
# The verse is about anger. It shares no meaning with the question at all.
#
# False means the reranker reads only the prose, which is a real sentence.
INCLUDE_COUPLET_IN_RERANK = True


def rerankable_text(kural_record, mode=None, include_couplet=None):
    """English only. All our current reranker can read."""
    if include_couplet is None:
        include_couplet = INCLUDE_COUPLET_IN_RERANK
    prose = rerankable_prose(kural_record, mode)
    if not include_couplet:
        return prose
    return kural_record["english_translation"] + ". " + prose


def rerankable_text_with_tamil(kural_record, mode=None):
    """English AND Tamil, for a model that can actually read both.

    Only worth passing to a multilingual reranker. Handing this to the
    English-only model would just be feeding it noise.
    """
    return (kural_record["english_translation"] + ". "
            + rerankable_prose(kural_record, mode) + " "
            + kural_record["tamil_meaning_mu_varadarajan"])


class Reranker:
    """Wraps the cross-encoder so callers never touch the model directly.

    Uses plain transformers rather than sentence-transformers' CrossEncoder.
    That is deliberate, and it cost an hour to find out why: the CrossEncoder
    wrapper silently mis-loads bge-reranker-v2-m3's classifier head and
    returns a score of 0.000 for EVERY pair - no error, no warning, just a
    ranking made of noise. Loading the same checkpoint directly gives real
    numbers (-6.9 for a match, -11.0 for a mismatch).

    A wrapper that fails loudly is a bug. One that fails silently is a trap.
    """

    def __init__(self, model_name=RERANKER_MODEL_NAME, max_length=512):
        self.max_length = max_length
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(
            model_name)
        self.model.eval()

    def score_pairs(self, question_text, kural_records,
                    build_text=rerankable_text):
        """Score this one question against each of these kurals.

        Returns one number per kural. Higher means "answers the question
        better". These are raw model outputs on the model's own scale - not
        similarities, not capped at 1 - so only their ORDER means anything.

        build_text decides how much of each kural the model gets to see, so
        the same model can be measured on English-only and on English+Tamil.
        """
        question_and_kural_pairs = [[question_text, build_text(record)]
                                    for record in kural_records]
        with torch.no_grad():
            tokenized = self.tokenizer(question_and_kural_pairs,
                                       padding=True, truncation=True,
                                       return_tensors="pt",
                                       max_length=self.max_length)
            logits = self.model(**tokenized).logits.view(-1).float()
        return logits.numpy()
