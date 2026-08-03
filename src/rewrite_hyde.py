"""The production question rewriter. Costs money, so it is careful with it.

WHAT IT DOES

Turns the question a person types into the words the 1330 verses actually
use, by asking a hosted language model.

    my uncle has money and will not spend it on anyone
        ->  avarice, miserliness, the vice of hoarding wealth

`avarice` and `miserliness` appear in the verses. `uncle` does not. That swap
is the whole job, and it is worth 26 questions on the 233-question scorecard.

The technique has a name - HyDE, Hypothetical Document Embeddings. The idea is
that a question and its answer are written differently, so searching with the
question shape finds other questions. Kural 251 is about eating meat and it
answered 26 of our first 100 questions purely because it opens "What
graciousness can one command...". Rewriting the question into the shape of an
ANSWER stops that.

WHAT IT REPLACED, AND WHY

src/rewrite_query.py deleted a fixed list of 111 boring words. It was free and
it worked, but its failure mode was destroying the question:

    should I spend time with people better than me?   ->   spend time

Measured on 233 questions, top-5 hit:

    word list          144 / 233
    Qwen3-1.7B local   155 / 233     (5.1 s per rewrite, needs 3.4 GB of RAM)
    Sarvam-105B        170 / 233     (0.5 s per rewrite, about Rs 0.00125)

Sarvam beats the word list with p = 0.0000 - that is settled. Against the
local model it scored 15 higher but p = 0.0534, just above the line, so it is
NOT proven better than Qwen and this file must not claim it is. It ships
because the local model needs about 100 seconds per question on a real host
and this needs half a second.

THE THREE THINGS THAT KEEP THE BILL DOWN

1. NOTHING IS ASKED TWICE. The model is set to temperature 0, so the same
   question always produces the same rewrite. Asking again would spend money
   to receive a string we already have. Every rewrite is written to disk and
   reused forever.

2. THE CACHE KNOWS WHAT IT HOLDS. The key includes the instruction text and
   the model name, not just the question. Change the instruction and every
   old entry stops matching, because those rewrites were answers to a
   different instruction. A cache that ignores this serves stale rewrites
   with no error - the same trap the vector cache in pipeline.py guards
   against.

3. FAILURE STOPS COSTING. If the provider is down, three failures in a row
   switch the rewriter off for a minute rather than making every visitor wait
   through a timeout. Search still works - it falls back to the raw question
   and SAYS SO in the result, so a degraded answer never pretends to be a
   full one.
"""

import hashlib
import json
import os
import time
from pathlib import Path

from hyde_prompt import INSTRUCTION, MAX_NEW_TOKENS
from llm import HostedModel

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# One rewrite per line, appended as they are produced. A line-per-entry file
# is used instead of one big JSON object so that adding an entry is a short
# append rather than rewriting the whole file, and so a process killed
# mid-write loses one line rather than the lot.
#
# The default lives in the repo and IS committed, because the 233 rewrites in
# it are what produced our measured 170/233 - a fresh clone reproduces that
# number without spending a rupee or depending on the provider still being up.
#
# A DEPLOYED copy should point this somewhere else with REWRITE_CACHE_PATH.
# Once real people are typing, this file becomes a log of what they asked, and
# that does not belong in a public repository.
CACHE_PATH = Path(os.environ.get(
    "REWRITE_CACHE_PATH",
    PROJECT_ROOT / "data" / "rewrite_cache.jsonl"))

# After this many failures in a row, stop calling the provider.
FAILURES_BEFORE_GIVING_UP = 3
# ...and try again only after this long. Long enough that a dead provider is
# not retried on every request, short enough that a blip heals by itself.
SECONDS_BEFORE_RETRYING = 60

# What produced the search text. This travels all the way to the browser, so a
# person can always see whether they got the real thing or the fallback.
REWRITER_WORKED = "sarvam-105b"
REWRITER_FAILED = "none (rewriter unavailable, searched the question as typed)"
REWRITER_SKIPPED_TAMIL = "none (Tamil question, searched as typed)"


