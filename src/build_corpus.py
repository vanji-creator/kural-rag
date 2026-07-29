"""
Build one clean corpus file from two messy raw sources.

Why two sources:
  thirukkural.json  -> has all 1330 kurals, well structured, English fields,
                       but NO Parimelazhagar commentary.
  all_thirukkural_information.json
                    -> HAS Parimelazhagar commentary,
                       but is missing kurals 395 and 648.

Neither file alone is enough, so we join them.

Rule we follow everywhere: JOIN ON THE KURAL NUMBER, NEVER ON POSITION.
Joining by position would silently mis-pair 934 records, because the second
file has holes at 395 and 648 and everything after a hole slides up.

Output: data/kurals.json — one record per kural, every field stored SEPARATELY
so that Phase 4 can freely combine them and measure which combination
retrieves best.
"""

import json                                  # read and write JSON files
import re                                    # pattern matching on text
from pathlib import Path                     # tidy, OS-independent file paths


# ---------------------------------------------------------------------------
# where the files live
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent   # the kural-rag folder
RAW_FOLDER = PROJECT_ROOT / "data" / "raw"              # untouched downloads
OUTPUT_PATH = PROJECT_ROOT / "data" / "kurals.json"     # the clean result

STRUCTURED_SOURCE_PATH = RAW_FOLDER / "thirukkural.json"
COMMENTARY_SOURCE_PATH = RAW_FOLDER / "all_thirukkural_information.json"

TOTAL_KURALS = 1330                          # the number we check against


# ---------------------------------------------------------------------------
# the two kurals missing from the commentary source, filled in by hand
#
# Both texts were cross-checked against two independent websites before being
# pasted here. They are marked in the output so we can always tell them apart
# from the bulk-imported ones.
# ---------------------------------------------------------------------------

