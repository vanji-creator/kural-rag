/**
 * The shape of one record in data/kurals.json.
 *
 * These field names are the ones src/build_corpus.py writes, and the build
 * script refuses to emit a record with any of them missing. If a field name
 * changes there, it changes here too — there is exactly one spelling of each.
 */
export interface Kural {
  number: number;

  /** பால் — the three books: Virtue, Wealth, Love */
  section_tamil: string;
  section_english: string;

  /** இயல் — 13 groupings of chapters inside the books */
  subsection_tamil: string;
  subsection_english: string;

  /** அதிகாரம் — 133 chapters of exactly 10 verses */
  chapter_tamil: string;
  chapter_english: string;

  /** the couplet itself, in Tamil, as two lines */
  kural_line1: string;
  kural_line2: string;

  /** the couplet in Latin letters, for readers who cannot read Tamil script */
  transliteration: string;

  /** short verse-form English rendering */
  english_translation: string;
  /** the fuller poetic couplet in English; semicolon separates its two lines */
  english_couplet: string;
  /** plain English prose — what the verse actually says */
  english_explanation: string;
  /** "primary" or "alternate": which raw source the explanation came from */
  english_explanation_source: string;

  /** modern Tamil prose readings, three editors */
  tamil_meaning_mu_varadarajan: string;
  tamil_meaning_solomon_pappaiah: string;
  tamil_meaning_karunanidhi: string;

  /** classical commentary — Tamil only, no English version exists */
  parimelazhagar_commentary: string;
  /** true when the commentary opens with the chapter's preamble */
  parimelazhagar_has_chapter_preamble: boolean;
  manakkudavar_commentary: string;

  /** fields that were filled by hand because no source carried them */
  hand_sourced_fields: string[];
}

/** One chapter: 10 consecutive kurals under one title. */
export interface Chapter {
  /** 1..133 */
  number: number;
  tamil: string;
  english: string;
  sectionTamil: string;
  sectionEnglish: string;
  subsectionTamil: string;
  subsectionEnglish: string;
  /** inclusive kural numbers this chapter covers */
  firstKural: number;
  lastKural: number;
}

/** One subsection: a run of chapters inside a book. */
export interface Subsection {
  tamil: string;
  english: string;
  chapters: Chapter[];
}

/** One of the three books. */
export interface Section {
  tamil: string;
  english: string;
  firstChapter: number;
  lastChapter: number;
  subsections: Subsection[];
}

/** A kural the retriever returned, with the score that put it there. */
export interface RetrievedKural {
  kural: Kural;
  /** 0..1, higher is a closer match */
  score: number;
}

/**
 * What the retrieval step hands to the interface.
 *
 * `engine` is displayed to the reader on purpose. A score means nothing
 * without knowing what produced it, and this project's whole claim is that
 * you can see how the answer was reached.
 */
export interface RetrievalOutcome {
  query: string;
  /** "en" | "ta" | "thanglish" — what script/language the query was read as */
  queryLanguage: QueryLanguage;
  results: RetrievedKural[];
  topScore: number;
  confidence: Confidence;
  engine: string;
  elapsedMs: number;
}

export type QueryLanguage = "en" | "ta" | "thanglish";

/**
 * high  — answer normally
 * low   — answer, but show the doubt above it
 * none  — refuse: no answer, no ranked list
 */
export type Confidence = "high" | "low" | "none";

/** One run of answer text, optionally followed by a citation to a kural. */
export interface AnswerPart {
  text: string;
  /** kural number this clause is grounded in, or null for plain text */
  cite: number | null;
}

/** The full response the search page renders. */
export interface SearchResponse {
  retrieval: RetrievalOutcome;
  /**
   * null until Phase 7 connects a generator. The interface renders retrieved
   * verses without it — an answer is the last thing added, not the first.
   */
  answer: AnswerParts | null;
}

export interface AnswerParts {
  parts: AnswerPart[];
  groundedIn: number;
  meta: string;
}
