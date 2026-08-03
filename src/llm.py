"""One small door to whichever hosted language model we are testing.

WHY THIS FILE EXISTS

Until now the language model ran on this laptop: src/hyde_fast.py loads a
1.7B model into memory and generates 3.7 words per second. That is fast
enough to experiment with and far too slow to serve a user, so the model
moves to a company's server and we call it over the internet.

The problem with that is lock-in. If the rewrite code says "Sarvam" in
twenty places, comparing Sarvam against Gemini means editing twenty places,
and a comparison that is annoying to run is a comparison that never gets run.

So every provider we care about is reached through the SAME request format
(the one OpenAI published; everyone else copied it). This file holds the two
things that actually differ between them - the address and the model name -
in one table, and nothing else in the project needs to know which one is live.

WHAT A CALL COSTS

Every provider bills two numbers separately:

    input tokens   the text we SEND     (the question, the retrieved kurals)
    output tokens  the text we GET BACK (the rewrite, the answer)

A token is roughly one short word. Output is always dearer than input,
usually four or five times, because the model does far more work per word
when writing than when reading.

This file records the price of both for each provider and adds up the real
rupee cost of every call, so no number in this project is a guess.

Prices checked 2026-08-02. They change - re-check before quoting them.
"""

import os
import threading
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# The exchange rate used to convert dollar-priced providers into rupees.
# Sarvam publishes in rupees already, so its numbers below are exact and this
# only affects the others.
RUPEES_PER_DOLLAR = 95.4

# Every provider we are comparing, keyed by a short name we type on the
# command line. Each entry says:
#
#   base_url          the address its server answers on
#   env_var           the name of the environment variable holding the key
#   model             which model to ask for
#   rupees_per_input_million / rupees_per_output_million
#                     the price, already converted to rupees per 1,000,000
#                     tokens, so cost arithmetic never needs a currency step
PROVIDERS = {
    # Indian company, models built deliberately for Indian languages. That is
    # not a nice-to-have here: the open questions in LEARNING_GAPS.md are
    # Tamil questions and Thanglish, which no general model was aimed at.
    #
    # sarvam-30b was the obvious cheaper sibling to try. It is DEPRECATED -
    # the server answers "Please use one of the available models instead:
    # sarvam-105b". There is no smaller option here.
    "sarvam": {
        "base_url": "https://api.sarvam.ai/v1",
        "env_var": "SARVAM_API_KEY",
        "model": "sarvam-105b",
        "rupees_per_input_million": 4.0,    # published directly in rupees
        "rupees_per_output_million": 16.0,
        # THIS LINE IS NOT OPTIONAL. Measured 2026-08-02:
        #
        #   setting                  seconds  output tokens  answer
        #   default                      4.3            400  (empty)
        #   reasoning_effort="low"       3.7            400  (empty)
        #   reasoning_effort=None        0.2             13  correct
        #
        # By default this model thinks out loud first, into a separate field
        # called reasoning_content, and only writes the real answer once the
        # thinking is done. Our rewrite needs 13 words, so the thinking never
        # finished inside any sane token limit and the answer field stayed
        # empty - while we were billed for all 400 tokens of the thinking.
        #
        # "low" does NOT reduce it. Only switching it off does.
        #
        # It must travel in extra_body: the openai package treats a plain
        # reasoning_effort=None as "the caller did not set this" and drops it
        # from the request entirely, so the setting never reaches the server.
        # Same trap as the CrossEncoder wrapper in src/rerank.py - the call
        # succeeds, nothing warns you, and the output is silently wrong.
        "extra_body": {"reasoning_effort": None},
    },
    # Google's cheap model, and the only one with a free daily allowance.
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "env_var": "GEMINI_API_KEY",
        "model": "gemini-2.5-flash-lite",
        "rupees_per_input_million": 0.10 * RUPEES_PER_DOLLAR,
        "rupees_per_output_million": 0.40 * RUPEES_PER_DOLLAR,
    },
    # The expensive end of the comparison. Not a candidate to ship - it is
    # here to tell us how much accuracy the cheap ones are giving up. Without
    # a top of the range we cannot tell "good" from "as good as it gets".
    "claude": {
        "base_url": "https://api.anthropic.com/v1/",
        "env_var": "ANTHROPIC_API_KEY",
        "model": "claude-opus-5",
        "rupees_per_input_million": 5.00 * RUPEES_PER_DOLLAR,
        "rupees_per_output_million": 25.00 * RUPEES_PER_DOLLAR,
    },
}