HAND_SOURCED_FIELDS = {

    # ---- kural 1000: line 1 was truncated in the structured source ----------
    # It read "ண்பிலான்" — the leading ப had been lost. The commentary source
    # had it right, and it is the only line disagreement in all 1330 kurals.
    # Verified: both raw sources compared.
    1000: {"kural_line1": "பண்பிலான் பெற்ற பெருஞ்செல்வம் நன்பால்"},

    # ---- kural 524: carried kural 468's meaning ----------------------------
    # Wrong in BOTH raw sources AND in two of the three websites checked,
    # because they all copy the same upstream dataset. Only thirukkural.io
    # had the correct text.
    # Lesson: agreement between sources proves nothing when they copy one another.
    # Verified: 1 independent source (the other two were copies of the error).
    524: {"tamil_meaning_mu_varadarajan":
          "சுற்றத்தாரால் சுற்றப்படும்படியாக அவர்களைத் தழுவி அன்பாக வாழ்தல் "
          "ஒருவன் செல்வத்தைப் பெற்றதனால் பெற்ற பயனாகும்."},

    # ---- kural 1277: Manakkudavar commentary absent from the source --------
    # Verified: 1 source (thirukkural.io). A second site did not carry
    # Manakkudavar at all, so this one is single-sourced. Flagged as such.
    1277: {"manakkudavar_commentary":
           "குளிர்ந்த துறையையுடையவன் நம்மை நீங்கினமையை, நாமறி வதற்கும் "
           "முன்னே வளைகள் அறிந்தன"},

    # ---- kurals 395 and 648: absent entirely from the commentary source ----
    # These two numbers are simply missing from all_thirukkural_information.json,
    # so every field it supplies had to be sourced by hand.
    395: {

        # Verified: 2 independent sources (thirutamil.com, kural.page)
        "parimelazhagar_commentary": (
        "உடையார்முன் இல்லார் போல் ஏக்கற்றும் கற்றார் - "
        "'பிற்றை நிலைமுனியாது கற்றல் நன்று' (புறநா.183) ஆதலான், "
        "செல்வர்முன் நல்கூர்ந்தார் நிற்குமாறு போலத் தாமும் ஆசிரியர்முன் "
        "ஏக்கற்று நின்றும் கற்றார் தலையாயினார். "
        "கல்லாதவர் கடையரே - அந்நிலைக்கு நாணிக் கல்லாதவர் எஞ்ஞான்றும் "
        "இழிந்தாரேயாவர். "
        "(உடையார், இல்லார் என்பன உலகவழக்கு. ஏக்கறுதல் ஆசையால் தாழ்தல். "
        "கடையர் என்றதனான், அதன் மறுதலைப் பெயர் வருவிக்கப்பட்டது. "
        "பொய்யாய மானம் நோக்க மெய்யாய கல்வி இழந்தார் பின் ஒரு ஞான்றும் "
        "அறிவுடைய ராகாமையின், 'கடையரே' என்றார். "
        "இதனால் கற்றாரது உயர்வும் கல்லாதாரது இழிவும் கூறப்பட்டன.)"
        ),

        # Verified: 2 independent sources (thirukkural.io, thirutamil.com)
        "manakkudavar_commentary": (
            "பொருளுடையார் முன்பு பொருளில்லாதார் நிற்குமாறு போல, "
            "அதனைக் காதலித்து நிற்றலுமன்றிக் கற்றாரிடத்தாவர் கல்லாதார்."
        ),

        # Verified: 1 source (ytamizh.com). thirukkural.io does not carry
        # Karunanidhi at all, so this one is single-sourced.
        "tamil_meaning_karunanidhi": (
            "அறிவுடையார் முன் அறிவில்லாதவர் போல் தாழ்ந்து நின்று, மேலும் "
            "கற்றுக்கொள்பவர்களின் ஆர்வத்தைக் கற்றுக் கொள்ளாதவர்கள் "
            "கடைநிலை மாந்தராக கருதப்படுவார்கள்."
        ),
    },

    648: {

        # Verified: 2 independent sources (kural.page, thirukkural.io)
        "parimelazhagar_commentary": (
            "தொழில் நிரந்து இனிது சொல்லுதல் வல்லார்ப்பெறின் - "
            "சொல்லப்படும் காரியங்களை நிரல்படக் கோத்து இனிதாகச் சொல்லுதல் "
            "வல்லாரைப் பெறின்; "
            "ஞாலம் விரைந்து கேட்கும் - உலகம் அவற்றை விரைந்து ஏற்றுக்கொள்ளும்."
        ),

        # Verified: 1 source (thirukkural.io)
        "manakkudavar_commentary": (
            "இனிதாகச் சொல்ல வல்லாரைப் பெற்றாராயின், உலகத்தார் மேவி விரைந்து "
            "சென்று செய்யுந் தொழில் யாது என்று கேட்பர்"
        ),

        # Verified: 1 source (ytamizh.com)
        "tamil_meaning_karunanidhi": (
            "வகைப்படுத்தியும், சுவையாகவும் கருத்துக்களைச் சொல்லும் "
            "வல்லமையுடையோர் சுட்டிக்காட்டும் பணியை, உலகத்தார் உடனடியாக "
            "நிறைவேற்ற முனைவார்கள்."
        ),
    },
}


# Every commentator label that has been found leaking into the middle of a
# commentary. Text from the first one onward belongs to a different field.
COMMENTATOR_LABELS = [
    "பரிமேலழகர் உரை", "மணக்குடவர் உரை", "மு.வரதராசனார் உரை", "மு.வ உரை",
    "சாலமன் பாப்பையா உரை", "கலைஞர் மு.கருணாநிதி உரை",
    "திருக்குறளார் வீ. முனிசாமி உரை", "சிவயோகி சிவக்குமார் உரை",
]
LABEL_MARKER = re.compile("|".join(re.escape(label) for label in COMMENTATOR_LABELS))

# invisible characters that some sources sprinkle into Tamil text
ZERO_WIDTH_CHARACTERS = re.compile(r"[​‌‍﻿]")


