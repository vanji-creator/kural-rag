"""Does each cited verse actually support the claim in front of it?

WHY THIS IS HARDER THAN THE CHECK WE ALREADY HAVE

src/generate.py already checks that a cited NUMBER was one we supplied. That
catches an invented number and nothing else. It cannot catch this:

    "Anger destroys friendship [301]"

301 is a verse we supplied, so that check passes. But kural 301 says anger
against the weak is wrong and futile against the strong. It says nothing about
friendship. The number is real and the claim is invented.

Deciding whether a sentence is supported by a verse is a reading task, so the
only tool that scales to 233 questions is another language model. That is a
real technique with a real name - LLM-as-judge - and it comes with a real
danger.

THE DANGER, AND WHAT THIS FILE DOES ABOUT IT

A judge is a measuring instrument. An unchecked instrument is not a
measurement, it is a second opinion. Worse here: the same author wrote the
generator's instruction and the judge's instruction, so both can share the
same blind spot and agree with each other while both being wrong.

So this file does NOT report a number on its own. It writes its verdicts to
a file with the verdicts HIDDEN, so a human can label the same claims without
seeing them, and then `--score` compares the two.

A judge that disagrees with the human is thrown away, not published.

WHY THE JUDGE IS ALLOWED TO BE A BIG MODEL WHEN THE REWRITER WAS NOT

The rewriter runs on every query a user types, forever - so it has to be a
model we can actually afford to deploy. The judge runs once, offline, to
produce a number for a report. Nobody pays for it per query. Different job,
different rule.

Run it:

    venv/bin/python -u src/judge_citations.py --sample 30    # judge a sample
    venv/bin/python -u src/judge_citations.py --blank        # human worksheet
    venv/bin/python -u src/judge_citations.py --score        # compare the two
    venv/bin/python -u src/judge_citations.py --all          # all 233, at the end
"""

import json
import random
import re
import sys
from pathlib import Path

from benchmark_chapters import load_questions
from generate import AnswerWriter
from llm import HostedModel
from pipeline import KuralRetriever

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIRECTORY = PROJECT_ROOT / "data"
ANSWERS_PATH = DATA_DIRECTORY / "generated_answers.json"
JUDGE_PATH = DATA_DIRECTORY / "citation_verdicts.json"
HUMAN_PATH = DATA_DIRECTORY / "citation_verdicts_human.json"
GPT_PATH = DATA_DIRECTORY / "citation_verdicts_gpt.json"

# The task for a second model, from a different company. Deliberately the same
# rules the human worksheet states, word for word where possible - if the two
# judges were given different instructions, any disagreement between them
# would partly be measuring the instructions rather than the judges.
GPT_TASK_HEADER = """You are checking whether a quoted source supports a \
claim. Be strict and literal.

Each item below gives you ONE claim and ONE verse from the Thirukkural, an \
ancient Tamil book of short moral verses. The claim comes from an answer \
that was supposed to be written using only that verse.

For each item, reply with exactly one word:

SUPPORTED   - the verse plainly says this. Different wording is fine; the \
meaning must be the same.
PARTIAL     - the verse is about this subject, but the claim adds something \
the verse does not say, or shifts who or what it applies to.
UNSUPPORTED - the verse does not say this. It may be about a different \
subject entirely, or it may contradict the claim.

IMPORTANT: judge ONLY against the verse text given to you. Do not use \
anything you know about the Thirukkural from elsewhere. If the verse alone \
does not establish the claim, it is not supported - however true the claim \
may be in general.

Give no explanation. One numbered line per item."""

# Same seed every time, so "the sample" means the same 30 claims on every run
# and two people comparing notes are looking at the same thing.
SAMPLE_SEED = 20260803

JUDGE_INSTRUCTION = """You check whether a quoted source supports a claim. \
You are strict and literal.

You will be given ONE claim and ONE verse from the Thirukkural, an old Tamil \
book. Decide whether the verse supports the claim.

Answer with exactly one word:

SUPPORTED   - the verse plainly says this. Different wording is fine; the \
meaning must be the same.
PARTIAL     - the verse is about this subject but the claim adds something \
the verse does not say, or shifts who or what it applies to.
UNSUPPORTED - the verse does not say this. It may be about a different \
subject entirely, or it may contradict the claim.

Judge ONLY against the verse text given. Do not use anything you know about \
the Thirukkural from elsewhere. If the verse alone does not establish the \
claim, it is not supported, however true the claim may be.

Reply with the single word and nothing else."""


