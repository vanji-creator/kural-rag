"""
Turn "suspicious" into "proven", on the real corpus with nothing planted.

A low similarity between a kural's English explanation and its Tamil meaning
has two possible causes:

  1. the translation is simply loose or free      -> not an error
  2. the Tamil meaning belongs to a DIFFERENT kural -> a real error

Low similarity alone cannot tell these apart. But this can:

  take the Tamil meaning, and compare it against ALL 1330 English explanations.

  - a loose translation still matches its OWN kural best
  - a misassigned meaning matches SOME OTHER kural best

That second case is evidence, not suspicion. It also tells us exactly which
kural the text was stolen from — which is how we confirmed 524 came from 468.
"""

import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CORPUS_PATH = PROJECT_ROOT / "data" / "kurals.json"

# the model that actually worked in audit_with_embeddings.py
MODEL_NAME = "sentence-transformers/LaBSE"

kurals = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
kural_numbers = [record["number"] for record in kurals]
english_texts = [record["english_explanation"] for record in kurals]
tamil_texts = [record["tamil_meaning_mu_varadarajan"] for record in kurals]

model = SentenceTransformer(MODEL_NAME)
english_embeddings = model.encode(english_texts, batch_size=32, show_progress_bar=False)
tamil_embeddings = model.encode(tamil_texts, batch_size=32, show_progress_bar=False)

# normalise every arrow to length 1. Once every vector has length 1, the
# division in cosine similarity becomes a division by 1 — so a plain dot
# product IS the cosine. This is the standard trick for comparing many at once.
english_unit = english_embeddings / np.linalg.norm(english_embeddings, axis=1, keepdims=True)
tamil_unit = tamil_embeddings / np.linalg.norm(tamil_embeddings, axis=1, keepdims=True)

# every Tamil meaning against every English explanation, in one multiplication
all_pairs_similarity = tamil_unit @ english_unit.T        # shape (1330, 1330)

own_score = np.diag(all_pairs_similarity)                 # each meaning vs its OWN kural
best_match_position = np.argmax(all_pairs_similarity, axis=1)
best_match_score = all_pairs_similarity[np.arange(len(kurals)), best_match_position]

print(f"corpus: {len(kurals)} kurals, model: {MODEL_NAME}\n")

mismatches = []
for position, number in enumerate(kural_numbers):
    matched_number = kural_numbers[best_match_position[position]]
    if matched_number != number:
        mismatches.append((
            number,
            matched_number,
            own_score[position],
            best_match_score[position],
        ))

print(f"Tamil meanings whose closest English explanation is NOT their own kural: "
      f"{len(mismatches)} of {len(kurals)}\n")

# biggest gap first — the most confident evidence of a swap
mismatches.sort(key=lambda row: row[3] - row[2], reverse=True)

print(f"{'kural':>6} {'matches':>8} {'own':>7} {'other':>7} {'gap':>7}")
print("-" * 40)
for number, matched_number, own, other in mismatches[:25]:
    print(f"{number:6} {matched_number:8} {own:7.3f} {other:7.3f} {other - own:7.3f}")

# save the strong candidates so we can inspect the text by hand
strong_candidates = [row for row in mismatches if row[3] - row[2] > 0.10]
output_path = PROJECT_ROOT / "experiments" / "misassignment_candidates.json"
output_path.write_text(json.dumps([
    {
        "kural": number,
        "meaning_matches_kural": matched_number,
        "similarity_to_own": round(float(own), 4),
        "similarity_to_other": round(float(other), 4),
    }
    for number, matched_number, own, other in strong_candidates
], indent=2), encoding="utf-8")

print(f"\n{len(strong_candidates)} candidates with a gap above 0.10 "
      f"-> {output_path.relative_to(PROJECT_ROOT)}")
