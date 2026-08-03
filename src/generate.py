"""Write an answer using ONLY the verses that were retrieved.

WHAT THIS IS FOR

Retrieval hands back five kurals. A person still has to read five old verses
and work out what they add up to. This writes that summary - and cites the
kural number behind every claim, so nothing in it is unverifiable.

THE ONE RULE

The model may use the five verses it is given and NOTHING ELSE. Not its own
opinion about Thirukkural, not something it read during training, not a
plausible-sounding interpretation. If the verses do not answer the question,
the correct output is to say so.

That rule is easy to write into a prompt and easy for a model to break. So
this file does not trust the prompt. Every citation the model produces is
checked against the numbers that were actually supplied, and any number it
invented is reported rather than displayed.

WHAT IS DELIBERATELY NOT DECIDED HERE YET

How hard to tighten the grounding, and what to do when it slips, are the
lesson of Phase 7 - to be worked through by Vikash, not chosen for him
overnight. What this file does today is make both things VISIBLE:

    check_citations()  says exactly which numbers were invented
    the meta line      says how many claims were backed by a real verse

Tomorrow's work is to break it on purpose, watch where it fails, and decide
what to do about it. The machinery for that is here; the decisions are not.

WHAT AN ANSWER COSTS

About 600 tokens in (the question plus five verses with their explanations)
and 100 back. On Sarvam that is roughly Rs 0.004 - about half a paisa.

Run it:

    venv/bin/python src/generate.py "how do I control my anger?"
"""

import re

from llm import HostedModel

# The model is told to mark citations like [301]. Bracketed numbers are used
# because they are rare in ordinary prose, so a number that appears this way
# is almost certainly a citation and not part of a sentence.
CITATION_PATTERN = re.compile(r"\[(\d{1,4})\]")

# Long enough for a short paragraph, short enough that a model which starts
# rambling is cut off rather than billed for.
MAX_ANSWER_TOKENS = 320

INSTRUCTION = """You answer questions using ONLY the numbered verses given \
to you. The verses are from the Thirukkural, a Tamil book of 1330 short \
verses about how to live.

RULES, in order of importance:

1. Use ONLY what the given verses say. You may not add teachings, examples, \
history or interpretation from anywhere else, even if you are confident it \
is correct.

2. Cite the verse behind every claim, like this: [301]. Cite only numbers \
that appear in the list you were given. Never write a number you were not \
given.

3. If the given verses do not answer the question, say so plainly in one \
sentence and stop. Do not stretch a verse to fit. Saying "these verses do \
not address this" is a correct and useful answer.

4. Write plainly, for someone who has not read the book. Three to five \
sentences. No preamble, no "the verses say" throat-clearing - just the answer.

5. Do not quote the old-fashioned translation wording. Explain it in ordinary \
modern English.

The citation goes inside the sentence, right after the claim it supports, \
before the full stop. Like this:

  Wealth kept and never used helps nobody [1001], and the miser is poorer \
than the poor man [1005].

Every sentence you write must carry at least one citation. A sentence with \
no number after it is a sentence you invented."""


def build_verse_block(kural_records):
    """Lay the retrieved verses out for the model to read.

    The explanation is included, not just the translation. The translations
    are 19th-century English verse - "Anger against the weak is wrong It is
    futile against the strong" - and a model asked to answer from that alone
    is working from a riddle.
    """
    blocks = []
    for record in kural_records:
        blocks.append(
            f"[{record['number']}] (chapter: {record['chapter_english']})\n"
            f"  {record['english_translation']}\n"
            f"  meaning: {record['english_explanation']}")
    return "\n\n".join(blocks)


def check_citations(answer_text, allowed_numbers):
    """Which cited numbers were real, and which did the model invent?

    This is the check the prompt cannot do for itself. A model told "cite only
    these numbers" will usually obey and sometimes will not, and the failure
    looks exactly like success - a confident sentence with a number after it.
    """
    cited = [int(number) for number in CITATION_PATTERN.findall(answer_text)]
    allowed = set(allowed_numbers)
    return {
        "cited": cited,
        "real": [number for number in cited if number in allowed],
        "invented": [number for number in cited if number not in allowed],
        "distinctReal": sorted({number for number in cited
                                if number in allowed}),
    }


def split_into_parts(answer_text, allowed_numbers):
    """Turn "...restrain it [301]. Also..." into the shape the screen wants.

    lib/types.ts expects a list of {text, cite} pairs, so the interface can
    render each citation as a button that jumps to that verse. An invented
    number is dropped here rather than rendered - a button that leads to a
    verse the answer was never given would be a lie the reader can click.
    """
    allowed = set(allowed_numbers)
    parts = []
    position = 0
    for match in CITATION_PATTERN.finditer(answer_text):
        number = int(match.group(1))
        text = answer_text[position:match.start()]
        if number in allowed:
            parts.append({"text": text, "cite": number})
        else:
            # Keep the sentence, drop the false citation.
            parts.append({"text": text, "cite": None})
        position = match.end()

    remainder = answer_text[position:]
    if remainder.strip():
        parts.append({"text": remainder, "cite": None})
    if not parts:
        parts = [{"text": answer_text, "cite": None}]
    return parts


class AnswerWriter:
    """Writes grounded answers. Holds one connection to the provider."""

    def __init__(self, provider_name="sarvam"):
        self.model = HostedModel(provider_name)
        self.answers_written = 0

    def write(self, question, kural_records):
        """Return an answer shaped like AnswerParts in lib/types.ts."""
        if not kural_records:
            return None

        allowed_numbers = [record["number"] for record in kural_records]
        user_message = (f"Question: {question}\n\n"
                        f"Verses you may use:\n\n"
                        f"{build_verse_block(kural_records)}")

        answer_text = self.model.ask(INSTRUCTION, user_message,
                                     max_output_tokens=MAX_ANSWER_TOKENS)
        self.answers_written += 1

        citations = check_citations(answer_text, allowed_numbers)
        parts = split_into_parts(answer_text, allowed_numbers)

        return {
            "parts": parts,
            # How many of the supplied verses the answer actually leaned on.
            # A low number against five supplied verses is not automatically
            # wrong - it can mean only two were relevant - but it is the
            # number to watch.
            "groundedIn": len(citations["distinctReal"]),
            "meta": (f"{self.model.settings['model']} · "
                     f"{len(citations['real'])} citations checked"),
            # Everything below is for the log and for Phase 7's hallucination
            # work. The interface does not display it.
            "citations": citations,
            "rawText": answer_text,
        }


def main():
    import sys

    from pipeline import KuralRetriever

    question = " ".join(sys.argv[1:]) or "how do I control my anger?"

    retriever = KuralRetriever()
    outcome = retriever.search(question, top_k=5)
    records = [item["kural"] for item in outcome["results"]]

    print()
    print(f'question: "{question}"')
    print(f'verses given: {[record["number"] for record in records]}')
    print()

    writer = AnswerWriter()
    answer = writer.write(question, records)

    print("ANSWER")
    print(f"  {answer['rawText']}")
    print()
    print(f"  cited            {answer['citations']['cited']}")
    print(f"  real             {answer['citations']['real']}")
    print(f"  INVENTED         {answer['citations']['invented']}"
          + ("   <- the model made these up" if answer["citations"]["invented"]
             else "   (none)"))
    print(f"  grounded in      {answer['groundedIn']} verses")
    print(f"  cost             {writer.model.cost_report()}")


if __name__ == "__main__":
    main()