def claim_pairs(answer):
    """Split one answer into (sentence, cited number) pairs.

    A citation sits at the end of the sentence it supports, so the text
    between the previous citation and this one is the claim being made.
    """
    pairs = []
    for part in answer["parts"]:
        if part["cite"] is None:
            continue
        # The split happens AT the citation, so the punctuation that ended the
        # previous sentence is glued to the front of this one - every claim
        # after the first began ". This is because...". Strip it, or the
        # person reading 113 of these reads 113 stray full stops.
        sentence = part["text"].strip().lstrip(".,;: ").strip()
        if sentence:
            pairs.append((sentence, part["cite"]))
    return pairs


def build_answers(questions, top_k=5):
    """Generate an answer for every question, keeping the verses used."""
    retriever = KuralRetriever()
    writer = AnswerWriter()

    records = []
    for index, question in enumerate(questions, start=1):
        outcome = retriever.search(question, top_k=top_k)
        supplied = [item["kural"] for item in outcome["results"]]
        answer = writer.write(question, supplied)
        records.append({
            "question": question,
            "suppliedNumbers": [record["number"] for record in supplied],
            "verses": {str(record["number"]): {
                "translation": record["english_translation"],
                "explanation": record["english_explanation"],
                "chapter": record["chapter_english"]} for record in supplied},
            "answer": answer["rawText"],
            "parts": answer["parts"],
            "citations": answer["citations"],
        })
        if index % 10 == 0:
            print(f"  {index}/{len(questions)} answers, "
                  f"Rs {writer.model.rupees_spent():.3f}")

    print(f"  done. {writer.model.cost_report()}")
    return records


def judge_one(judge, claim, verse):
    """One claim, one verse, one word back."""
    message = (f"CLAIM:\n{claim}\n\n"
               f"VERSE {verse['number']}:\n"
               f"  {verse['translation']}\n"
               f"  meaning: {verse['explanation']}")
    reply = judge.ask(JUDGE_INSTRUCTION, message, max_output_tokens=12)
    word = reply.strip().upper().split()[0].strip(".:,") if reply.strip() else ""
    return word if word in ("SUPPORTED", "PARTIAL", "UNSUPPORTED") else "UNCLEAR"


