"""Do the prompt's worked examples give away any test question?

WHY THIS EXISTS

The in-domain prompt teaches with examples drawn from the same world as the
corpus - gratitude, broken promises, inherited wealth. That is exactly the
situation in which a worked example stops being a teaching aid and becomes an
answer key.

"How do I control my anger" is question 1 of the golden set. An example built
on it would hand the model the answer to a question we then score it on, and
the score would go up for the wrong reason.

This project has had three leakage incidents. The last one happened AFTER a
plan promised to keep a file closed. So this is a check that runs, not a
paragraph that reassures.

WHAT IT MEASURES

For every example question in every prompt, against all 233 test questions:

    word overlap    how many meaningful words they share, as a fraction of
                    the shorter one. 1.0 means one contains the other.

Anything above the threshold is reported and the script exits non-zero.

Run it:

    venv/bin/python src/check_prompt_leakage.py
"""

import re
import sys

from benchmark_chapters import load_questions
from hyde_prompt import EXAMPLE_QUESTIONS, EXAMPLE_STATEMENTS

# Above this share of shared words, an example is too close to a test question
# to be safe. Chosen low on purpose: a false alarm costs a minute of reading,
# a missed leak costs the credibility of every number in the project.
OVERLAP_LIMIT = 0.45

# Words that two English sentences share regardless of what they are about.
# Counting them would make every pair look related.
COMMON_WORDS = {
    "a", "an", "the", "of", "to", "is", "are", "was", "were", "be", "and",
    "or", "but", "if", "in", "on", "at", "by", "for", "with", "from", "as",
    "that", "this", "it", "its", "there", "so", "than", "then", "too", "very",
    "just", "also", "about", "into", "over", "under", "up", "down", "out",
    "any", "some", "all", "how", "what", "why", "when", "where", "which",
    "who", "do", "does", "did", "can", "could", "should", "would", "will",
    "i", "me", "my", "we", "us", "our", "you", "your", "he", "him", "his",
    "she", "her", "they", "them", "their", "not", "no", "have", "has", "had",
}


def meaningful_words(text):
    """The words in a sentence that actually say what it is about."""
    words = re.findall(r"[a-z']+", text.lower())
    return {word for word in words
            if word not in COMMON_WORDS and len(word) > 2}


def overlap(text_a, text_b):
    """Shared meaningful words as a share of the smaller sentence."""
    words_a, words_b = meaningful_words(text_a), meaningful_words(text_b)
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / min(len(words_a), len(words_b))


def main():
    set_a, set_b = load_questions()
    test_questions = [question for question, _ in set_a + set_b]
    print(f"{len(EXAMPLE_QUESTIONS)} example questions and "
          f"{len(EXAMPLE_STATEMENTS)} example statements")
    print(f"checked against {len(test_questions)} test questions")
    print(f"limit: {OVERLAP_LIMIT:.0%} shared meaningful words")
    print()

    problems = []
    worst = []
    for example in EXAMPLE_QUESTIONS + EXAMPLE_STATEMENTS:
        scores = [(overlap(example, question), question)
                  for question in test_questions]
        highest, closest = max(scores)
        worst.append((highest, example, closest))
        if highest >= OVERLAP_LIMIT:
            problems.append((highest, example, closest))

    worst.sort(reverse=True)
    print("CLOSEST MATCH FOR EACH EXAMPLE")
    print("  Key: 'share' is the fraction of meaningful words the example and")
    print("  the nearest test question have in common. Higher is worse.")
    print()
    for share, example, closest in worst:
        print(f"  {share:.0%}  {example[:62]}")
        print(f"       nearest: {closest[:62]}")

    print()
    if problems:
        print(f"LEAKAGE: {len(problems)} example(s) too close to a test "
              f"question. Rewrite them before measuring anything.")
        raise SystemExit(1)
    print("PASS - no example resembles a test question")


if __name__ == "__main__":
    main()
