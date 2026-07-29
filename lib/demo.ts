import "server-only";

import { getKurals } from "./corpus";
import type { AnswerPart, SearchResponse } from "./types";

/**
 * Canned states, for looking at the interface.
 *
 * Every one of these is sample copy written for the design, not output from
 * a working system — there is no generator connected yet. They exist because
 * some states (a strong grounded answer, a low-confidence answer, a refusal)
 * cannot be produced on demand by a real search, and an interface whose
 * states you cannot look at is an interface you cannot review.
 *
 * The verses and scores below are the designer's, chosen to exercise the
 * layout. Anything reached this way is marked "demo state" on screen, and
 * that marker is not optional — an unlabelled fabricated answer is the exact
 * failure this whole product is built to avoid.
 */

interface DemoScenario {
  key: string;
  label: string;
  query: string;
  queryLanguage: "en" | "ta" | "thanglish";
  confidence: "high" | "low" | "none";
  kuralNumbers: number[];
  scores: number[];
  /** [text, kural number cited after it] */
  parts: [string, number?][];
  meta: string;
  /** for the refusal state, the best score that still fell under the floor */
  topScore?: number;
}

const SCENARIOS: DemoScenario[] = [
  {
    key: "anger_en",
    label: "strong answer",
    query: "How do I stop being controlled by my anger?",
    queryLanguage: "en",
    confidence: "high",
    kuralNumbers: [305, 301, 302, 309],
    scores: [0.87, 0.84, 0.79, 0.74],
    parts: [
      ["The Kural treats anger as damage to the self before it is damage to anyone else: guard yourself by guarding your anger, or the anger kills the one holding it", 305],
      [". It refuses the excuse of powerlessness — restraint counts where the anger could actually land", 301],
      [", and it condemns both directions: useless where it cannot reach, worst of all where it can", 302],
      [". What is asked is not suppression but non-arising; the mind that never entertains anger gets what it seeks", 309],
      ["."],
    ],
    meta: "chapter 31 · வெகுளாமை",
  },
  {
    key: "anger_ta",
    label: "tamil query",
    query: "சினத்தை அடக்குவது எப்படி?",
    queryLanguage: "ta",
    confidence: "high",
    kuralNumbers: [305, 301, 309],
    scores: [0.85, 0.81, 0.73],
    parts: [
      ["Anger is read as self-harm first: guard the self by guarding anger", 305],
      [", and restraint only counts where the anger has somewhere to land", 301],
      [". The chapter's promise is practical rather than moral — an unangered mind reaches what it intends", 309],
      ["."],
    ],
    meta: "chapter 31 · வெகுளாமை",
  },
  {
    key: "anger_tg",
    label: "thanglish",
    query: "sinam adakkuvadhu eppadi",
    queryLanguage: "thanglish",
    confidence: "low",
    kuralNumbers: [305, 301, 302],
    scores: [0.68, 0.62, 0.57],
    parts: [
      ["Read as Thanglish, the query still lands in chapter 31: guard anger to guard yourself", 305],
      [", and restraint counts where anger has power to act", 301],
      [". Scores are lower than the same question in Tamil script, so treat the ranking as approximate", 302],
      ["."],
    ],
    meta: "transliterated · both scripts searched",
  },
  {
    key: "lie",
    label: "low confidence",
    query: "Is it ever right to lie in order to protect someone?",
    queryLanguage: "en",
    confidence: "low",
    kuralNumbers: [292, 291],
    scores: [0.66, 0.58],
    parts: [
      ["Two verses bear on this, and neither is addressed to your case directly. Falsehood is admitted into the place of truth when it yields a good entirely free of fault", 292],
      [", while truthfulness itself is defined not as accuracy but as speech that causes no harm", 291],
      [". The text sets a condition rather than granting permission; read both before relying on this."],
    ],
    meta: "chapter 30 · வாய்மை",
  },
  {
    key: "crypto",
    label: "no match",
    query: "Should I move my savings into crypto this year?",
    queryLanguage: "en",
    confidence: "none",
    kuralNumbers: [],
    scores: [],
    parts: [],
    meta: "",
    topScore: 0.24,
  },
];

export const DEMO_LABELS = SCENARIOS.map((scenario) => ({
  key: scenario.key,
  label: scenario.label,
}));

export function getDemoResponse(key: string): SearchResponse | null {
  const scenario = SCENARIOS.find((candidate) => candidate.key === key);
  if (!scenario) return null;

  const kurals = getKurals(scenario.kuralNumbers);

  const results = kurals.map((kural) => {
    const position = scenario.kuralNumbers.indexOf(kural.number);
    return { kural, score: scenario.scores[position] ?? 0 };
  });

  const parts: AnswerPart[] = scenario.parts.map(([text, cite]) => ({
    text,
    cite: cite ?? null,
  }));

  return {
    retrieval: {
      query: scenario.query,
      queryLanguage: scenario.queryLanguage,
      results,
      topScore: scenario.topScore ?? scenario.scores[0] ?? 0,
      confidence: scenario.confidence,
      engine: "demo state · not a real search",
      elapsedMs: 0,
    },
    answer:
      scenario.confidence === "none"
        ? null
        : {
            parts,
            groundedIn: results.length,
            meta: scenario.meta,
          },
  };
}

export function isDemoKey(key: string): boolean {
  return SCENARIOS.some((scenario) => scenario.key === key);
}
