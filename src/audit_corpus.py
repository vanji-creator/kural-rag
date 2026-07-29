"""
A thorough audit of data/kurals.json.

This does NOT fix anything. It only looks, counts, and reports.

Why a separate script: the checks inside build_corpus.py are a gate — they stop
a broken file being written. This is different. This asks "what is actually in
the file we built", including things that are not errors but are worth knowing
before we start embedding text in Phase 2.

Every bug we have hit in this project so far was silent. None of them crashed.
The only defence is to count things on purpose.
"""

import json                                  # read the corpus and the raw sources
import re                                    # pattern checks on text
from collections import Counter, defaultdict # tallying
from pathlib import Path                     # file paths


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CORPUS_PATH = PROJECT_ROOT / "data" / "kurals.json"
RAW_FOLDER = PROJECT_ROOT / "data" / "raw"

TOTAL_KURALS = 1330
KURALS_PER_CHAPTER = 10
TOTAL_CHAPTERS = 133

# Tamil script occupies this Unicode block. Anything outside it in a Tamil
# field (other than punctuation and digits) is worth a second look.
TAMIL_CHARACTER = re.compile(r"[஀-௿]")
LATIN_LETTER = re.compile(r"[A-Za-z]")

# fields we expect to be Tamil script, and fields we expect to be English
TAMIL_FIELDS = [
    "section_tamil", "subsection_tamil", "chapter_tamil",
    "kural_line1", "kural_line2",
    "tamil_meaning_mu_varadarajan", "tamil_meaning_solomon_pappaiah",
    "tamil_meaning_karunanidhi",
    "parimelazhagar_commentary", "manakkudavar_commentary",
]
ENGLISH_FIELDS = [
    "section_english", "subsection_english", "chapter_english",
    "english_translation", "english_couplet", "english_explanation",
    "transliteration",
]


def print_heading(text):
    """Print a section heading so the report is readable."""
    print()
    print("=" * 72)
    print(text)
    print("=" * 72)


def load_json(path):
    with open(path, encoding="utf-8") as json_file:
        return json.load(json_file)


kurals = load_json(CORPUS_PATH)


# ===========================================================================
# 1. SHAPE — is the file the container we think it is
# ===========================================================================
print_heading("1. SHAPE")

print("top-level type      :", type(kurals).__name__)
print("record count        :", len(kurals), f"(expected {TOTAL_KURALS})")
print("record type         :", type(kurals[0]).__name__)

# do all records carry exactly the same keys, in the same order
key_signatures = Counter(tuple(record.keys()) for record in kurals)
print("distinct key layouts:", len(key_signatures), "(expected 1)")
if len(key_signatures) > 1:
    for signature, count in key_signatures.items():
        print("   layout used by", count, "records:", signature)

print("fields per record   :", len(kurals[0]))


# ===========================================================================
# 2. TYPES — is every field the type we assume it is
# ===========================================================================
print_heading("2. TYPES")

types_seen = defaultdict(Counter)
for record in kurals:
    for field_name, value in record.items():
        types_seen[field_name][type(value).__name__] += 1

for field_name, counter in types_seen.items():
    mixed = "  <-- MIXED TYPES" if len(counter) > 1 else ""
    print(f"  {field_name:32} {dict(counter)}{mixed}")


# ===========================================================================
# 3. IDENTITY — numbers present, unique, and in order
# ===========================================================================
print_heading("3. IDENTITY (kural numbers)")

numbers = [record["number"] for record in kurals]
print("min:", min(numbers), " max:", max(numbers))
print("duplicates          :", [n for n, c in Counter(numbers).items() if c > 1] or "none")
print("missing from 1..1330:", [n for n in range(1, TOTAL_KURALS + 1)
                                if n not in set(numbers)] or "none")
print("stored in ascending order:", numbers == sorted(numbers))


# ===========================================================================
# 4. BOOK STRUCTURE — this is a real cross-check, not a formality
#
# Thirukkural has a known shape: 133 chapters of exactly 10 kurals each.
# So chapter number can be DERIVED from kural number. If the derived chapter
# boundaries disagree with the stored chapter names, the join is wrong.
# ===========================================================================
print_heading("4. BOOK STRUCTURE")

chapters = defaultdict(list)
for record in kurals:
    derived_chapter_index = (record["number"] - 1) // KURALS_PER_CHAPTER + 1
    chapters[derived_chapter_index].append(record)

print("chapters found      :", len(chapters), f"(expected {TOTAL_CHAPTERS})")

