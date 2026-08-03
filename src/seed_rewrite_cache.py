"""Move the 233 rewrites we already paid for into the production cache.

WHY THIS EXISTS

src/benchmark_sarvam.py fetched 233 rewrites and saved them in its own file.
The production rewriter keeps its cache somewhere else, in a different shape.
Without this step the first evaluation run would buy all 233 again - about
Rs 0.29 to receive strings we already have on disk.

It also does something more important than saving money. It guarantees the
production rewriter uses the EXACT text that scored 170/233. If production
re-fetched them, a provider that had changed its model overnight would give
slightly different rewrites and our measured number would quietly stop
describing what users get.

Safe to run more than once: an entry already in the cache is skipped.

Run it:

    venv/bin/python src/seed_rewrite_cache.py
"""

import json
from pathlib import Path

from benchmark_chapters import load_questions
from hyde_prompt import INSTRUCTION
from rewrite_hyde import CACHE_PATH, cache_key

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BENCHMARK_REWRITES = PROJECT_ROOT / "data" / "hyde_rewrites_sarvam.json"
MODEL_NAME = "sarvam-105b"


def main():
    with open(BENCHMARK_REWRITES, encoding="utf-8") as open_file:
        rewrites = json.load(open_file)

    set_a, set_b = load_questions()
    questions = [question for question, _ in set_a + set_b]

    if len(questions) != len(rewrites):
        raise SystemExit(
            f"{len(questions)} questions but {len(rewrites)} rewrites. These "
            f"files must line up position by position - refusing to guess "
            f"which rewrite belongs to which question.")

    already_there = set()
    if CACHE_PATH.exists():
        with open(CACHE_PATH, encoding="utf-8") as open_file:
            for line in open_file:
                if line.strip():
                    already_there.add(json.loads(line)["key"])

    added = 0
    with open(CACHE_PATH, "a", encoding="utf-8") as open_file:
        for question, rewrite_text in zip(questions, rewrites):
            key = cache_key(question, MODEL_NAME, INSTRUCTION)
            if key in already_there:
                continue
            json.dump({"key": key,
                       "question": question,
                       "model": MODEL_NAME,
                       "rewrite": rewrite_text}, open_file,
                      ensure_ascii=False)
            open_file.write("\n")
            already_there.add(key)
            added += 1

    print(f"seeded {added} rewrites into {CACHE_PATH.name}")
    print(f"cache now holds {len(already_there)} rewrites")
    print(f"saved about Rs {added * 0.00125:.2f} of repeat calls")


if __name__ == "__main__":
    main()
