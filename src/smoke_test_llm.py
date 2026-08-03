"""The smallest possible first call to a hosted model. Five questions.

WHAT THIS DECIDES

Three things, and nothing else. It is deliberately not the scorecard.

    1. Does the key work at all, and is the model name right?
    2. Does the hosted model FOLLOW THE INSTRUCTION - one short statement,
       no question mark, no explanation, no reasoning out loud? The local
       Qwen3 needed a "/no_think" trick to stop reasoning. A hosted model
       may need its own handling and it is cheaper to find that out on five
       questions than on 233.
    3. What does one call really cost, measured rather than estimated?

WHAT IT DOES NOT DECIDE

Whether Sarvam is better than Qwen3-1.7B. Five questions cannot tell us
that - we learned on 2026-08-02 that a rewrite looking good and a rewrite
scoring well are different things, and that reading five outputs fooled us
once already. The side-by-side below is printed to be READ, not counted.

The judge is still src/benchmark_models.py on all 233 questions.

Run it:

    venv/bin/python -u src/smoke_test_llm.py            # sarvam-105b
    venv/bin/python -u src/smoke_test_llm.py sarvam-30b # the smaller one
"""

import json
import sys
import time
from pathlib import Path

from benchmark_chapters import load_questions
from hyde_prompt import INSTRUCTION, MAX_NEW_TOKENS
from llm import DEFAULT_PROVIDER, HostedModel

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOCAL_REWRITES_PATH = PROJECT_ROOT / "data" / "hyde_rewrites_neutral.json"
HOW_MANY = 5


def clean_reply(text, fallback_question):
    """Strip the wrappers a model puts around its answer.

    Kept identical to the local version in src/hyde_fast.py on purpose. If
    the two cleaned their output differently, a comparison between them would
    partly be measuring the cleaning code instead of the models.
    """
    if "</think>" in text:                       # some models reason out loud
        text = text.split("</think>")[-1].strip()
    text = text.split("\n")[0].strip()           # keep the first line only
    if text.lower().startswith("statement:"):    # drop a repeated label
        text = text[len("statement:"):].strip()
    return text or fallback_question


def main():
    provider_name = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PROVIDER
    model = HostedModel(provider_name)
    print(f"provider : {provider_name}")
    print(f"model    : {model.settings['model']}")
    print(f"address  : {model.settings['base_url']}")
    print()

    # The same questions the whole project has been measured on, in the same
    # order, so the cached local rewrites line up with them exactly.
    set_a, set_b = load_questions()
    questions = [question for question, _ in set_a + set_b][:HOW_MANY]

    local_rewrites = []
    if LOCAL_REWRITES_PATH.exists():
        with open(LOCAL_REWRITES_PATH, encoding="utf-8") as open_file:
            local_rewrites = json.load(open_file).get("Qwen3-1.7B", [])

    seconds_taken = []
    for index, question in enumerate(questions):
        started_at = time.perf_counter()
        reply = model.ask(INSTRUCTION, f"question: {question}",
                          max_output_tokens=MAX_NEW_TOKENS)
        elapsed = time.perf_counter() - started_at
        seconds_taken.append(elapsed)

        statement = clean_reply(reply, question)
        print(f"  Q       {question}")
        if index < len(local_rewrites):
            print(f"  laptop  {local_rewrites[index]}")
        print(f"  hosted  {statement}")
        print(f"          ({elapsed:.1f} s)")

        # The instruction says: a statement, one line, under 20 words. Say so
        # when it is not obeyed, rather than letting it slide into a 233
        # question run where nobody is reading the output.
        problems = []
        if statement.endswith("?"):
            problems.append("still a question")
        if len(statement.split()) > 25:
            problems.append(f"{len(statement.split())} words, asked for <20")
        if "\n" in reply.strip():
            problems.append("more than one line")
        if problems:
            print(f"          INSTRUCTION NOT FOLLOWED: {', '.join(problems)}")
        print()

    average_seconds = sum(seconds_taken) / len(seconds_taken)
    print("=" * 62)
    print(f"average    {average_seconds:.1f} s per rewrite "
          f"(laptop Qwen3-1.7B was 5.1 s)")
    print(f"cost       {model.cost_report()}")

    # Scale the measured cost up to the sizes we actually care about, so the
    # budget question is answered with real numbers instead of a forecast.
    per_call = model.rupees_spent() / HOW_MANY
    print(f"one full scorecard run (233 rewrites)   Rs {per_call * 233:.2f}")
    print(f"Rs 100 of credit buys about             "
          f"{int(100 / per_call):,} rewrites")


if __name__ == "__main__":
    main()
