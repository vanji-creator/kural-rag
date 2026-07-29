import "server-only";

import { allKurals } from "./corpus";
import type {
  Confidence,
  Kural,
  QueryLanguage,
  RetrievalOutcome,
  RetrievedKural,
} from "./types";

/**
 * ============================================================================
 * THIS IS A STAND-IN. IT DOES NOT UNDERSTAND MEANING.
 * ============================================================================
 *
 * The real retriever — embed the question, compare it against 1330 verse
 * vectors, rank by cosine similarity — is Phases 2 to 6 of this project and
 * does not exist yet. This module exists so the interface can be built,
 * exercised and shipped before it does.
 *
 * What is here instead is word overlap. It finds a verse when the question
 * happens to use the same words the translation uses, and misses completely
 * when it does not. Ask it "how do I stop being controlled by my anger" and
 * it will find the anger chapter, because the word "anger" is right there in
 * the English. Ask it "how do I keep my temper" and it will find much less,
 * because no translation uses the word "temper". That gap is exactly what
 * embeddings are for, and it is why this file is temporary.
 *
 * Every engine reports its own name and its own thresholds, and the interface
 * displays them. Swapping this for the real thing means writing a second
 * RetrievalEngine and changing ACTIVE_ENGINE below. Nothing in the UI changes.
 */

export interface RetrievalEngine {
  /** shown to the reader, so a score is never presented without its source */
  name: string;
  /** one line explaining what this engine actually does */
  description: string;
  /** at or above this score, answer normally */
  highConfidence: number;
  /** below this score, refuse: no answer, no ranked list */
  floor: number;
  /**
   * Whether this engine's scores mean anything across different questions.
   *
   * An uncalibrated engine may still rank well *within* one question — its
   * best result really is its best result — while its absolute numbers say
   * nothing about whether the book addresses the question at all. The whole
   * refusal policy rests on that second property, so an engine without it
   * must not be allowed to refuse or to claim confidence. See the note on
   * lexicalEngine below for the measurement behind this flag.
   */
  calibrated: boolean;
  search(query: string, limit: number): RetrievalOutcome;
}

// ---------------------------------------------------------------------------
// reading the query
// ---------------------------------------------------------------------------

/** Tamil script occupies one contiguous block of Unicode. */
const TAMIL_SCRIPT = /[஀-௿]/;

/**
 * Letter patterns that are common in romanized Tamil and rare in English.
 * This is a heuristic, not a language detector, and it is allowed to be
 * wrong — being read as English costs the reader a worse ranking, not a
 * wrong answer.
 */
const THANGLISH_MARKERS =
  /(zh|dh[aeiou]|thth|kk[aeiou]|nn[aeiou]|pp[aeiou]|vadhu|eppadi|illai|enna|ondru|adakku)/;

/** Words so common that matching on them says nothing about relevance. */
const ENGLISH_STOPWORDS = new Set([
  "a", "about", "all", "am", "an", "and", "any", "are", "as", "at", "be",
  "been", "being", "but", "by", "can", "did", "do", "does", "for", "from",
  "get", "had", "has", "have", "he", "her", "him", "his", "how", "i", "if",
  "in", "into", "is", "it", "its", "just", "me", "more", "most", "my", "no",
  "not", "of", "on", "one", "or", "our", "out", "over", "own", "said", "same",
  "say", "says", "she", "should", "so", "some", "such", "than", "that", "the",
  "their", "them", "then", "there", "these", "they", "this", "those", "to",
  "too", "under", "up", "very", "was", "we", "were", "what", "when", "where",
  "which", "while", "who", "why", "will", "with", "would", "you", "your",
]);

/**
 * A few English words that would otherwise make a Thanglish query look
 * English. If the query is mostly these, it is English.
 */
const CLEARLY_ENGLISH = new Set([
  "anger", "angry", "control", "friend", "friendship", "wealth", "poverty",
  "love", "truth", "lie", "king", "learning", "rain", "god", "wife", "child",
  "children", "food", "speech", "words", "kindness", "gratitude", "envy",
  "fate", "death", "virtue", "does", "say", "about", "what", "how", "should",
]);