wrong_size = {index: len(group) for index, group in chapters.items()
              if len(group) != KURALS_PER_CHAPTER}
print("chapters not of size 10:", wrong_size or "none")

# inside one chapter, every kural must carry the SAME chapter name.
# a mismatch here means a record is bound to the wrong chapter.
inconsistent_chapters = []
for index, group in chapters.items():
    distinct_names = {record["chapter_tamil"] for record in group}
    if len(distinct_names) != 1:
        inconsistent_chapters.append((index, distinct_names))
print("chapters with mixed names:", inconsistent_chapters or "none")

# the same chapter name should not appear in two different chapters
name_to_indices = defaultdict(set)
for index, group in chapters.items():
    name_to_indices[group[0]["chapter_tamil"]].add(index)
repeated_names = {name: sorted(indices) for name, indices in name_to_indices.items()
                  if len(indices) > 1}
print("chapter names reused across chapters:", repeated_names or "none")

# sections: the three paal, and where each one starts and ends
print()
print("sections (பால்):")
section_ranges = defaultdict(list)
for record in kurals:
    section_ranges[record["section_tamil"]].append(record["number"])
for section_name, member_numbers in section_ranges.items():
    first, last = min(member_numbers), max(member_numbers)
    contiguous = (last - first + 1) == len(member_numbers)
    print(f"   {section_name:16} kurals {first:4}-{last:4}  "
          f"count {len(member_numbers):4}  contiguous: {contiguous}")

print()
print("subsections (இயல்):", len(section_ranges := {r["subsection_tamil"] for r in kurals}))


# ===========================================================================
# 5. EMPTINESS — which fields have holes
# ===========================================================================
print_heading("5. EMPTY FIELDS")

for field_name in kurals[0]:
    # only text fields can be "empty" in a meaningful sense. A False boolean or
    # an empty provenance list is not a hole in the data.
    if not isinstance(kurals[0][field_name], str):
        continue
    empty_numbers = [r["number"] for r in kurals if not str(r[field_name]).strip()]
    if empty_numbers:
        print(f"  {field_name:32} empty for {len(empty_numbers):4}: {empty_numbers[:10]}")
    else:
        print(f"  {field_name:32} complete")


# ===========================================================================
# 6. SCRIPT MISMATCH — Tamil text sitting in English fields and vice versa
# ===========================================================================
print_heading("6. SCRIPT MISMATCH")

for field_name in TAMIL_FIELDS:
    offenders = [r["number"] for r in kurals
                 if r[field_name] and not TAMIL_CHARACTER.search(r[field_name])]
    print(f"  {field_name:32} no Tamil script at all: {len(offenders)} {offenders[:6]}")

print()
for field_name in ENGLISH_FIELDS:
    offenders = [r["number"] for r in kurals
                 if r[field_name] and TAMIL_CHARACTER.search(r[field_name])]
    print(f"  {field_name:32} contains Tamil script: {len(offenders)} {offenders[:6]}")

# The check above only asks "is there ANY Tamil". That was too weak — it passed
# 664 records whose Tamil commentary had an English translation glued on the
# end. Mixing, not absence, was the defect. So test for that directly.
print()
ENGLISH_WORD = re.compile(r"[A-Za-z]{4,}")
for field_name in TAMIL_FIELDS:
    mixed = [r["number"] for r in kurals if ENGLISH_WORD.search(r[field_name])]
    print(f"  {field_name:32} MIXED - English words present: {len(mixed)} {mixed[:6]}")


# ===========================================================================
# 7. TEXT HYGIENE — the quiet stuff that hurts embeddings later
# ===========================================================================
print_heading("7. TEXT HYGIENE")

text_fields = [f for f in kurals[0]
               if isinstance(kurals[0][f], str) and f != "number"]

for field_name in text_fields:
    values = [r[field_name] for r in kurals]
    leading_trailing = sum(1 for v in values if v != v.strip())
    double_spaces = sum(1 for v in values if "  " in v)
    newlines = sum(1 for v in values if "\n" in v or "\t" in v)
    html_entities = sum(1 for v in values if re.search(r"&[a-z]+;|&#\d+;", v))
    # only a real leftover list-repr counts. An opening apostrophe is normal
    # English ("'Tis rain works all...") and was a false alarm in the first
    # version of this audit.
    stray_brackets = sum(1 for v in values if v.startswith("[") or v.startswith("['"))
    if any([leading_trailing, double_spaces, newlines, html_entities, stray_brackets]):
        print(f"  {field_name:32} untrimmed={leading_trailing:4} "
              f"double_space={double_spaces:4} newline/tab={newlines:4} "
              f"html={html_entities:3} stray_bracket={stray_brackets:3}")