DEFAULT_PROVIDER = "sarvam"

# A question longer than this is truncated before being sent. We pay per token
# sent, and nobody types a real question this long - but somebody will paste a
# whole page into the search box eventually.
MAX_INPUT_CHARACTERS = 2000

# How long to wait for one reply before giving up on it. A rewrite takes about
# half a second, so 30 is enormously generous - it is there to catch a request
# that has silently stalled, not a slow one.
REQUEST_TIMEOUT_SECONDS = 30

# The client retries a failed request this many times, with a growing pause
# between attempts, before the error reaches us.
REQUEST_RETRIES = 3

# The client's own retries do not cover a rate limit for long enough - the
# limit is counted per minute and its backoff is measured in seconds. These
# waits are what actually gets a long run through a busy minute.
RATE_LIMIT_WAITS = (2, 5, 12, 30, 60, 90)


class HostedModel:
    """A language model on someone else's server, with the meter running."""

    def __init__(self, provider_name=DEFAULT_PROVIDER):
        if provider_name not in PROVIDERS:
            raise ValueError(f"unknown provider {provider_name!r}. "
                             f"known: {', '.join(PROVIDERS)}")
        self.provider_name = provider_name
        self.settings = PROVIDERS[provider_name]

        # Load .env from the project root. That file holds the API keys and is
        # listed in .gitignore, so the keys never reach GitHub.
        load_dotenv(PROJECT_ROOT / ".env")
        api_key = (os.environ.get(self.settings["env_var"]) or "").strip()
        if not api_key:
            raise RuntimeError(
                f"no key found. Put this line in {PROJECT_ROOT / '.env'}:\n"
                f"    {self.settings['env_var']}=your-key-here")
        # The .env file ships with a placeholder. Catch it here rather than
        # letting it travel to the server and come back as a confusing 401.
        if "paste-your" in api_key or api_key.endswith("-key-here"):
            raise RuntimeError(
                f"{self.settings['env_var']} is still the placeholder text. "
                f"Put the real key in {PROJECT_ROOT / '.env'}.")

        # Kept ONLY so it can be scrubbed out of error messages. Never printed,
        # never returned, never written to a log or a cache file.
        self._api_key = api_key

        # A hosted model is a network call, and networks drop requests. The
        # judging run on 2026-08-03 made ~450 calls in a row and one of them
        # timed out, which killed the whole job and lost every verdict before
        # it. Retries and an explicit timeout are not optional at that volume.
        self.client = OpenAI(base_url=self.settings["base_url"],
                             api_key=api_key,
                             timeout=REQUEST_TIMEOUT_SECONDS,
                             max_retries=REQUEST_RETRIES)

        # Running totals for the whole session, so any script can print what
        # it just spent instead of estimating it.
        #
        # The lock is needed because one HostedModel can be shared by several
        # threads - src/modernise_corpus.py runs 8 calls at once. "count += n"
        # is read, add, write: two threads can read the same old value and one
        # update is lost. That would understate what we spent.
        self._counter_lock = threading.Lock()
        self.input_tokens_used = 0
        self.output_tokens_used = 0
        # How many times we were told to slow down. Reported so a run
        # that took twice as long says why.
        self.rate_limit_waits = 0

    def __repr__(self):
        """Deliberately says nothing about the key.

        Python prints this object automatically in tracebacks and debuggers.
        The default would show every attribute, and one of them is the key.
        """
        return f"<HostedModel {self.provider_name} {self.settings['model']}>"

    def scrub(self, text):
        """Remove the key from any text before it is shown or logged.

        A key that reaches a log file, a crash report or a terminal that
        someone screenshots is a leaked key. Client libraries do sometimes put
        request details into exception messages, so nothing this class raises
        goes out unfiltered.
        """
        text = str(text)
        if self._api_key and self._api_key in text:
            text = text.replace(self._api_key, "***KEY-HIDDEN***")
        return text

    def ask(self, system_instruction, user_message, max_output_tokens=200):
        """Send one instruction plus one message. Return the reply text.

        temperature=0 means the model always picks its most likely next word
        instead of sampling a less likely one. Same question in, same answer
        out, every time. Any other setting would make the scorecard wobble
        between runs and we would not know whether a change or the dice moved
        the number.
        """
        # A user can paste an essay into a search box. We are billed per token
        # sent, so cut it before it becomes cost. 2000 characters is roughly
        # 400 tokens - far longer than any real question, short enough that a
        # pasted page cannot run up a bill.
        user_message = user_message[:MAX_INPUT_CHARACTERS]

        # WAIT OUT A RATE LIMIT RATHER THAN THROWING THE WORK AWAY.
        #
        # This belongs here and nowhere else. It was first written inside
        # src/modernise_corpus.py, which fixed that one script and left every
        # other caller exposed - and the very next long run, in
        # src/measure_modern_stack.py, died on a 429 after 100 paid rewrites.
        # A retry that only one caller has is a retry the codebase does not
        # have.
        #
        # Only rate limits are waited out. A bad request or a wrong model name
        # will fail identically in ninety seconds, so those are raised at once.
        response = None
        for attempt, wait_seconds in enumerate(RATE_LIMIT_WAITS, start=1):
            try:
                response = self.client.chat.completions.create(
                    model=self.settings["model"],
                    messages=[
                        {"role": "system", "content": system_instruction},
                        {"role": "user", "content": user_message}],
                    max_tokens=max_output_tokens,
                    temperature=0.0,
                    # Anything this provider needs that the others do not,
                    # such as Sarvam's thinking off-switch.
                    extra_body=self.settings.get("extra_body"),
                )
                break
            except Exception as error:
                message = self.scrub(error)
                is_rate_limit = ("rate_limit" in message.lower()
                                 or "429" in message)
                if not is_rate_limit or attempt == len(RATE_LIMIT_WAITS):
                    # Re-raise with the key removed. Never let the original
                    # escape: its message may quote the request that carried
                    # the key.
                    raise RuntimeError(
                        f"{self.provider_name} call failed: "
                        f"{message}") from None
                self.rate_limit_waits += 1
                time.sleep(wait_seconds)

        # Every provider reports back exactly how many tokens it charged for.
        # We use their count, not our guess at it.
        usage = response.usage
        if usage is not None:
            with self._counter_lock:
                self.input_tokens_used += usage.prompt_tokens
                self.output_tokens_used += usage.completion_tokens

        choice = response.choices[0]
        answer = (choice.message.content or "").strip()

        # An empty answer that still cost 400 tokens is the failure we hit on
        # 2026-08-02, and it looked exactly like a working call. Refuse to
        # return silence. A run of 233 questions must not quietly become 233
        # blanks that then get scored as if they were rewrites.
        if not answer:
            spent = getattr(usage, "completion_tokens", 0)
            thinking = getattr(choice.message, "reasoning_content", None)
            raise RuntimeError(
                f"{self.provider_name} returned an EMPTY answer after "
                f"{spent} output tokens (stopped because: "
                f"{choice.finish_reason}).\n"
                + ("The model spent them thinking instead of answering. "
                   "Switch thinking off for this provider - see the "
                   "extra_body note on 'sarvam' above.\n" if thinking else "")
                + "Refusing to return silence, because silence scores as a "
                  "failed question and hides the real cause.")

        return answer

    def rupees_spent(self):
        """What this session has cost so far, in rupees."""
        input_cost = (self.input_tokens_used / 1_000_000
                      * self.settings["rupees_per_input_million"])
        output_cost = (self.output_tokens_used / 1_000_000
                       * self.settings["rupees_per_output_million"])
        return input_cost + output_cost

    def cost_report(self):
        """One line saying what was sent, what came back, and what it cost."""
        return (f"{self.provider_name} ({self.settings['model']}): "
                f"{self.input_tokens_used} tokens in, "
                f"{self.output_tokens_used} out, "
                f"Rs {self.rupees_spent():.4f}"
                + (f", waited out {self.rate_limit_waits} rate limits"
                   if self.rate_limit_waits else ""))
