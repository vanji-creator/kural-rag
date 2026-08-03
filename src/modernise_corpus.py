"""Rewrite what each verse MEANS into plain modern English.

THE HYPOTHESIS THIS TESTS

Vikash, 2026-08-03: "the english meaning is also very old, the current modern
llms were not trained on this old english, it reads modern english like us."

Here is the English we currently search, for kural 865:

    translation   Crooked, cruel, tactless and base Any foe can fell him with ease
    couplet       No way of right he scans, no precepts bind, no crimes affright
    explanation   (A) pleasing (object) to his foes is he who reads not moral
                  works, does nothing that is enjoined by them cares not for
                  reproach and is not possessed of good qualities

None of that is how anyone writes now. LaBSE was trained on modern text, and
this is half the meaning score - chapter description 0.5, this text 0.5.

We solved the same problem once already, on the other side. HyDE rewrites the
QUESTION to reach the book's vocabulary. This is the mirror image: rewrite the
BOOK to reach the question's vocabulary. Both ends moving toward each other.

WHY SARVAM AND NOT A BIGGER ENGLISH MODEL

Because the richest sources here are in Tamil, not English. Each kural carries
two classical Tamil commentaries and three modern Tamil paraphrases. A model
built for Indian languages can read the meaning at its source instead of
polishing a Victorian translation of it.

NOTHING IS DELETED

data/kurals.json is never written to. The modern text goes in its own file and
is swapped in at pipeline level only, so the old English is always one flag
away.

WHY THE PROMPT FORBIDS INTERPRETING

Whatever is written here gets retrieved, and then CITED by the answer
generator as though it were the verse's own meaning. A sentence that adds a
thought the verse never had would travel all the way to a reader with a kural
number attached to it. That is the failure this whole project exists to
prevent, so "paraphrase, do not interpret" is rule 2, not rule 5.

LEAKAGE CONTROL

This process never loads data/golden_set.json or any question file. Not "is
careful not to look at" - never loads. We have had three leakage incidents,
and the last one happened AFTER a plan promised to keep a file closed. A plan
to not-look is not a control. Not importing it is.

Run it:

    venv/bin/python -u src/modernise_corpus.py            # write them
    venv/bin/python    src/modernise_corpus.py --check    # validate
    venv/bin/python    src/modernise_corpus.py --show 20  # old vs new
"""

import json
import random
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from llm import HostedModel

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CORPUS_PATH = PROJECT_ROOT / "data" / "kurals.json"
MODERN_PATH = PROJECT_ROOT / "data" / "modern_explanations.jsonl"

# Stage 2: the paste files for a second model, and its replies.
REVIEW_DIRECTORY = PROJECT_ROOT / "data" / "review"
REVIEW_REPLIES_PATH = REVIEW_DIRECTORY / "gpt_review.jsonl"
REVIEW_PATH = PROJECT_ROOT / "data" / "modern_review_gpt.json"

# One or two sentences. 160 leaves room to finish a thought and not to ramble.
MAX_OUTPUT_TOKENS = 160

# How many rewrites to have in flight at once. Nearly all the time is spent
# waiting for a reply over the network rather than computing, so this mostly
# divides the total time - but not by the full amount, because the provider
# limits how much it will do for us at once.
#
# Measured 2026-08-03 on 24 kurals, seconds per rewrite:
#
#      1 at once   4.34
#      8 at once   2.11
#     16 at once   1.35     <- looked like the knee
#     24 at once   1.45     worse, not better
#
# THAT MEASUREMENT WAS WRONG, AND THE REASON IS WORTH REMEMBERING.
#
# 24 calls is a few seconds of traffic. A rate limit is counted per minute,
# so a test that short never reaches it - it measures the beginning of an
# allowance rather than the allowance. Run against all 1330, this same
# setting produced 783 rate-limit errors and lost more work than it saved.
#
# A short test cannot see a limit that is measured over a longer window than
# the test. The fix is not only a smaller number here; it is the backoff
# below, which finds the real limit by being told about it.
AT_ONCE = 6

# When the provider says "too many requests", wait and try again rather than
# throwing the work away. The waits grow each time, so a busy minute costs a
# pause and not 783 missing rewrites.
RATE_LIMIT_WAITS = (2, 5, 12, 30, 60, 90)

# Words that would give away that this text came from a book of numbered
# verses. They must not appear: the search text should read as a statement
# about life, because that is what a question is about.
FORBIDDEN_WORDS = re.compile(
    r"\b(kural|thirukkural|thirukural|couplet|verse|chapter|valluvar|"
    r"thiruvalluvar)\b", re.IGNORECASE)

