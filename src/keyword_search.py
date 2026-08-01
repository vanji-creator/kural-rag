"""BM25 keyword search, written out by hand.

Embeddings match MEANING. This matches WORDS. They fail in different ways,
which is the whole reason for having both:

  - embeddings find "controlling anger" in a kural that says "restrain wrath"
  - embeddings also confidently return a kural about eating meat
  - keyword search will never find "wrath" from the word "anger"
  - but keyword search will NEVER return the meat kural for an anger question

Three ideas, all of which fall out of common sense:

  1. RARE WORDS COUNT MORE. A word in 500 of 1330 kurals cannot tell them
     apart. A word in 12 nearly points at the answer by itself.
  2. MORE MATCHES ARE BETTER. Matching both "control" and "anger" beats
     matching only "anger".
  3. SHORT TEXTS WIN TIES. One "anger" inside a 10-word kural means more
     than one "anger" inside a 60-word explanation.

Put together, those three are BM25 - the standard keyword formula that every
search engine is still measured against.
"""

import math
import re
from collections import Counter

# BM25's two tuning knobs. These are the values the original paper used and
# that nearly everyone still uses. We are not tuning them; if we ever do, it
# gets measured on the scorecard like everything else.
#
# TERM_FREQUENCY_SATURATION controls how fast repeating a word stops helping.
# The 5th "anger" in a text should add far less than the 2nd did.
TERM_FREQUENCY_SATURATION = 1.5
#
# LENGTH_PENALTY_STRENGTH controls how much we punish long texts.
# 0.0 = ignore length entirely, 1.0 = punish it fully.
LENGTH_PENALTY_STRENGTH = 0.75


def split_into_words(text):
    """Lowercase, then keep runs of letters and digits.

    Punctuation and apostrophes are dropped, so "friend's" becomes "friend"
    and "s" - close enough, and it keeps the code honest and readable.
    """
    return re.findall(r"[a-z0-9]+", text.lower())


class BM25Index:
    """A searchable index over a list of documents.

    Here one "document" is one kural's searchable text.
    """

    def __init__(self, documents):
        self.document_word_lists = [split_into_words(text)
                                    for text in documents]
        self.document_lengths = [len(words)
                                 for words in self.document_word_lists]
        self.average_document_length = (sum(self.document_lengths)
                                        / len(self.document_lengths))

        # How many documents contain each word at least once.
        documents_containing_word = Counter()
        for word_list in self.document_word_lists:
            for word in set(word_list):
                documents_containing_word[word] += 1

        # Turn that count into a WEIGHT, so rare words score higher.
        #
        # Idea 1 from the docstring. A word in every document gets a weight
        # near zero. A word in a handful of documents gets a large weight.
        # The log is what makes the drop-off gentle instead of a cliff.
        document_count = len(documents)
        self.word_weights = {}
        for word, containing_count in documents_containing_word.items():
            self.word_weights[word] = math.log(
                1 + (document_count - containing_count + 0.5)
                / (containing_count + 0.5))

        # How many times each word appears inside each document.
        self.word_counts_per_document = [Counter(words)
                                         for words in self.document_word_lists]

    def scores_for_query(self, query_text):
        """Score every document against this query. Higher is a better match."""
        query_words = split_into_words(query_text)
        all_scores = []

        for document_index in range(len(self.document_word_lists)):
            word_counts = self.word_counts_per_document[document_index]
            document_length = self.document_lengths[document_index]

            # Idea 3: a document longer than average gets penalised, a shorter
            # one gets a small bonus.
            length_penalty = (
                TERM_FREQUENCY_SATURATION
                * (1 - LENGTH_PENALTY_STRENGTH
                   + LENGTH_PENALTY_STRENGTH
                   * document_length / self.average_document_length))

            document_score = 0.0
            for word in query_words:
                times_in_document = word_counts.get(word, 0)
                if times_in_document == 0:
                    continue  # this query word is simply not here

                # Idea 2: every matching word adds to the total.
                # The fraction below is idea 1's saturation - going from 1 to 2
                # occurrences helps a lot, 8 to 9 barely at all.
                document_score += (
                    self.word_weights.get(word, 0.0)
                    * times_in_document * (TERM_FREQUENCY_SATURATION + 1)
                    / (times_in_document + length_penalty))

            all_scores.append(document_score)

        return all_scores