export function detectQueryLanguage(query: string): QueryLanguage {
  if (TAMIL_SCRIPT.test(query)) return "ta";

  const words = query.toLowerCase().split(/[^a-z]+/).filter(Boolean);
  if (words.length === 0) return "en";

  const englishWords = words.filter(
    (word) => ENGLISH_STOPWORDS.has(word) || CLEARLY_ENGLISH.has(word),
  ).length;
  const looksTamil = THANGLISH_MARKERS.test(query.toLowerCase());

  // mostly non-English words, with romanized-Tamil letter patterns in them
  if (looksTamil && englishWords / words.length < 0.5) return "thanglish";
  return "en";
}

// ---------------------------------------------------------------------------
// the searchable text of one kural, per language
// ---------------------------------------------------------------------------

/**
 * Which fields a query of each language is matched against.
 *
 * This matters more than it looks. A Tamil question compared against English
 * prose would score near zero for the right verse — not because the verse is
 * wrong but because the words are in the wrong language. Word overlap cannot
 * cross languages at all. (A shared embedding space is precisely the thing
 * that can, which is the point of Phase 2.)
 */
function searchableText(kural: Kural, language: QueryLanguage): string {
  if (language === "ta") {
    return [
      kural.kural_line1,
      kural.kural_line2,
      kural.tamil_meaning_mu_varadarajan,
      kural.tamil_meaning_solomon_pappaiah,
      kural.tamil_meaning_karunanidhi,
      kural.chapter_tamil,
    ].join(" ");
  }

  if (language === "thanglish") {
    // the transliteration is the only field written in the same alphabet a
    // Thanglish question uses, so it carries almost all the weight
    return [kural.transliteration, kural.chapter_english].join(" ");
  }

  return [
    kural.english_explanation,
    kural.english_translation,
    kural.english_couplet,
    kural.chapter_english,
  ].join(" ");
}

/**
 * Split text into comparable pieces.
 *
 * English and Tamil are compared word by word. Thanglish cannot be, because
 * there is no agreed spelling: the corpus writes "Sinamennum", a reader
 * writes "sinam", and as whole words those two share nothing. So Thanglish
 * is compared as overlapping four-letter runs instead — "sinam" produces
 * "sina" and "inam", both of which sit inside "sinamennum". Spelling drift
 * costs a few of the runs rather than all of the match.
 */
function tokenize(text: string, language: QueryLanguage): string[] {
  const lowered = text.toLowerCase();

  if (language === "thanglish") {
    const grams: string[] = [];
    for (const word of lowered.split(/[^a-z]+/)) {
      if (word.length < 3) continue;
      if (word.length <= 4) {
        grams.push(word);
        continue;
      }
      for (let start = 0; start + 4 <= word.length; start += 1) {
        grams.push(word.slice(start, start + 4));
      }
    }
    return grams;
  }

  const pattern = language === "ta" ? /[^஀-௿]+/ : /[^a-z0-9]+/;
  return lowered.split(pattern).filter((word) => word.length > 1);
}

// ---------------------------------------------------------------------------
// the index — built once, on first search
// ---------------------------------------------------------------------------

interface LanguageIndex {
  /** for each kural, how many times each word appears */
  documents: Map<string, number>[];
  /** for each word, how much a match on it is worth */
  wordWeight: Map<string, number>;
}

const indexCache = new Map<QueryLanguage, LanguageIndex>();

function getIndex(language: QueryLanguage): LanguageIndex {
  const cached = indexCache.get(language);
  if (cached) return cached;

  const documents = allKurals.map((kural) => {
    const counts = new Map<string, number>();
    for (const word of tokenize(searchableText(kural, language), language)) {
      counts.set(word, (counts.get(word) ?? 0) + 1);
    }
    return counts;
  });

  // how many of the 1330 verses contain each word
  const documentFrequency = new Map<string, number>();
  for (const counts of documents) {
    for (const word of counts.keys()) {
      documentFrequency.set(word, (documentFrequency.get(word) ?? 0) + 1);
    }
  }

  // A word in 900 of 1330 verses tells you almost nothing; a word in 4 tells
  // you a great deal. This is the standard inverse-document-frequency weight:
  // rare words are worth more. It is the oldest trick in text search, and it
  // is worth seeing it work before replacing it with something that doesn't
  // count words at all.
  const wordWeight = new Map<string, number>();
  const total = documents.length;
  for (const [word, frequency] of documentFrequency) {
    wordWeight.set(word, Math.log(total / frequency));
  }

  const index: LanguageIndex = { documents, wordWeight };
  indexCache.set(language, index);
  return index;
}