# Openings that begin an ADDED sentence rather than a translated one.
#
# Found the hard way. Of 64 rewrites a reviewer rejected, 80% had a second
# sentence, against 15% of the ones it passed - every invention lived in one.
# Kural 17 gained "This is like how a society thrives only when its successful
# people contribute back to it", which appears in no source and would have
# been retrieved and then cited with a kural number attached.
#
# The instruction now forbids these, and this catches it when the instruction
# is ignored. A rule nothing checks is a wish.
ADDED_SENTENCE_OPENERS = re.compile(
    r"(?:^|\.\s+)(this is because|this means|this is like|this shows|"
    r"in other words|that is to say|therefore|thus,|so,|for example|"
    r"in essence|essentially)", re.IGNORECASE)

INSTRUCTION = """You rewrite the meaning of an old Tamil verse into plain \
modern English.

You will be given one verse in Tamil, several English translations of it, and \
several Tamil explanations and classical commentaries. They all describe the \
SAME verse. Read all of them, then write what it means.

RULES, in order of importance:

1. WRITE ONE SENTENCE. Use a second sentence ONLY if the sources themselves \
make two separate statements. Never add a second sentence to explain, to \
justify, to give an example, or to draw a lesson. If you are about to write \
"This is because", "This means", "This is like", or "In other words", stop - \
that sentence does not belong here.

2. PARAPHRASE, DO NOT INTERPRET. Say only what the sources say. Do not add a \
lesson, an application, an example, or a conclusion of your own. If the \
sources disagree, follow the ones that agree with each other. Do not borrow \
an idea from a neighbouring verse, however related it seems.

3. No old-fashioned words. No inverted word order. No bracketed glosses. \
Write "someone who" rather than "he who", "should not" rather than "let him \
not".

4. KEEP THE SPECIFIC WORDS. If it says anger against the weak, do not write \
"negative emotions". If it says wealth, do not write "resources". The exact \
nouns are what make it findable.

5. Never mention Thirukkural, kural, verse, couplet, chapter, or Valluvar. \
Write the meaning itself, not a description of a verse.

Reply with the sentences only. No preamble, no quotes, no numbering."""


def load_kurals():
    """The corpus. Read only - this file is never written by this script."""
    with open(CORPUS_PATH, encoding="utf-8") as open_file:
        return json.load(open_file)


def build_sources_block(record):
    """Everything we know about one kural, laid out for the model.

    All eleven fields go in. Withholding any of them would be choosing which
    source is best before measuring, and the whole point is that no single
    field carries the full meaning - the English is archaic, the Tamil
    commentaries are the closest to the original, and the modern Tamil
    paraphrases are the clearest.
    """
    return "\n".join([
        f"TAMIL VERSE:\n  {record['kural_line1']}\n  {record['kural_line2']}",
        "",
        f"ENGLISH TRANSLATION 1: {record['english_translation']}",
        f"ENGLISH TRANSLATION 2: {record['english_couplet']}",
        f"ENGLISH EXPLANATION:   {record['english_explanation']}",
        "",
        f"TAMIL MEANING 1: {record['tamil_meaning_mu_varadarajan']}",
        f"TAMIL MEANING 2: {record['tamil_meaning_solomon_pappaiah']}",
        f"TAMIL MEANING 3: {record['tamil_meaning_karunanidhi']}",
        "",
        f"CLASSICAL COMMENTARY (Parimelazhagar):\n"
        f"  {record['parimelazhagar_commentary']}",
        f"CLASSICAL COMMENTARY (Manakkudavar):\n"
        f"  {record['manakkudavar_commentary']}",
    ])


def tidy(text):
    """Strip the wrappers a model puts around its answer."""
    text = text.strip()
    if "</think>" in text:
        text = text.split("</think>")[-1].strip()
    # Some models open with "Meaning:" or wrap the whole thing in quotes.
    for prefix in ("meaning:", "modern english:", "answer:", "statement:"):
        if text.lower().startswith(prefix):
            text = text[len(prefix):].strip()
    return text.strip('"').strip()


def load_existing():
    """Rewrites already paid for, keyed by kural number."""
    existing = {}
    if not MODERN_PATH.exists():
        return existing
    with open(MODERN_PATH, encoding="utf-8") as open_file:
        for line in open_file:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue          # a line cut short by a killed process
            existing[entry["number"]] = entry["modern"]
    return existing


# ----------------------------------------------------------------------
# stage 1 - write them
# ----------------------------------------------------------------------

