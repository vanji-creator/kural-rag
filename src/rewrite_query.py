"""Turn a chatty question into a bare topic, before searching.

Measured twice on the scorecard, two different ways, same conclusion:

  - the embedding model matches question-SHAPED text. Kural 251 is about
    eating meat and it answered 26 of our 100 questions, because it opens
    "What graciousness can one command...".
  - BM25 gives the word "how" a weight of 3.78 - nearly the same as "anger"
    at 4.13 - because the corpus is old verse translation that rarely says
    "how do I my".

Both methods are distracted by the same words. So remove them.

    "how do I control my anger?"   ->   "control anger"

This is the cheap, LLM-free version. It exists to TEST the diagnosis. If
deleting these words moves the scorecard, the diagnosis was right and paying
an LLM to do the same job properly is worth it. If it does not move, the
diagnosis was wrong and no amount of LLM would have saved it.
"""

import re

# Ordinary English glue words. These carry no topic on their own.
FUNCTION_WORDS = {
    "a", "an", "the", "of", "to", "is", "are", "was", "were", "be", "been",
    "and", "or", "but", "if", "in", "on", "at", "by", "for", "with", "from",
    "as", "that", "this", "these", "those", "it", "its", "there", "here",
    "so", "than", "then", "too", "very", "just", "also", "about", "into",
    "over", "under", "up", "down", "out", "off", "any", "some", "all",
}

# Words that build a QUESTION rather than name its subject. These are the
# real culprits - they are rare in the corpus, so BM25 rates them highly,
# and they make a question look like the many kurals phrased as questions.
QUESTION_WORDS = {
    "how", "what", "why", "when", "where", "which", "who", "whom", "whose",
    "do", "does", "did", "can", "could", "should", "would", "will", "shall",
    "i", "me", "my", "mine", "we", "us", "our", "you", "your", "he", "him",
    "his", "she", "her", "they", "them", "their", "someone", "somebody",
    "person", "people", "ever", "really", "like", "know", "say", "says",
    "tell", "think", "good", "bad", "better", "best",
}

# Words specific to THIS corpus that appear in questions without narrowing
# anything down - every question here is about Thirukkural.
CORPUS_WORDS = {"thirukkural", "kural", "kurals", "thiruvalluvar", "valluvar",
                "tamil", "text", "ancient", "poet", "verse", "couplet"}

WORDS_TO_DROP = FUNCTION_WORDS | QUESTION_WORDS | CORPUS_WORDS


def rewrite(question_text):
    """Strip the question shape, keep the topic.

    Falls back to the original question if stripping would leave nothing -
    better a noisy search than an empty one.
    """
    words = re.findall(r"[a-z0-9']+", question_text.lower())
    kept_words = [word for word in words if word not in WORDS_TO_DROP]
    if not kept_words:
        return question_text
    return " ".join(kept_words)


if __name__ == "__main__":
    examples = [
        "how do I control my anger?",
        "what does Thirukkural say about true friendship?",
        "I would really like to know what the ancient Tamil text Thirukkural "
        "written by the poet Thiruvalluvar has to say on the subject of a "
        "person controlling their own anger and temper in daily life",
        "why should I not talk behind someone's back?",
    ]
    for question in examples:
        print(f"  {question[:64]}")
        print(f"    -> {rewrite(question)}")
        print()