# In the commentary source, some Tamil commentary entries have the English
# "Translation" and "Explanation" blocks appended onto the end of them. Those
# belong to other fields and must not be glued into a Tamil commentary.
# Everything from the first such marker onward is dropped.
ENGLISH_SECTION_MARKER = re.compile(r"\s*(Translation|Explanation)\b.*$", re.DOTALL)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def strip_english_sections(tamil_text):
    """Cut off English 'Translation'/'Explanation' blocks leaked into Tamil text.

    Example of the damage this repairs (kural 216, Manakkudavar):
        "...இது வேண்டாதார்க்கும் பயன்படு மென்றது. Translation A tree that
         fruits in th' hamlet's central mart... Explanation The wealth of..."
    Only the Tamil part before 'Translation' is kept.
    """
    return ENGLISH_SECTION_MARKER.sub("", tamil_text).strip()


def cut_at_next_label(commentary_text):
    """Keep only the text before the next commentator's label.

    Kural 319's Solomon Pappaiah entry ran two commentaries together:
        "...மாலையில் தானாக வரும். சாலமன் பாப்பையா உரை அடுத்தவர் செய்த..."
    Everything from the label onward is a different commentator's work.
    """
    match = LABEL_MARKER.search(commentary_text)
    return commentary_text[:match.start()].strip() if match else commentary_text


def letters_only(text):
    """Reduce text to lowercase letters and single spaces, for comparison."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z ]", " ", text.lower())).strip()


def is_fragment_of_couplet(explanation, couplet):
    """True when the 'explanation' is really just a slice of the verse translation.

    25 kurals have this defect. Kural 1156's explanation reads
        "Is hard, when he could stand, and of departure speak to me"
    which is the second line of its poetic couplet, not an explanation at all.
    The plain-prose explanation is simply absent for those records.

    The embedding audit found this — no text check could have. It is not empty,
    not duplicated, not mixed-script. It is just the wrong content.
    """
    explanation_letters = letters_only(explanation)
    return bool(explanation_letters) and explanation_letters in letters_only(couplet)


def tidy(text):
    """Final pass on any text field: remove invisible characters, collapse
    runs of whitespace, and drop the unbalanced square brackets that wrap
    Parimelazhagar's chapter preambles in the raw source."""
    text = ZERO_WIDTH_CHARACTERS.sub("", text)
    text = text.replace("[", "").replace("]", "")
    return re.sub(r"\s+", " ", text).strip()


def clean_text(raw_value):
    """Turn any raw field into a tidy single string.

    Some fields arrive as a plain string. Others arrive as a list whose first
    item is a label like 'பரிமேலழகர் உரை' and whose remaining items are the
    actual paragraphs. We drop the label and glue the paragraphs together.
    """
    if raw_value is None:                        # field absent entirely
        return ""
    if isinstance(raw_value, list):              # labelled, multi-part field
        paragraphs = [str(part).strip() for part in raw_value[1:]]
        return " ".join(part for part in paragraphs if part).strip()
    return str(raw_value).strip()                # already a plain string


def load_json(path):
    """Read a UTF-8 JSON file. UTF-8 matters — the text is Tamil script."""
    with open(path, encoding="utf-8") as json_file:
        return json.load(json_file)


# ---------------------------------------------------------------------------
# step 1 — load both raw sources
# ---------------------------------------------------------------------------

structured_kurals = load_json(STRUCTURED_SOURCE_PATH)["kural"]   # list of 1330

# this source is a dictionary whose KEYS are the kural numbers as strings
commentary_by_number_text = load_json(COMMENTARY_SOURCE_PATH)

# re-key it by integer so lookups are unambiguous
commentary_by_number = {
    int(number_text): record
    for number_text, record in commentary_by_number_text.items()
}


# ---------------------------------------------------------------------------
# step 2 — build one clean record per kural, joined BY NUMBER
# ---------------------------------------------------------------------------

clean_kurals = []