def write_all(kurals, only_numbers=None, note=None, at_once=AT_ONCE):
    """Rewrite every kural that does not already have one.

    Runs several calls at the same time. Almost all of the time here is spent
    waiting for a reply, not computing, so eight requests in flight finish in
    roughly the time one does. Measured: 4.3 s each one at a time, which is
    95 minutes for 1330.

    Every finished rewrite is appended immediately, so stopping this half way
    costs nothing - restarting skips whatever is already on disk.
    """
    existing = load_existing()
    todo = [record for record in kurals
            if record["number"] not in existing
            and (only_numbers is None or record["number"] in only_numbers)]

    if not todo:
        print(f"all {len(existing)} rewrites already on disk, nothing to do")
        return existing

    model = HostedModel("sarvam")
    print(f"{len(existing)} already done, writing {len(todo)} more "
          f"({at_once} at a time)")
    started_at = time.perf_counter()

    # One writer at a time, or two half-written lines interleave and the file
    # is corrupt. Held only for the instant an append takes.
    write_lock = threading.Lock()
    done_count = 0

    def rewrite_one(record):
        nonlocal done_count
        message = build_sources_block(record)
        if note:
            # Used when regenerating a rejected rewrite: the reviewer's exact
            # objection goes back to the model, so the second attempt is aimed
            # rather than a reroll of the same dice.
            message += f"\n\nA previous attempt was rejected because: {note}"
        modern = None
        for attempt, wait_seconds in enumerate(RATE_LIMIT_WAITS, start=1):
            try:
                modern = tidy(model.ask(INSTRUCTION, message,
                                        max_output_tokens=MAX_OUTPUT_TOKENS))
                break
            except Exception as error:
                # Only a rate limit is worth waiting out. Anything else -
                # a bad request, a dead model name - will fail identically
                # in ninety seconds, so it is reported straight away.
                if "rate_limit" not in str(error).lower():
                    print(f"  kural {record['number']}: {error}")
                    return None
                if attempt == len(RATE_LIMIT_WAITS):
                    print(f"  kural {record['number']}: still rate limited "
                          f"after {attempt} tries, giving up on this one")
                    return None
                time.sleep(wait_seconds)
        if modern is None:
            return None

        with write_lock:
            existing[record["number"]] = modern
            with open(MODERN_PATH, "a", encoding="utf-8") as open_file:
                json.dump({"number": record["number"],
                           "chapter": record["chapter_english"],
                           "old": record["english_explanation"],
                           "modern": modern}, open_file, ensure_ascii=False)
                open_file.write("\n")
            done_count += 1
            if done_count % 50 == 0:
                elapsed = time.perf_counter() - started_at
                per = elapsed / done_count
                left = (len(todo) - done_count) * per / 60
                print(f"  {done_count}/{len(todo)}  {per:.2f}s each, "
                      f"Rs {model.rupees_spent():.2f} so far, "
                      f"~{left:.0f} min left")
        return modern

    with ThreadPoolExecutor(max_workers=at_once) as pool:
        list(pool.map(rewrite_one, todo))

    print(f"done in {(time.perf_counter() - started_at) / 60:.1f} min. "
          f"{model.cost_report()}")
    return existing


# ----------------------------------------------------------------------
# checks
# ----------------------------------------------------------------------

def check(kurals):
    """Validate every rewrite. Prints problems; says nothing when clean."""
    modern = load_existing()
    problems = []

    for record in kurals:
        number = record["number"]
        if number not in modern:
            problems.append((number, "missing"))
            continue
        text = modern[number]
        if not text.strip():
            problems.append((number, "empty"))
        elif len(text) < 25:
            problems.append((number, f"suspiciously short: {text!r}"))
        elif len(text) > 600:
            problems.append((number, f"far too long: {len(text)} characters"))
        found = FORBIDDEN_WORDS.findall(text)
        if found:
            problems.append((number, f"mentions the book: {set(found)}"))
        added = ADDED_SENTENCE_OPENERS.findall(text)
        if added:
            problems.append((number,
                             f"looks like an added sentence: {added}"))

    print(f"{len(modern)} of {len(kurals)} kurals have a modern version")
    if not problems:
        print("no problems found")
        return True

    print(f"{len(problems)} problems:")
    for number, why in problems[:40]:
        print(f"  kural {number}: {why}")
    if len(problems) > 40:
        print(f"  ... and {len(problems) - 40} more")
    return False


def show(kurals, how_many):
    """Old and new, side by side, for a random sample."""
    modern = load_existing()
    have = [record for record in kurals if record["number"] in modern]
    for record in random.Random(20260803).sample(
            have, min(how_many, len(have))):
        print("=" * 76)
        print(f"kural {record['number']}  [{record['chapter_english']}]")
        print(f"  verse   {record['english_translation']}")
        print(f"  OLD     {record['english_explanation']}")
        print(f"  MODERN  {modern[record['number']]}")
        print()


# ----------------------------------------------------------------------
# stage 2 - a second model reviews every rewrite
# ----------------------------------------------------------------------
#
# Sarvam wrote these, so Sarvam cannot be the one to check them. We proved
# that today on the citation work: asked to judge its own answers it called
# 92% of them clean, and marked a word-for-word quote "unsupported".
#
# So the reviewer is a model from a different company, reached by pasting.
# Terse output on purpose - a reviewer asked to comment on all 1330 writes
# 1330 paragraphs saying "this is fine", and the few real problems drown.

