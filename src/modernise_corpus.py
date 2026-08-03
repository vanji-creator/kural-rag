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
import time
from pathlib import Path

from llm import HostedModel

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CORPUS_PATH = PROJECT_ROOT / "data" / "kurals.json"
MODERN_PATH = PROJECT_ROOT / "data" / "modern_explanations.jsonl"

# One or two sentences. 160 leaves room to finish a thought and not to ramble.
MAX_OUTPUT_TOKENS = 160

# Words that would give away that this text came from a book of numbered
# verses. They must not appear: the search text should read as a statement
# about life, because that is what a question is about.
FORBIDDEN_WORDS = re.compile(
    r"\b(kural|thirukkural|thirukural|couplet|verse|chapter|valluvar|"
    r"thiruvalluvar)\b", re.IGNORECASE)

INSTRUCTION = """You rewrite the meaning of an old Tamil verse into plain \
modern English.

You will be given one verse in Tamil, several English translations of it, and \
several Tamil explanations and classical commentaries. They all describe the \
SAME verse. Read all of them, then write what it means.

RULES, in order of importance:

1. Write 1 to 2 sentences of plain modern English. Write the way a person \
writes today.

2. PARAPHRASE, DO NOT INTERPRET. Say only what the sources say. Do not add a \
lesson, an application, an example, or a conclusion of your own. If the \
sources disagree, follow the ones that agree with each other.

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

def write_all(kurals, only_numbers=None, note=None):
    """Rewrite every kural that does not already have one."""
    existing = load_existing()
    todo = [record for record in kurals
            if record["number"] not in existing
            and (only_numbers is None or record["number"] in only_numbers)]

    if not todo:
        print(f"all {len(existing)} rewrites already on disk, nothing to do")
        return existing

    model = HostedModel("sarvam")
    print(f"{len(existing)} already done, writing {len(todo)} more")
    started_at = time.perf_counter()

    for index, record in enumerate(todo, start=1):
        message = build_sources_block(record)
        if note:
            # Used when regenerating a rejected rewrite: the reviewer's exact
            # objection goes back to the model, so the second attempt is aimed
            # rather than just a reroll of the same dice.
            message += f"\n\nA previous attempt was rejected because: {note}"
        try:
            modern = tidy(model.ask(INSTRUCTION, message,
                                    max_output_tokens=MAX_OUTPUT_TOKENS))
        except Exception as error:
            print(f"  kural {record['number']}: {error}")
            continue

        existing[record["number"]] = modern
        with open(MODERN_PATH, "a", encoding="utf-8") as open_file:
            json.dump({"number": record["number"],
                       "chapter": record["chapter_english"],
                       "old": record["english_explanation"],
                       "modern": modern}, open_file, ensure_ascii=False)
            open_file.write("\n")

        if index % 25 == 0:
            per = (time.perf_counter() - started_at) / index
            left = (len(todo) - index) * per / 60
            print(f"  {index}/{len(todo)}  {per:.2f}s each, "
                  f"Rs {model.rupees_spent():.2f} so far, ~{left:.0f} min left")

    print(f"done. {model.cost_report()}")
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


def main():
    arguments = sys.argv[1:]
    kurals = load_kurals()

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
