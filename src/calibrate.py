"""Does the top score know when Thirukkural has nothing to say?

The interface has a refusal policy: answer normally above one threshold, show
doubt below it, refuse entirely below a floor. Those thresholds only mean
anything if the score SEPARATES questions the book answers from questions it
does not.

The placeholder word-overlap engine was tested this way and FAILED - so
`lib/retrieval.ts` carries `calibrated: false`, and the interface is forbidden
from claiming confidence on its behalf. Selected results from that test:

    0.283   is it wrong to eat meat                  (on topic)
    0.363   how do I stop being controlled by anger  (on topic)
    0.847   who won the football world cup           (OFF topic)
    1.000   what does it say about friendship        (on topic)

"Who won the football world cup" outscored most real questions, because "won",
"world" and "cup" all appear in verses about conquest and abundance.

This script runs the SAME test on the real pipeline. It must be run before any
threshold is written into the interface, and the answer is allowed to be "no".

There is a reason to hope it does better: the final score comes from a
cross-encoder trained to answer "does this passage answer this query", which is
a different question from "do these two texts share rare words". But that is a
hypothesis, and hypotheses get measured here.

Run it:

    venv/bin/python src/calibrate.py
"""

import json
from pathlib import Path

import numpy as np

from pipeline import KuralRetriever

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GOLDEN_SET_PATH = PROJECT_ROOT / "data" / "golden_set.json"

# Every twentieth golden question, so the sample spans all three books rather
# than clustering in the virtue chapters at the front.
ON_TOPIC_STRIDE = 5

# Questions Thirukkural genuinely cannot answer. A working refusal policy has
# to put these BELOW every real question. They are deliberately varied: some
# share vocabulary with the corpus ("king", "war", "gold"), some share none.
OFF_TOPIC_QUESTIONS = [
    "who won the football world cup",
    "how do I install docker on ubuntu",
    "what is the capital of Brazil",
    "how do I fix a null pointer exception in java",
    "what time does the train to Chennai leave",
    "how many calories are in a banana",
    "what is the price of bitcoin today",
    "how do I reset my wifi router",
    "which king won the most gold in the war",
    "what are the side effects of paracetamol",
    "how do I make chicken biryani",
    "what is the tallest building in the world",
    "how do I get a passport renewed",
    "what is the offside rule in football",
    "how do I center a div in css",
]


def main():
    golden_questions = json.load(open(GOLDEN_SET_PATH, encoding="utf-8"))
    on_topic_questions = [entry["question"]
                          for entry in golden_questions][::ON_TOPIC_STRIDE]

    retriever = KuralRetriever(use_reranker=True)

    print()
    print(f"scoring {len(on_topic_questions)} on-topic "
          f"and {len(OFF_TOPIC_QUESTIONS)} off-topic questions")
    print()

    def top_scores_for(questions):
        scores = []
        for question in questions:
            outcome = retriever.search(question)
            scores.append(outcome["topScore"])
        return np.array(scores)

    on_topic_scores = top_scores_for(on_topic_questions)
    off_topic_scores = top_scores_for(OFF_TOPIC_QUESTIONS)

    print("ON TOPIC - questions the book really does answer")
    for question, score in sorted(zip(on_topic_questions, on_topic_scores),
                                  key=lambda pair: pair[1]):
        print(f"   {score:.3f}  {question[:62]}")
    print()

    print("OFF TOPIC - questions the book cannot answer")
    for question, score in sorted(zip(OFF_TOPIC_QUESTIONS, off_topic_scores),
                                  key=lambda pair: pair[1], reverse=True):
        print(f"   {score:.3f}  {question[:62]}")
    print()

    lowest_on_topic = float(np.min(on_topic_scores))
    highest_off_topic = float(np.max(off_topic_scores))

    print("=" * 66)
    print(f"  worst on-topic question scored   {lowest_on_topic:.3f}")
    print(f"  best  off-topic question scored  {highest_off_topic:.3f}")
    print(f"  median on-topic   {float(np.median(on_topic_scores)):.3f}")
    print(f"  median off-topic  {float(np.median(off_topic_scores)):.3f}")
    print("=" * 66)
    print()

    if lowest_on_topic > highest_off_topic:
        # A clean gap: every real question beat every fake one. A threshold
        # placed inside the gap refuses the fakes and passes the real ones.
        floor = (lowest_on_topic + highest_off_topic) / 2
        print("CALIBRATED. The two groups do not overlap at all.")
        print(f"  gap: {highest_off_topic:.3f} .. {lowest_on_topic:.3f}")
        print(f"  suggested floor          {floor:.3f}")
        print(f"  suggested highConfidence "
              f"{float(np.median(on_topic_scores)):.3f}")
        print()
        print("  Set calibrated: true in lib/retrieval.ts and use these.")
        print("  Note this is fitted on these 35 questions - a gap this")
        print("  clean should be re-checked when the question set grows.")
    else:
        overlapping = int(np.sum(off_topic_scores >= lowest_on_topic))
        print("NOT CALIBRATED. The groups overlap.")
        print(f"  {overlapping} off-topic question(s) scored at or above the")
        print(f"  worst real question, so no threshold separates them.")
        print()
        print("  Keep calibrated: false in lib/retrieval.ts. The engine still")
        print("  ranks well WITHIN a question - its best result really is its")
        print("  best - but its absolute score says nothing about whether the")
        print("  book addresses the question at all, so it must not refuse")
        print("  and must not claim confidence.")


if __name__ == "__main__":
    main()