REVIEW_INSTRUCTION = """Read these two files:

  {modern_path}
      One JSON object per line. "number" is the kural number, "modern" is a
      new plain-English version of that kural's meaning, written by another
      model. There are {count} of them.

  {corpus_path}
      The source data for all 1330 kurals. For each one, the fields that
      matter here are english_translation, english_couplet,
      english_explanation, and tamil_meaning_mu_varadarajan.

For every kural, one question:

  DOES THE "modern" TEXT SAY THE SAME THING AS THE SOURCE FIELDS?

Say WRONG if it changed the meaning, added something the sources do not say,
or dropped part of what they say. Otherwise say OK.

Write your answer to:

  {output_path}

One JSON object per line, nothing else in the file:

  {{"number": 1, "verdict": "OK"}}
  {{"number": 2, "verdict": "WRONG", "reason": "dropped 'when it can injure'"}}

Cover all {count} kurals. Do not skip any, and do not summarise."""


def review_prompt(kurals):
    """Print the prompt to hand a file-reading assistant. Nothing is pasted.

    GPT runs inside the editor and can open these files itself, so the job is
    to tell it where they are and where to put its answer - not to carve the
    corpus into 23 clipboard-sized pieces.
    """
    modern = load_existing()
    REVIEW_DIRECTORY.mkdir(parents=True, exist_ok=True)
    print(REVIEW_INSTRUCTION.format(
        modern_path=MODERN_PATH,
        corpus_path=CORPUS_PATH,
        output_path=REVIEW_REPLIES_PATH,
        count=len(modern)))


def collect_review(kurals):
    """Read the reviewer's file and record its verdict against each kural.

    Keyed by KURAL NUMBER, not by position in a list. The reviewer works
    through the file in its own order and may skip or repeat; a position-based
    join would silently attach the wrong verdict to the wrong verse, and
    nothing downstream would notice.
    """
    if not REVIEW_REPLIES_PATH.exists():
        raise SystemExit(
            f"no review file at {REVIEW_REPLIES_PATH}\n"
            f"Ask GPT to write it - see --gpt-prompt for the wording.")

    modern = load_existing()
    by_number = {record["number"]: record for record in kurals}

    verdicts = {}
    for line in REVIEW_REPLIES_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip().rstrip(",")
        if not line.startswith("{"):
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "number" not in entry or "verdict" not in entry:
            continue
        verdicts[int(entry["number"])] = {
            "verdict": str(entry["verdict"]).strip().upper(),
            "reason": str(entry.get("reason", "")).strip(),
        }

    reviewed = []
    for number, verdict in sorted(verdicts.items()):
        if number not in modern or number not in by_number:
            continue
        reviewed.append({
            "number": number,
            "chapter": by_number[number]["chapter_english"],
            "modern": modern[number],
            **verdict,
        })
    rows = [record for record in kurals if record["number"] in modern]

    with open(REVIEW_PATH, "w", encoding="utf-8") as open_file:
        json.dump(reviewed, open_file, ensure_ascii=False, indent=2)

    flagged = [item for item in reviewed if item["verdict"] != "OK"]
    missing = [record["number"] for record in rows
               if record["number"] not in verdicts]

    print(f"collected {len(reviewed)} of {len(rows)} verdicts")
    if missing:
        print(f"  {len(missing)} items have no verdict yet: "
              f"{missing[:15]}{' ...' if len(missing) > 15 else ''}")
    print(f"  OK     {len(reviewed) - len(flagged)}")
    print(f"  WRONG  {len(flagged)}")

    if flagged:
        print()
        print("  first few:")
        for item in flagged[:10]:
            print(f"    kural {item['number']}: {item['reason']}")

    print()
    print("Nothing is regenerated yet - I read these before anything is "
          "rewritten, including a sample of the ones marked OK.")
    return reviewed


def main():
    arguments = sys.argv[1:]
    kurals = load_kurals()

    if "--gpt-prompt" in arguments or "--review-files" in arguments:
        REVIEW_DIRECTORY.mkdir(parents=True, exist_ok=True)
        review_prompt(kurals)
        return

    if "--collect-review" in arguments or "--collect-gpt" in arguments:
        collect_review(kurals)
        return

    if "--check" in arguments:
        raise SystemExit(0 if check(kurals) else 1)

    if "--show" in arguments:
        position = arguments.index("--show")
        how_many = int(arguments[position + 1]) if len(arguments) > position + 1 else 20
        show(kurals, how_many)
        return

    write_all(kurals)
    print()
    check(kurals)


if __name__ == "__main__":
    main()
