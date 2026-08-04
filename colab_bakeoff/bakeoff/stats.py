"""McNemar's exact test - is a gap real, or could it be luck?

The full derivation lives in the main project's log. The short version:
only the questions where two methods DISAGREE carry information. If the
methods were equally good, each disagreement is a fair coin flip, so the
p value is just the chance of a coin-flip split this lopsided or worse.
p below 0.05 means "luck would do this less than one time in twenty".
"""

from math import comb


def mcnemar_exact(hits_a, hits_b):
    """Returns (a_only_wins, b_only_wins, p)."""
    a_only = sum(1 for a, b in zip(hits_a, hits_b) if a and not b)
    b_only = sum(1 for a, b in zip(hits_a, hits_b) if b and not a)
    total = a_only + b_only
    if total == 0:
        return a_only, b_only, 1.0
    smaller = min(a_only, b_only)
    p = 2 * sum(comb(total, i) for i in range(smaller + 1)) / 2 ** total
    return a_only, b_only, min(p, 1.0)
