"""Read the logs back and answer the questions we actually have.

A log nobody reads is a file that costs disk space. This is the reader.

Six questions, which are the six we will really ask:

    1. how much was used, and how much did it cost?
    2. how healthy was it - how often did the rewriter fail?
    3. which stage is slow? (rewrite / search / rerank)
    4. which searches came back weak, and what were they?
    5. what do people ask about?
    6. what went wrong?

Run it:

    venv/bin/python src/read_logs.py              # everything in the file
    venv/bin/python src/read_logs.py --last 100   # only the last 100 searches
"""

import json
import sys
from collections import Counter
from pathlib import Path

from search_log import SEARCH_LOG_PATH

# A search whose best result scores below this is worth looking at by hand.
# NOT a refusal threshold - pipeline.py refuses nothing, because the scores
# are not calibrated. This is only a flag for reading later.
WEAK_TOP_SCORE = 0.05

# Words too common to tell us anything about what a person wanted.
BORING_WORDS = {
    "the", "a", "an", "of", "to", "is", "are", "do", "does", "how", "what",
    "why", "when", "i", "my", "me", "it", "in", "on", "and", "or", "for",
    "with", "about", "that", "this", "should", "can", "does", "if", "be",
    "you", "your", "we", "they", "them", "he", "she", "his", "her", "not",
    "have", "has", "am", "was", "were", "there", "from", "at", "by", "as",
}


def load_events(path):
    """Read every line, skipping any that a killed process left half-written."""
    if not path.exists():
        raise SystemExit(
            f"no log file at {path}\n"
            f"Start the service and make a search first:\n"
            f"    venv/bin/uvicorn service.app:app --port 8000")
    events = []
    with open(path, encoding="utf-8") as open_file:
        for line in open_file:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def average(numbers):
    """Mean, or 0 for an empty list."""
    numbers = [value for value in numbers if value is not None]
    return sum(numbers) / len(numbers) if numbers else 0.0


def middle_value(numbers):
    """The median - the value with half the numbers above and half below.

    Reported alongside the average because they answer different questions.
    The average is dragged upward by a few very slow searches; the median
    says what a TYPICAL search felt like. When they disagree sharply, a small
    number of requests are much worse than the rest.
    """
    numbers = sorted(value for value in numbers if value is not None)
    if not numbers:
        return 0.0
    middle = len(numbers) // 2
    if len(numbers) % 2:
        return numbers[middle]
    return (numbers[middle - 1] + numbers[middle]) / 2


def main():
    how_many = None
    if "--last" in sys.argv:
        how_many = int(sys.argv[sys.argv.index("--last") + 1])

    events = load_events(SEARCH_LOG_PATH)
    searches = [event for event in events if event["event"] == "search"]
    errors = [event for event in events if event["event"] == "error"]
    starts = [event for event in events if event["event"] == "service_started"]
    if how_many:
        searches = searches[-how_many:]

    if not searches:
        raise SystemExit(f"{len(events)} events in the log, but no searches "
                         f"yet. Make one and run this again.")

    print("=" * 66)
    print(f"{len(searches)} searches, {len(errors)} errors, "
          f"{len(starts)} service starts")
    print(f"from {searches[0]['time'][:19]} to {searches[-1]['time'][:19]}")
    print("=" * 66)

    # ---- 1. what it cost -------------------------------------------------
    print()
    print("1. USE AND COST")
    paid = [event.get("rewritesPaidSoFar") for event in searches
            if event.get("rewritesPaidSoFar") is not None]
    rupees = [event.get("rupeesSpentSoFar") for event in searches
              if event.get("rupeesSpentSoFar") is not None]
    from_cache = sum(1 for event in searches
                     if event.get("servedFromQueryCache"))
    print(f"  searches served                 {len(searches)}")
    print(f"  answered from the query cache   {from_cache} "
          f"({from_cache / len(searches) * 100:.0f}%)")
    if rupees:
        # These are running totals, so the last one is the total for the run
        # and a restart sends it back to zero.
        print(f"  rewrites paid for (this run)    {max(paid) if paid else 0}")
        print(f"  spent (this run)                Rs {max(rupees):.4f}")

    # ---- 2. health -------------------------------------------------------
    print()
    print("2. HEALTH")
    degraded = [event for event in searches if event.get("degraded")]
    print(f"  searches WITHOUT a rewrite      {len(degraded)} "
          f"({len(degraded) / len(searches) * 100:.1f}%)")
    print("      (each of these is a measurably worse search - "
          "about 144/233 instead of 170/233)")
    if degraded:
        print("      most recent:")
        for event in degraded[-3:]:
            print(f"        {event['time'][11:19]}  {event.get('question')}")

    # ---- 3. where the time goes -----------------------------------------
    print()
    print("3. WHERE THE TIME GOES")
    print("   Key: 'average' is dragged up by a few slow ones. 'typical' is")
    print("   the middle value - what most searches actually felt like.")
    live = [event for event in searches
            if not event.get("servedFromQueryCache")]
    if live:
        print(f"   {'stage':22s} {'average':>10s} {'typical':>10s}")
        for stage, label in [("rewrite", "rewrite the question"),
                             ("searchAll1330", "score all 1330"),
                             ("rerank", "reread the top 50")]:
            values = [event.get("timingMs", {}).get(stage) for event in live]
            print(f"   {label:22s} {average(values):>8.0f}ms "
                  f"{middle_value(values):>8.0f}ms")
        totals = [event.get("totalMs") for event in live]
        print(f"   {'TOTAL':22s} {average(totals):>8.0f}ms "
              f"{middle_value(totals):>8.0f}ms")

    # ---- 4. weak results -------------------------------------------------
    print()
    print("4. SEARCHES THAT CAME BACK WEAK")
    print(f"   Top result scored below {WEAK_TOP_SCORE}. These are the ones to")
    print("   read by hand - either the book has nothing to say, or we missed.")
    weak = [event for event in searches
            if (event.get("topScore") or 0) < WEAK_TOP_SCORE]
    print(f"   {len(weak)} of {len(searches)} "
          f"({len(weak) / len(searches) * 100:.0f}%)")
    for event in weak[-8:]:
        print(f"     {event.get('topScore'):.3f}  {event.get('question')}")

    # ---- 5. what people ask about ---------------------------------------
    print()
    print("5. WHAT PEOPLE ASK ABOUT")
    print("   Most common words in the questions, with the boring ones removed.")
    words = Counter()
    for event in searches:
        for word in (event.get("question") or "").lower().split():
            word = "".join(letter for letter in word if letter.isalpha())
            if len(word) > 2 and word not in BORING_WORDS:
                words[word] += 1
    print("     " + ", ".join(f"{word} ({count})"
                              for word, count in words.most_common(15)))

    print()
    print("   Kurals returned most often:")
    returned = Counter()
    for event in searches:
        returned.update(event.get("resultKurals") or [])
    print("     " + ", ".join(f"kural {number} ({count})"
                              for number, count in returned.most_common(10)))
    print("   A single kural appearing in a large share of searches is the")
    print("   'hub kural' failure - kural 251 once answered 26 of 100.")

    # ---- 6. errors -------------------------------------------------------
    print()
    print("6. WHAT WENT WRONG")
    if not errors:
        print("   nothing")
    else:
        by_kind = Counter(event.get("whatFailed") for event in errors)
        for kind, count in by_kind.most_common():
            print(f"   {count:4d}  {kind}")
        print("   most recent:")
        for event in errors[-3:]:
            print(f"     {event['time'][11:19]}  {event.get('whatFailed')}: "
                  f"{str(event.get('message'))[:80]}")


if __name__ == "__main__":
    main()
