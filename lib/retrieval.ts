import "server-only";

import { allKurals, getKural } from "./corpus";
import { recordError } from "./logger";
import type {
  Confidence,
  Kural,
  QueryLanguage,
  RetrievalOutcome,
  RetrievedKural,
} from "./types";

/**
 * ============================================================================
 * TWO ENGINES. The real one, and the word-overlap one behind it as a net.
 * ============================================================================
 *
 * `embeddingEngine` is the real retriever, added 2026-08-02: it calls the
 * Python service in service/app.py, which has Sarvam-105B rewrite the question
 * into the vocabulary the verses use, scores all 1330 verses by meaning and by
 * keyword, and rereads the top 50 with a cross-encoder. Measured at 90 of 100
 * on the golden set in data/golden_set.json.
 *
 * `lexicalEngine` is what shipped before it, and it stays. It is word overlap:
 * it finds a verse when the question happens to use the same words the
 * translation uses, and misses when it does not. Ask it "how do I keep my
 * temper" and it finds little, because no translation uses the word "temper".
 * That exact gap is what the embeddings closed — 44 of 100 to 90 of 100.
 *
 * It is kept because the real engine lives in another process, and a process
 * can be down. `resilientEngine` falls back to it and CHANGES THE ENGINE NAME
 * when it does, so a reader is never shown degraded results under the better
 * engine's name.
 *
 * Every engine reports its own name and its own thresholds, and the interface
 * displays them. A score is never presented without its source.
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
  /**
   * Async because the real engine is a network call to a separate Python
   * process (service/app.py). It has to be: LaBSE takes seconds and about a
   * gigabyte to load, so the models are held in a long-running process rather
   * than loaded per request. The word-overlap engine does no I/O at all and
   * simply satisfies the same signature.
   */
  /**
   * `requestId` is optional and is passed straight through to the Python
   * service, which writes it into its own log. Both sides logging the same id
   * is what lets one question's two log lines be read together afterwards.
   * Engines that make no network call simply ignore it.
   */
  search(
    query: string,
    limit: number,
    requestId?: string,
  ): Promise<RetrievalOutcome>;
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

  async search(query, limit) {
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

// ---------------------------------------------------------------------------
// the real engine
// ---------------------------------------------------------------------------

/**
 * Where the Python retrieval service listens. See service/app.py for why it is
 * a separate process at all: LaBSE takes seconds and about a gigabyte to load,
 * so it is loaded once and held, not loaded per request.
 */
const RETRIEVAL_SERVICE_URL =
  process.env.RETRIEVAL_SERVICE_URL ?? "http://127.0.0.1:8000";

/** Give up rather than leave a reader watching a spinner forever. */
const SERVICE_TIMEOUT_MS = 20_000;

/** What service/app.py sends back. Mirrors its /search response. */
interface ServiceResponse {
  query: string;
  queryLanguage: QueryLanguage;
  searchedFor: string;
  /**
   * What produced `searchedFor`. Either the model's name, or a plain sentence
   * saying why there was no rewrite. The rewriter is the only part of the
   * pipeline that leaves the machine, so it is the only part that can be
   * missing while everything else still works — and a search running without
   * it scores about 144 of 233 instead of 170. That gap must be visible.
   */
  rewrittenBy: string;
  results: { kural: { number: number }; score: number }[];
  topScore: number;
  confidence: Confidence;
  calibrated: boolean;
  engine: string;
  elapsedMs: number;
  cached: boolean;
}

export const embeddingEngine: RetrievalEngine = {
  name: "Sarvam HyDE + LaBSE + BM25 + cross-encoder rerank",
  description:
    "Rewrites the question into the vocabulary the verses actually use with Sarvam-105B, scores every one of the 1330 verses by meaning and by keyword, blends in the chapter signal, then rereads the top 50 against the original question with a cross-encoder. Measured at 90 of 100 on a hand-built English question set, and 170 of 233 on the wider set.",

  /*
   * STILL FALSE, AND STILL FOR A MEASURED REASON.
   *
   * This engine ranks far better than the word-overlap one it replaced — 85 of
   * 100 against a 44 baseline. That is a statement about ORDER within a
   * question, and it is not the same claim as "the score knows when the book
   * has nothing to say".
   *
   * src/calibrate.py runs the same on-topic/off-topic test that condemned the
   * placeholder engine. Until it reports a clean separation, this stays false
   * and the interface must not refuse or claim confidence on this engine's
   * behalf. Python is the source of truth: pipeline.py exports the same flag,
   * and the service reports it on /health.
   */
  calibrated: false,
  highConfidence: 1.01, // unreachable on purpose while uncalibrated
  floor: 0,

  async search(query, limit, requestId) {
    const startedAt = performance.now();
    const url = `${RETRIEVAL_SERVICE_URL}/search?q=${encodeURIComponent(query)}&limit=${limit}`;

    const response = await fetch(url, {
      signal: AbortSignal.timeout(SERVICE_TIMEOUT_MS),
      cache: "no-store",
      // Carried into the Python service's log line for this same search.
      headers: requestId ? { "X-Request-Id": requestId } : undefined,
    });
    if (!response.ok) {
      throw new Error(`retrieval service returned ${response.status}`);
    }
    const payload = (await response.json()) as ServiceResponse;

    // Resolve verses from THIS app's own corpus rather than rendering whatever
    // the wire sent. The service and the interface must agree on what kural
    // 301 says, and the only way to guarantee that is to look it up here.
    const results: RetrievedKural[] = [];
    for (const item of payload.results) {
      const kural = getKural(item.kural.number);
      if (!kural) continue; // a number the corpus does not have is not shown
      results.push({ kural, score: item.score });
    }

    return {
      query,
      queryLanguage: payload.queryLanguage,
      results,
      topScore: payload.topScore,
      confidence: payload.confidence,
      // The rewriter can be down while the rest of the pipeline is fine. When
      // that happens the reader is looking at a measurably worse search, so
      // the engine name says so — the same rule as the service-down fallback
      // below. A degraded search must never wear the full engine's name.
      engine: payload.rewrittenBy.startsWith("none (rewriter")
        ? `${this.name} — DEGRADED, the question was not rewritten`
        : this.name,
      // measured here, not there: this includes the network hop the reader
      // actually waits through
      elapsedMs: Math.round((performance.now() - startedAt) * 10) / 10,
    };
  },
};

/**
 * The real engine, with the word-overlap one behind it as a net.
 *
 * If the Python service is down, the reader still gets results — but the
 * engine name they are shown changes to say so. The interface displays that
 * field on every screen, so degraded mode announces itself rather than quietly
 * serving worse answers under the better engine's name. Silently falling back
 * would be the same sin as an unmeasured metric.
 */
export const resilientEngine: RetrievalEngine = {
  ...embeddingEngine,

  async search(query, limit, requestId) {
    try {
      return await embeddingEngine.search(query, limit, requestId);
    } catch (error) {
      const reason = error instanceof Error ? error.message : "unknown error";
      recordError({
        requestId: requestId ?? "-",
        whatFailed: "retrieval service unreachable",
        message: reason,
        query,
      });

      const fallback = await lexicalEngine.search(query, limit);
      return {
        ...fallback,
        engine: `${lexicalEngine.name} — FALLBACK, the embedding service is unreachable`,
      };
    }
  },
};

/**
 * The engine the app uses. This is the one line the file was written to have
 * changed, and this is the change.
 */
export const ACTIVE_ENGINE: RetrievalEngine = resilientEngine;

export const DEFAULT_RESULT_LIMIT = 5;
