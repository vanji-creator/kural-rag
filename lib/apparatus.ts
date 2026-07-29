import type { Kural } from "./types";

/**
 * The scholarly apparatus around a verse: the other translations, the modern
 * Tamil readings, the classical commentaries.
 *
 * Pure functions of one record, so the result card and the full verse page
 * agree on what exists and who wrote it. No file access, no corpus import —
 * these run on the client too.
 */

export interface AltTranslation {
  label: string;
  text: string;
}

export interface Meaning {
  who: string;
  text: string;
}

export interface Commentary {
  who: string;
  era: string;
  text: string;
  /** the commentary opens with the chapter's preamble, not the verse gloss */
  hasChapterPreamble: boolean;
  /** shown as "1,240 chars" — commentary length varies enormously */
  length: string;
}

/** The couplet's two English lines, as the source separates them. */
export function coupletLines(kural: Kural): string[] {
  return kural.english_couplet
    .split(";")
    .map((line) => line.trim())
    .filter(Boolean);
}

export function altTranslations(kural: Kural): AltTranslation[] {
  return [
    { label: "Verse translation", text: coupletLines(kural).join(" / ") },
    { label: "Short gloss", text: kural.english_translation },
  ].filter((translation) => translation.text.length > 0);
}

export function meanings(kural: Kural): Meaning[] {
  return [
    { who: "மு. வரதராசன்", text: kural.tamil_meaning_mu_varadarajan },
    { who: "சாலமன் பாப்பையா", text: kural.tamil_meaning_solomon_pappaiah },
    { who: "கலைஞர் மு. கருணாநிதி", text: kural.tamil_meaning_karunanidhi },
  ].filter((meaning) => meaning.text.trim().length > 0);
}

export function commentaries(kural: Kural): Commentary[] {
  return [
    {
      who: "பரிமேலழகர்",
      era: "13th c.",
      text: kural.parimelazhagar_commentary,
      hasChapterPreamble: kural.parimelazhagar_has_chapter_preamble,
      length: describeLength(kural.parimelazhagar_commentary),
    },
    {
      who: "மணக்குடவர்",
      era: "c. 11th c.",
      text: kural.manakkudavar_commentary,
      hasChapterPreamble: false,
      length: describeLength(kural.manakkudavar_commentary),
    },
  ];
}

function describeLength(text: string): string {
  if (!text.trim()) return "—";
  return `${text.length.toLocaleString("en-US")} chars`;
}

/** Every chapter is exactly ten verses, so this is arithmetic, not a lookup. */
export function chapterNumberOf(kuralNumber: number): number {
  return Math.ceil(kuralNumber / 10);
}