for structured_record in structured_kurals:
    kural_number = int(structured_record["Number"])

    # look the commentary up by NUMBER. missing numbers simply return {}
    commentary_record = commentary_by_number.get(kural_number, {})

    parimelazhagar = clean_text(commentary_record.get("6_parimela"))

    # Parimelazhagar opens each chapter with an introduction to the chapter as
    # a whole, wrapped in square brackets and glued onto that chapter's first
    # kural. It is real text, not junk, so we keep it — but we flag it, because
    # those 57 records are much longer than the rest and Phase 4 will want to
    # test whether that changes how they retrieve.
    has_chapter_preamble = parimelazhagar.lstrip().startswith("[")

    # text we sourced by hand, either to replace something wrong or to fill
    # something missing. It always wins over the raw sources.
    hand_sourced = HAND_SOURCED_FIELDS.get(kural_number, {})
    hand_sourced_fields_used = []

    # --- repair an english_explanation that is really a slice of the couplet ---
    english_explanation = tidy(clean_text(structured_record["explanation"]))
    english_couplet = tidy(clean_text(structured_record["couplet"]))
    explanation_source = "primary"

    if is_fragment_of_couplet(english_explanation, english_couplet):
        # the other raw source carries a different, genuinely prose translation
        alternate_explanation = tidy(clean_text(commentary_record.get("6_explanation")))
        if alternate_explanation:
            english_explanation = alternate_explanation
            explanation_source = "alternate"

    def field(field_name, raw_value):
        """Hand-sourced text wins; otherwise tidy whatever the raw source gave."""
        if field_name in hand_sourced:
            hand_sourced_fields_used.append(field_name)
            return tidy(hand_sourced[field_name])
        return tidy(raw_value)

    clean_kurals.append({
        "number": kural_number,

        # --- where the kural sits in the book (display / filtering) ---
        "section_tamil":      field("section_tamil", clean_text(structured_record["paul_name"])),
        "section_english":    field("section_english", clean_text(structured_record["paul_translation"])),
        "subsection_tamil":   field("subsection_tamil", clean_text(structured_record["iyal_name"])),
        "subsection_english": field("subsection_english", clean_text(structured_record["iyal_translation"])),
        "chapter_tamil":      field("chapter_tamil", clean_text(structured_record["adikaram_name"])),
        "chapter_english":    field("chapter_english", clean_text(structured_record["adikaram_translation"])),

        # --- the verse itself, classical Tamil ---
        "kural_line1": field("kural_line1", clean_text(structured_record["Line1"])),
        "kural_line2": field("kural_line2", clean_text(structured_record["Line2"])),
        "transliteration": field("transliteration",
            clean_text(structured_record["transliteration1"]) + " " +
            clean_text(structured_record["transliteration2"])),

        # --- English, three different flavours (see LEARNING_LOG) ---
        "english_translation": field("english_translation", clean_text(structured_record["Translation"])),
        "english_couplet":     field("english_couplet", english_couplet),
        "english_explanation": field("english_explanation", english_explanation),
        # "primary" = the structured source. "alternate" = repaired, because the
        # primary held a slice of the couplet instead of a prose explanation.
        "english_explanation_source": explanation_source,

        # --- modern Tamil prose meanings ---
        # Mu.Varadarajan and Solomon Pappaiah are taken from the STRUCTURED
        # source. The commentary source's versions are dirtier: it runs two
        # commentators together in some records (kurals 319, 320) and carries
        # kural 810's meaning under kural 870.
        "tamil_meaning_mu_varadarajan": field("tamil_meaning_mu_varadarajan",
            clean_text(structured_record["mv"])),
        "tamil_meaning_solomon_pappaiah": field("tamil_meaning_solomon_pappaiah",
            clean_text(structured_record["sp"])),
        # only the commentary source has Karunanidhi, so it needs the full clean-up
        "tamil_meaning_karunanidhi": field("tamil_meaning_karunanidhi",
            cut_at_next_label(strip_english_sections(
                clean_text(commentary_record.get("6_mu_karu"))))),

        # --- classical commentaries ---
        "parimelazhagar_commentary": field("parimelazhagar_commentary",
            cut_at_next_label(strip_english_sections(parimelazhagar))),
        "parimelazhagar_has_chapter_preamble": has_chapter_preamble,
        "manakkudavar_commentary": field("manakkudavar_commentary",
            cut_at_next_label(strip_english_sections(
                clean_text(commentary_record.get("6_manikudavar"))))),

        # provenance: which fields did NOT come from the bulk sources.
        # Phase 5 will want to know, if any of these records behave oddly.
        "hand_sourced_fields": sorted(hand_sourced_fields_used),
    })