// ---------------------------------------------------------------------------
// the stand-in engine
// ---------------------------------------------------------------------------

export const lexicalEngine: RetrievalEngine = {
  name: "word overlap · no embeddings yet",
  description:
    "Ranks verses by how many rare words they share with the question. It cannot match meaning across different wording, and it cannot match an English question to a Tamil verse at all.",

  /*
   * MEASURED, NOT ASSUMED.
   *
   * The design specified a refusal policy: answer above 0.70, show doubt
   * between 0.45 and 0.69, refuse below 0.45. Before wiring those numbers up,
   * ten on-topic questions and seven off-topic ones were run through this
   * engine to see where the two groups separated.
   *
   * They did not separate. Selected results:
   *
   *     0.283   is it wrong to eat meat                  (on topic)
   *     0.363   how do I stop being controlled by anger  (on topic)
   *     0.847   who won the football world cup           (OFF topic)
   *     1.000   what does it say about friendship        (on topic)
   *
   * "Who won the football world cup" outscored most real questions, because
   * "won", "world" and "cup" all appear in translations of verses about
   * conquest and abundance. There is no threshold that puts the on-topic
   * questions on one side and the off-topic ones on the other, so any floor
   * chosen here would be decoration.
   *
   * Hence calibrated: false. The engine still ranks sensibly *within* one
   * question — the anger question really does surface the anger chapter —
   * but its absolute score carries no information about whether the book
   * addresses the question at all. The interface is told this and refuses to
   * claim confidence on its behalf.
   *
   * The floor below is therefore only "did anything match at all", not a
   * judgement about relevance.
   */
  calibrated: false,
  highConfidence: 1.01, // unreachable on purpose: this engine cannot say "high"
  floor: 0.001,

  search(query, limit) {
    const startedAt = performance.now();
    const language = detectQueryLanguage(query);
    const { documents, wordWeight } = getIndex(language);

    const queryWords = tokenize(query, language).filter(
      (word) => language !== "en" || !ENGLISH_STOPWORDS.has(word),
    );

    // total weight available if every query word were matched
    const availableWeight = queryWords.reduce(
      (total, word) => total + (wordWeight.get(word) ?? 0),
      0,
    );

    const scored: RetrievedKural[] = [];

    if (availableWeight > 0) {
      for (let position = 0; position < allKurals.length; position += 1) {
        const counts = documents[position];
        let matchedWeight = 0;

        for (const word of new Set(queryWords)) {
          if (!counts.has(word)) continue;
          const weight = wordWeight.get(word) ?? 0;
          // a second occurrence of the same word is worth less than the first
          const occurrences = counts.get(word) ?? 0;
          matchedWeight += weight * (1 + Math.log(occurrences)) / 2;
        }

        if (matchedWeight <= 0) continue;
        scored.push({
          kural: allKurals[position],
          score: Math.min(1, matchedWeight / availableWeight),
        });
      }
    }

    scored.sort((first, second) => second.score - first.score);
    const results = scored.slice(0, limit);
    const topScore = results.length > 0 ? results[0].score : 0;

    let confidence: Confidence = "none";
    if (topScore >= this.highConfidence) confidence = "high";
    else if (topScore >= this.floor) confidence = "low";

    return {
      query,
      queryLanguage: language,
      // refusing means refusing: below the floor, nothing is listed at all
      results: confidence === "none" ? [] : results,
      topScore,
      confidence,
      engine: this.name,
      elapsedMs: Math.round((performance.now() - startedAt) * 10) / 10,
    };
  },
};

/**
 * The engine the app uses. Phase 6 replaces this line, and only this line.
 */
export const ACTIVE_ENGINE: RetrievalEngine = lexicalEngine;

export const DEFAULT_RESULT_LIMIT = 5;