def main():
    DATA_DIRECTORY.mkdir(exist_ok=True)
    arguments = sys.argv[1:]

    # ---- compare the judge against the human labels --------------------
    if "--score" in arguments:
        if not JUDGE_PATH.exists():
            raise SystemExit(f"no {JUDGE_PATH.name}. Run --sample first.")

        def load_verdicts(path):
            if not path.exists():
                return {}
            return {item["id"]: item["verdict"].upper()
                    for item in json.load(open(path, encoding="utf-8"))
                    if item.get("verdict", "").strip()}

        rows = {item["id"]: item for item in json.load(open(JUDGE_PATH,
                                                           encoding="utf-8"))}
        sarvam = load_verdicts(JUDGE_PATH)
        gpt = load_verdicts(GPT_PATH)
        human = load_verdicts(HUMAN_PATH)

        print("=" * 70)
        print(f"{'judge':22s} {'labelled':>10s}   what it said")
        print("=" * 70)
        for name, verdicts in (("Sarvam-105B", sarvam),
                               ("GPT (in VS Code)", gpt),
                               ("you, by hand", human)):
            if not verdicts:
                print(f"{name:22s} {'-':>10s}   not run yet")
                continue
            counts = {}
            for verdict in verdicts.values():
                counts[verdict] = counts.get(verdict, 0) + 1
            spread = "  ".join(
                f"{verdict[:4]} {count:3d} ({count / len(verdicts) * 100:.0f}%)"
                for verdict, count in sorted(counts.items(),
                                             key=lambda pair: -pair[1]))
            print(f"{name:22s} {len(verdicts):>10d}   {spread}")

        def agreement(name_a, a, name_b, b):
            shared = [key for key in a if key in b]
            if not shared:
                print(f"\n{name_a} vs {name_b}: no claims labelled by both")
                return
            same = sum(1 for key in shared if a[key] == b[key])
            print(f"\n{name_a} vs {name_b}: "
                  f"{same}/{len(shared)} = {same / len(shared) * 100:.0f}% agree")
            for key in shared:
                if a[key] != b[key]:
                    print(f"    {name_a} {a[key]:12s} | {name_b} {b[key]}")
                    print(f"      claim: {rows[key]['claim'][:100]}")
                    print(f"      verse: {rows[key]['verseTranslation'][:100]}")

        print()
        print("=" * 70)
        print("DO THEY AGREE?")
        print("=" * 70)
        agreement("Sarvam", sarvam, "GPT", gpt)
        if human:
            agreement("Sarvam", sarvam, "you", human)
            agreement("GPT", gpt, "you", human)

        # A judge is only proven by the labels that could have caught it out.
        # If every human label says SUPPORTED, then a judge that says
        # SUPPORTED to absolutely everything scores 100% - and it would be a
        # useless judge. This warns rather than letting that pass as proof.
        if human:
            distinct = set(human.values())
            print()
            print("=" * 70)
            if len(distinct) < 2:
                print("WARNING: EVERY ONE OF YOUR LABELS IS THE SAME VERDICT")
                print(f"  You marked {len(human)} claims and all say "
                      f"{distinct.pop()}.")
                print("  A judge that answered that word to EVERY claim would")
                print("  score 100% against these labels. So high agreement")
                print("  here does NOT show the judge can spot a bad citation")
                print("  - only that it agrees when things are fine.")
                print()
                print("  To make this a real test, label some claims you")
                print("  expect to FAIL. The disagreements listed above are")
                print("  the place to look.")
            else:
                print(f"your labels contain {len(distinct)} different verdicts "
                      f"- the test can catch a judge in both directions")
        return

    # ---- the human worksheet -------------------------------------------
    if "--blank" in arguments:
        # REFUSE to overwrite work. This nearly destroyed a half-finished
        # worksheet on 2026-08-03: a background job had --blank chained after
        # a long --rejudge, and rewrote the file an hour after it was handed
        # over. Hand-labelling is the most expensive input in this project -
        # it is a person's attention, and it cannot be regenerated for Rs 2.
        readable = HUMAN_PATH.with_suffix(".md")
        for path in (readable, HUMAN_PATH):
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            has_work = ('"verdict": "S' in text or '"verdict": "P' in text
                        or '"verdict": "U' in text
                        or any(line.startswith("verdict:") and line[8:].strip()
                               for line in text.splitlines()))
            if has_work and "--force" not in arguments:
                raise SystemExit(
                    f"{path.name} already has verdicts written in it.\n"
                    f"Refusing to overwrite them. If you really want a fresh "
                    f"blank worksheet, move that file aside first, or pass "
                    f"--force.")

        # Built from the ANSWERS, not from the judge's verdicts. That is not a
        # convenience - it is the control. A worksheet derived from the judge's
        # output could leak its opinion through ordering or through a field
        # left in by mistake. This file cannot leak what it never read.
        records = json.load(open(ANSWERS_PATH, encoding="utf-8"))
        rows = []
        for record in records:
            for position, (claim, number) in enumerate(claim_pairs(record)):
                verse = record["verses"][str(number)]
                rows.append({
                    "id": f"{record['question'][:40]}#{position}",
                    "question": record["question"],
                    "claim": claim,
                    "verseNumber": number,
                    "verseTranslation": verse["translation"],
                    "verseExplanation": verse["explanation"],
                    "verdict": "",
                })

        with open(HUMAN_PATH, "w", encoding="utf-8") as open_file:
            json.dump(rows, open_file, ensure_ascii=False, indent=2)

        # A readable version to actually work through. Editing 113 rows of
        # raw data is a good way to give up halfway.
        readable = HUMAN_PATH.with_suffix(".md")
        with open(readable, "w", encoding="utf-8") as open_file:
            open_file.write(
                "# Citation worksheet\n\n"
                "For each one: does the VERSE support the CLAIM?\n\n"
                "Write one word on the `verdict:` line —\n"
                "`SUPPORTED`, `PARTIAL`, or `UNSUPPORTED`.\n\n"
                "Judge ONLY against the verse shown. Not what you know the\n"
                "Thirukkural says elsewhere. If the verse alone does not\n"
                "establish the claim, it is not supported — however true the\n"
                "claim happens to be.\n\n"
                "About 40 is enough to decide whether the machine can be\n"
                "trusted with the rest. Stop when you have had enough; only\n"
                "the rows you fill in are counted.\n\n"
                "---\n\n")
            for index, row in enumerate(rows, start=1):
                open_file.write(
                    f"## {index}. {row['question']}\n\n"
                    f"**claim** {row['claim']}\n\n"
                    f"**verse {row['verseNumber']}** "
                    f"{row['verseTranslation']}\n\n"
                    f"> {row['verseExplanation']}\n\n"
                    f"verdict: \n\n---\n\n")

        print(f"{len(rows)} claims to label")
        print(f"  read and fill in : {readable}")
        print(f"  or edit directly : {HUMAN_PATH}")
        print()
        print("The judge's verdicts are NOT in either file, on purpose.")
        print("When you are done:")
        print("  venv/bin/python src/judge_citations.py --collect   "
              "(if you used the .md)")
        print("  venv/bin/python src/judge_citations.py --score")
        return

    # ---- a prompt to paste into a different model ----------------------
    #
    # A second judge from a different company is worth having: it fails in
    # different places than Sarvam does. It is NOT a replacement for the human
    # labels. Two models agreeing can mean both are right, or that both were
    # trained on similar text and share a blind spot - and those two look
    # identical from the outside. Only a person breaks that tie.
    if "--gpt-prompt" in arguments:
        records = json.load(open(ANSWERS_PATH, encoding="utf-8"))
        rows = []
        for record in records:
            for position, (claim, number) in enumerate(claim_pairs(record)):
                verse = record["verses"][str(number)]
                rows.append((claim, number, verse))

        per_file = 40                       # keeps each paste a sane length
        chunk_paths = []
        for start in range(0, len(rows), per_file):
            chunk = rows[start:start + per_file]
            path = DATA_DIRECTORY / f"gpt_task_{start // per_file + 1}.md"
            with open(path, "w", encoding="utf-8") as open_file:
                open_file.write(GPT_TASK_HEADER)
                open_file.write(
                    f"\nThere are {len(chunk)} items below, numbered "
                    f"{start + 1} to {start + len(chunk)}.\n"
                    f"Reply with exactly {len(chunk)} lines, nothing else:\n\n"
                    f"{start + 1}. SUPPORTED\n{start + 2}. PARTIAL\n"
                    f"{start + 3}. UNSUPPORTED\n...\n\n---\n\n")
                for offset, (claim, number, verse) in enumerate(chunk):
                    open_file.write(
                        f"**{start + offset + 1}.**\n"
                        f"CLAIM: {claim}\n"
                        f"VERSE {number}: {verse['translation']}\n"
                        f"MEANING: {verse['explanation']}\n\n")
            chunk_paths.append(path)

        print(f"{len(rows)} claims split into {len(chunk_paths)} files.")
        print("Paste each one into GPT as a separate message:")
        for path in chunk_paths:
            print(f"  {path}")
        print()
        print("Save its replies, all together, into:")
        print(f"  {DATA_DIRECTORY / 'gpt_replies.txt'}")
        print("Then: venv/bin/python src/judge_citations.py --collect-gpt")
        return

    # ---- read a second model's replies back in -------------------------
    if "--collect-gpt" in arguments:
        replies_path = DATA_DIRECTORY / "gpt_replies.txt"
        if not replies_path.exists():
            raise SystemExit(f"paste the replies into {replies_path} first")

        records = json.load(open(ANSWERS_PATH, encoding="utf-8"))
        ordered = []
        for record in records:
            for position, (claim, number) in enumerate(claim_pairs(record)):
                ordered.append({
                    "id": f"{record['question'][:40]}#{position}",
                    "claim": claim,
                    "verseNumber": number,
                })

        # Read "12. SUPPORTED" lines, keyed by their number, so replies pasted
        # out of order or with chat chatter around them still land correctly.
        by_position = {}
        for line in replies_path.read_text(encoding="utf-8").splitlines():
            match = re.match(r"\s*(\d+)[.):]\s*([A-Za-z_]+)", line)
            if not match:
                continue
            verdict = match.group(2).upper()
            if verdict in ("SUPPORTED", "PARTIAL", "UNSUPPORTED"):
                by_position[int(match.group(1))] = verdict

        collected = []
        for index, row in enumerate(ordered, start=1):
            if index in by_position:
                collected.append(dict(row, verdict=by_position[index]))
        with open(GPT_PATH, "w", encoding="utf-8") as open_file:
            json.dump(collected, open_file, ensure_ascii=False, indent=2)
        print(f"collected {len(collected)} of {len(ordered)} verdicts")
        missing = [i for i in range(1, len(ordered) + 1)
                   if i not in by_position]
        if missing:
            print(f"  missing numbers: {missing[:20]}"
                  + (" ..." if len(missing) > 20 else ""))
        return

    # ---- read the verdicts back out of the readable worksheet ----------
    if "--collect" in arguments:
        readable = HUMAN_PATH.with_suffix(".md")
        rows = json.load(open(HUMAN_PATH, encoding="utf-8"))
        text = readable.read_text(encoding="utf-8")

        written = [line.split("verdict:", 1)[1].strip().upper()
                   for line in text.splitlines()
                   if line.startswith("verdict:")]
        if len(written) != len(rows):
            raise SystemExit(
                f"{readable.name} has {len(written)} verdict lines but there "
                f"are {len(rows)} claims. Do not add or remove sections - "
                f"only fill in the blanks.")

        filled = 0
        for row, verdict in zip(rows, written):
            if verdict in ("SUPPORTED", "PARTIAL", "UNSUPPORTED"):
                row["verdict"] = verdict
                filled += 1
            elif verdict:
                print(f"  ignoring unrecognised verdict {verdict!r} "
                      f"on: {row['claim'][:60]}")
        with open(HUMAN_PATH, "w", encoding="utf-8") as open_file:
            json.dump(rows, open_file, ensure_ascii=False, indent=2)
        print(f"collected {filled} of {len(rows)} verdicts")
        print("  next: venv/bin/python src/judge_citations.py --score")
        return

    # ---- generate answers and judge them -------------------------------
    set_a, set_b = load_questions()
    all_questions = [question for question, _ in set_a + set_b]

    if "--all" in arguments:
        questions = all_questions
    else:
        how_many = 30
        if "--sample" in arguments:
            how_many = int(arguments[arguments.index("--sample") + 1])
        random.Random(SAMPLE_SEED).shuffle(all_questions)
        questions = all_questions[:how_many]

    # Re-judge the answers already on disk. Used when only the claim-splitting
    # changed: the answers cost real money and did not change, so paying to
    # generate them again would buy nothing. It also guarantees the judge and
    # the human worksheet are built from the SAME text - if they drifted, the
    # agreement number would partly be measuring the difference between them.
    if "--rejudge" in arguments:
        records = json.load(open(ANSWERS_PATH, encoding="utf-8"))
        print(f"re-judging {len(records)} answers already on disk")
    else:
        print(f"generating answers for {len(questions)} questions...")
        records = build_answers(questions)
        with open(ANSWERS_PATH, "w", encoding="utf-8") as open_file:
            json.dump(records, open_file, ensure_ascii=False, indent=2)

    print()
    print("judging every claim...")
    judge = HostedModel("sarvam")
    verdicts = []
    failures = 0
    for record in records:
        for position, (claim, number) in enumerate(claim_pairs(record)):
            verse = dict(record["verses"][str(number)], number=number)
            # One bad network call must not destroy the whole run. The first
            # attempt at this lost ~450 judged claims to a single timeout,
            # after the retries the client already makes had been exhausted.
            try:
                verdict = judge_one(judge, claim, verse)
            except Exception as error:
                failures += 1
                verdict = "FAILED"
                print(f"  claim {len(verdicts) + 1}: {error}")
            verdicts.append({
                "id": f"{record['question'][:40]}#{position}",
                "question": record["question"],
                "claim": claim,
                "verseNumber": number,
                "verseTranslation": verse["translation"],
                "verseExplanation": verse["explanation"],
                "verdict": verdict,
            })
            # Written after every single claim. Judging costs real money and
            # real minutes; a crash at claim 400 should cost claim 400, not
            # claims 1 through 400.
            if len(verdicts) % 10 == 0:
                with open(JUDGE_PATH, "w", encoding="utf-8") as open_file:
                    json.dump(verdicts, open_file, ensure_ascii=False, indent=2)
                print(f"  {len(verdicts)} judged, "
                      f"Rs {judge.rupees_spent():.3f}")

    with open(JUDGE_PATH, "w", encoding="utf-8") as open_file:
        json.dump(verdicts, open_file, ensure_ascii=False, indent=2)
    if failures:
        print(f"  {failures} claims could not be judged and are marked FAILED")

    counts = {}
    for item in verdicts:
        counts[item["verdict"]] = counts.get(item["verdict"], 0) + 1

    print()
    print(f"{len(verdicts)} claims judged   {judge.cost_report()}")
    for verdict in ("SUPPORTED", "PARTIAL", "UNSUPPORTED", "UNCLEAR"):
        if verdict in counts:
            print(f"  {verdict:12s} {counts[verdict]:4d}  "
                  f"{counts[verdict] / len(verdicts) * 100:5.1f}%")
    print()
    print("THIS IS NOT A RESULT YET. The judge has not been checked.")
    print("  next:  venv/bin/python src/judge_citations.py --blank")


if __name__ == "__main__":
    main()