# ---------------------------------------------------------------------------
# step 3 — check the result BEFORE writing it
#
# These checks exist because the bugs in this data do not crash. They produce
# a file that looks fine. The only defence is counting on purpose.
# ---------------------------------------------------------------------------

problems = []

if len(clean_kurals) != TOTAL_KURALS:
    problems.append(f"expected {TOTAL_KURALS} kurals, built {len(clean_kurals)}")

numbers_present = [record["number"] for record in clean_kurals]
missing_numbers = [n for n in range(1, TOTAL_KURALS + 1) if n not in set(numbers_present)]
if missing_numbers:
    problems.append(f"missing kural numbers: {missing_numbers}")

if len(numbers_present) != len(set(numbers_present)):
    problems.append("duplicate kural numbers found")

# every field that must never be empty, for every single kural
# every one of these is now complete for all 1330, so any future regression
# stops the build instead of shipping a hole
REQUIRED_FIELDS = [
    "kural_line1", "kural_line2", "transliteration",
    "english_translation", "english_couplet", "english_explanation",
    "tamil_meaning_mu_varadarajan", "tamil_meaning_solomon_pappaiah",
    "tamil_meaning_karunanidhi",
    "parimelazhagar_commentary", "manakkudavar_commentary",
    "chapter_tamil", "chapter_english",
    "subsection_tamil", "subsection_english",
    "section_tamil", "section_english",
]
for field_name in REQUIRED_FIELDS:
    empty_for = [r["number"] for r in clean_kurals if not r[field_name]]
    if empty_for:
        problems.append(f"{field_name} empty for kurals: {empty_for[:15]}")

# Tamil fields must not contain runs of English words. This caught 664 records
# whose Manakkudavar commentary had an English translation glued onto the end.
LATIN_WORD = re.compile(r"[A-Za-z]{4,}")
TAMIL_ONLY_FIELDS = [
    "kural_line1", "kural_line2",
    "tamil_meaning_mu_varadarajan", "tamil_meaning_solomon_pappaiah",
    "tamil_meaning_karunanidhi",
    "parimelazhagar_commentary", "manakkudavar_commentary",
]
for field_name in TAMIL_ONLY_FIELDS:
    polluted = [r["number"] for r in clean_kurals if LATIN_WORD.search(r[field_name])]
    if polluted:
        problems.append(
            f"{field_name} contains English words in {len(polluted)} kurals: {polluted[:10]}")

# no explanation may be a verbatim slice of its own couplet — that means the
# prose explanation is missing and a line of the verse translation took its place
still_fragments = [r["number"] for r in clean_kurals
                   if is_fragment_of_couplet(r["english_explanation"], r["english_couplet"])]
if still_fragments:
    problems.append(
        f"english_explanation is a couplet fragment for {len(still_fragments)} "
        f"kurals: {still_fragments[:10]}")

if problems:
    print("PROBLEMS FOUND — nothing was written:")
    for problem in problems:
        print("  -", problem)
    raise SystemExit(1)


# ---------------------------------------------------------------------------
# step 4 — write the clean corpus
# ---------------------------------------------------------------------------

with open(OUTPUT_PATH, "w", encoding="utf-8") as output_file:
    # ensure_ascii=False keeps Tamil readable in the file instead of அ escapes
    json.dump(clean_kurals, output_file, ensure_ascii=False, indent=2)

print(f"OK — wrote {len(clean_kurals)} kurals to {OUTPUT_PATH.relative_to(PROJECT_ROOT)}")
for record in clean_kurals:
    if record["hand_sourced_fields"]:
        print(f"     kural {record['number']:4} hand-sourced: "
              f"{', '.join(record['hand_sourced_fields'])}")