print()
print("  (blank above means the field is clean on all five checks)")


# ===========================================================================
# 8. LABEL LEAKAGE — did a commentator's name survive into the text
# ===========================================================================
print_heading("8. LABEL LEAKAGE")

LABELS = ["பரிமேலழகர் உரை", "மணக்குடவர் உரை", "மு.வரதராசனார் உரை",
          "சாலமன் பாப்பையா உரை", "கலைஞர் மு.கருணாநிதி உரை",
          "Explanation", "Translation"]
for field_name in TAMIL_FIELDS:
    hits = [r["number"] for r in kurals
            if any(label in r[field_name] for label in LABELS)]
    if hits:
        print(f"  {field_name:32} label text found in {len(hits)} records: {hits[:8]}")
print("  (nothing listed = no labels leaked)")


# ===========================================================================
# 9. DUPLICATE CONTENT — two kurals sharing identical text is a copy error
# ===========================================================================
print_heading("9. DUPLICATE CONTENT")

for field_name in ["kural_line1", "kural_line2", "english_explanation",
                   "english_translation", "parimelazhagar_commentary",
                   "tamil_meaning_mu_varadarajan"]:
    counts = Counter(r[field_name] for r in kurals if r[field_name])
    duplicates = {text: count for text, count in counts.items() if count > 1}
    if duplicates:
        print(f"  {field_name}: {len(duplicates)} repeated values")
        for text, count in list(duplicates.items())[:3]:
            owners = [r["number"] for r in kurals if r[field_name] == text]
            print(f"     x{count} kurals {owners}: {text[:60]}")
    else:
        print(f"  {field_name}: no duplicates")


# ===========================================================================
# 10. LENGTH PROFILE — matters a lot for Phase 4 chunking
# ===========================================================================
print_heading("10. LENGTH PROFILE (characters)")

print(f"  {'field':32} {'min':>6} {'median':>7} {'mean':>7} {'max':>7}")
for field_name in text_fields:
    lengths = sorted(len(r[field_name]) for r in kurals)
    if not any(lengths):
        continue
    median = lengths[len(lengths) // 2]
    mean = sum(lengths) / len(lengths)
    print(f"  {field_name:32} {lengths[0]:6} {median:7} {mean:7.0f} {lengths[-1]:7}")

# the shortest and longest commentaries are worth eyeballing by hand
commentary_lengths = [(len(r["parimelazhagar_commentary"]), r["number"]) for r in kurals]
commentary_lengths.sort()
print()
print("  shortest Parimelazhagar commentaries:", commentary_lengths[:5])
print("  longest  Parimelazhagar commentaries:", commentary_lengths[-5:])


# ===========================================================================
# 11. CROSS-SOURCE AGREEMENT — do the two raw files tell the same story
#
# Both raw sources carry the kural lines and the English explanation.
# If they disagree, one of them is wrong, and we need to know which fields
# are affected before we trust either.
# ===========================================================================
print_heading("11. CROSS-SOURCE AGREEMENT (raw file A vs raw file B)")

structured_raw = load_json(RAW_FOLDER / "thirukkural.json")["kural"]
info_raw = load_json(RAW_FOLDER / "all_thirukkural_information.json")
info_by_number = {int(k): v for k, v in info_raw.items()}


def normalise(text):
    """Collapse whitespace so trivial spacing differences are not counted."""
    return re.sub(r"\s+", " ", str(text)).strip()


comparisons = [
    ("kural line 1", lambda s: s["Line1"], lambda i: i["1_line1"]),
    ("kural line 2", lambda s: s["Line2"], lambda i: i["1_line2"]),
    ("english explanation", lambda s: s["explanation"],
     lambda i: " ".join(i["6_explanation"][1:])),
    ("chapter name", lambda s: s["adikaram_name"], lambda i: i["2_adikaram"]),
]

for label, get_from_structured, get_from_info in comparisons:
    disagreements = []
    for structured_record in structured_raw:
        number = int(structured_record["Number"])
        if number not in info_by_number:
            continue                                  # 395 and 648, already known
        try:
            left = normalise(get_from_structured(structured_record))
            right = normalise(get_from_info(info_by_number[number]))
        except (KeyError, TypeError):
            continue
        if left != right:
            disagreements.append(number)
    print(f"  {label:22} disagreements: {len(disagreements):4} {disagreements[:8]}")


print()
print("=" * 72)
print("AUDIT COMPLETE — nothing was modified.")
print("=" * 72)