def cache_key(question, model_name, instruction):
    """A short string that changes if ANY of the three inputs changes."""
    digest = hashlib.sha256()
    for part in (question.strip().lower(), model_name, instruction):
        digest.update(part.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()[:20]


def tidy_reply(text, fallback_question):
    """Strip the wrappers a model puts around its answer.

    Deliberately identical to the version in src/smoke_test_llm.py, which the
    benchmark also used. If production cleaned its output differently from the
    thing we measured, the measured number would stop describing production.
    """
    if "</think>" in text:                       # some models reason out loud
        text = text.split("</think>")[-1].strip()
    text = text.split("\n")[0].strip()           # keep the first line only
    if text.lower().startswith("statement:"):    # drop a repeated label
        text = text[len("statement:"):].strip()
    return text or fallback_question


class HydeRewriter:
    """Rewrites questions, remembers every answer, and fails quietly."""

    def __init__(self, provider_name="sarvam", cache_path=CACHE_PATH):
        self.model = HostedModel(provider_name)
        self.cache_path = Path(cache_path)
        self.instruction = INSTRUCTION
        self.model_name = self.model.settings["model"]

        self.cache = self._load_cache()

        # Circuit breaker state. Starts closed - we assume the provider works
        # until it tells us otherwise.
        self.failures_in_a_row = 0
        self.stop_calling_until = 0.0
        self.last_error = None

        # Counters, so any script can report what it really spent.
        self.calls_made = 0
        self.cache_hits = 0

    # ------------------------------------------------------------------

    def _load_cache(self):
        """Read every rewrite we have ever paid for."""
        cache = {}
        if not self.cache_path.exists():
            return cache
        with open(self.cache_path, encoding="utf-8") as open_file:
            for line in open_file:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    # A line half-written when a process was killed. Skip it;
                    # the worst outcome is paying for that one rewrite again.
                    continue
                cache[entry["key"]] = entry["rewrite"]
        return cache

    def _remember(self, key, question, rewrite_text):
        """Add one rewrite to memory and to disk."""
        self.cache[key] = rewrite_text
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_path, "a", encoding="utf-8") as open_file:
            # The question and model are stored alongside the key so the file
            # can be read by a human and audited. The key alone would make it
            # a wall of hashes.
            json.dump({"key": key,
                       "question": question,
                       "model": self.model_name,
                       "rewrite": rewrite_text}, open_file,
                      ensure_ascii=False)
            open_file.write("\n")

    def _provider_is_open(self):
        """False while the circuit breaker is holding calls back."""
        if self.failures_in_a_row < FAILURES_BEFORE_GIVING_UP:
            return True
        if time.monotonic() >= self.stop_calling_until:
            # The cool-off has passed. Allow one call through to test the
            # water; if it fails, the breaker trips again immediately.
            self.failures_in_a_row = FAILURES_BEFORE_GIVING_UP - 1
            return True
        return False

    # ------------------------------------------------------------------

    def rewrite(self, question):
        """Return (search_text, what_produced_it).

        Never raises. A search that fails because the rewriter is down is a
        worse outcome than a search done on the raw question, so every failure
        path ends in a usable string.
        """
        question = question.strip()
        if not question:
            return question, REWRITER_FAILED

        key = cache_key(question, self.model_name, self.instruction)
        if key in self.cache:
            self.cache_hits += 1
            return self.cache[key], REWRITER_WORKED

        if not self._provider_is_open():
            return question, REWRITER_FAILED

        try:
            reply = self.model.ask(self.instruction,
                                   f"question: {question}",
                                   max_output_tokens=MAX_NEW_TOKENS)
        except Exception as error:
            # HostedModel.ask has already removed the key from this message.
            self.failures_in_a_row += 1
            self.last_error = str(error)
            if self.failures_in_a_row >= FAILURES_BEFORE_GIVING_UP:
                self.stop_calling_until = (time.monotonic()
                                           + SECONDS_BEFORE_RETRYING)
                print(f"rewriter: {FAILURES_BEFORE_GIVING_UP} failures in a "
                      f"row, pausing for {SECONDS_BEFORE_RETRYING}s. "
                      f"last error: {self.last_error}")
            return question, REWRITER_FAILED

        self.failures_in_a_row = 0
        self.calls_made += 1
        rewrite_text = tidy_reply(reply, question)
        self._remember(key, question, rewrite_text)
        return rewrite_text, REWRITER_WORKED

    # ------------------------------------------------------------------

    def spend_report(self):
        """What this rewriter has cost since it was created."""
        return (f"{self.calls_made} paid rewrites, "
                f"{self.cache_hits} served from cache, "
                f"Rs {self.model.rupees_spent():.4f}")


def main():
    """Rewrite whatever is typed on the command line, and show the cost."""
    import sys

    questions = sys.argv[1:] or [
        "how do I control my anger?",
        "my uncle has money and will not spend it on anyone",
        "should I spend time with people better than me?",
    ]
    rewriter = HydeRewriter()
    for question in questions:
        started_at = time.perf_counter()
        search_text, produced_by = rewriter.rewrite(question)
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        print(f"  {question}")
        print(f"    -> {search_text}")
        print(f"       {produced_by}, {elapsed_ms:.0f} ms")
        print()
    print(rewriter.spend_report())


if __name__ == "__main__":
    main()
