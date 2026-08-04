"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { NoticeBlock, type Notice } from "./NoticeBlock";
import { ResultCard } from "./ResultCard";
import { ThinkingScreen } from "./ThinkingScreen";
import type { SearchResponse } from "@/lib/types";

type Phase = "rest" | "thinking" | "answer" | "error";

interface EngineInfo {
  name: string;
  description: string;
  highConfidence: number;
  floor: number;
  /** false when the engine's absolute scores carry no meaning across questions */
  calibrated: boolean;
}

interface SearchExperienceProps {
  engine: EngineInfo;
  corpusSize: number;
  initialResponse: SearchResponse | null;
  initialPhase: Phase;
  /** a question arriving in the URL, e.g. from "ask about this chapter" */
  initialQuery: string;
  isDemo: boolean;
}

const EXAMPLE_QUERIES = [
  {
    tag: "EN",
    query: "How do I stop being controlled by my anger?",
    lang: "en",
    font: "var(--f-text)",
    fontSize: "15.5px",
  },
  {
    tag: "தமிழ்",
    query: "சினத்தை அடக்குவது எப்படி?",
    lang: "ta",
    font: "var(--f-ta)",
    fontSize: "17px",
  },
  {
    tag: "Thanglish",
    query: "sinam adakkuvadhu eppadi",
    lang: "en",
    font: "var(--f-mono)",
    fontSize: "13.5px",
  },
  {
    tag: "EN",
    query: "Is it ever right to lie to protect someone?",
    lang: "en",
    font: "var(--f-text)",
    fontSize: "15.5px",
  },
];

/** The shortest the thinking screen is allowed to be, so it is legible. */
const MINIMUM_THINKING_MS = 900;

export function SearchExperience({
  engine,
  corpusSize,
  initialResponse,
  initialPhase,
  initialQuery,
  isDemo,
}: SearchExperienceProps) {
  const [phase, setPhase] = useState<Phase>(initialPhase);
  const [query, setQuery] = useState(
    initialResponse?.retrieval.query ?? initialQuery,
  );
  const [response, setResponse] = useState<SearchResponse | null>(initialResponse);
  const [openPanels, setOpenPanels] = useState<Record<number, boolean>>({});
  const [arrivedAt, setArrivedAt] = useState(0);
  const [scoreProgress, setScoreProgress] = useState(initialResponse ? 1 : 0);
  const [step, setStep] = useState(0);
  const [reducedMotion, setReducedMotion] = useState(false);

  const cardRefs = useRef<Record<number, HTMLLIElement | null>>({});
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const rafId = useRef<number | null>(null);
  const scrollRafId = useRef<number | null>(null);

  // ------------------------------------------------------------------
  // motion preference, and cleaning up after ourselves
  // ------------------------------------------------------------------

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReducedMotion(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  const clearTimers = useCallback(() => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
    if (rafId.current !== null) cancelAnimationFrame(rafId.current);
    if (scrollRafId.current !== null) cancelAnimationFrame(scrollRafId.current);
    rafId.current = null;
    scrollRafId.current = null;
  }, []);

  useEffect(() => clearTimers, [clearTimers]);

  const later = useCallback((ms: number, run: () => void) => {
    timers.current.push(setTimeout(run, ms));
  }, []);

  // ------------------------------------------------------------------
  // the score count-up: bars grow from nothing so the ranking assembles
  // ------------------------------------------------------------------

  const countUp = useCallback(() => {
    if (reducedMotion) {
      setScoreProgress(1);
      return;
    }
    const startedAt = performance.now();
    const durationMs = 900;
    const tick = () => {
      const progress = Math.min(1, (performance.now() - startedAt) / durationMs);
      setScoreProgress(1 - Math.pow(1 - progress, 3));
      if (progress < 1) rafId.current = requestAnimationFrame(tick);
    };
    rafId.current = requestAnimationFrame(tick);
  }, [reducedMotion]);

  // ------------------------------------------------------------------
  // running a search
  // ------------------------------------------------------------------

  const runSearch = useCallback(
    async (rawQuery: string) => {
      const trimmed = rawQuery.trim();
      if (!trimmed) return;

      clearTimers();
      setQuery(trimmed);
      setResponse(null);
      setOpenPanels({});
      setArrivedAt(0);
      setScoreProgress(0);
      setStep(0);
      setPhase("thinking");

      [
        [360, 1],
        [880, 2],
        [1420, 3],
      ].forEach(([delay, stepIndex]) => later(delay, () => setStep(stepIndex)));

      const startedAt = performance.now();

      try {
        const request = await fetch(
          `/api/search?q=${encodeURIComponent(trimmed)}`,
          { cache: "no-store" },
        );
        if (!request.ok) throw new Error(`search failed: ${request.status}`);
        const payload = (await request.json()) as SearchResponse;

        // never flash the thinking screen — if the search was instant, hold
        const elapsed = performance.now() - startedAt;
        const wait = Math.max(0, MINIMUM_THINKING_MS - elapsed);

        later(wait, () => {
          setResponse(payload);
          setStep(4);
          setPhase("answer");
          countUp();
        });
      } catch {
        later(400, () => setPhase("error"));
      }
    },
    [clearTimers, countUp, later],
  );

  const reset = useCallback(() => {
    clearTimers();
    setPhase("rest");
    setQuery("");
    setResponse(null);
    setOpenPanels({});
    setArrivedAt(0);
  }, [clearTimers]);

  // A question can arrive already written, from "ask about this chapter" or
  // from a shared link. Run it once, on arrival, and never again.
  const hasRunInitialQuery = useRef(false);
  useEffect(() => {
    if (hasRunInitialQuery.current) return;
    if (!initialQuery || initialResponse) return;
    hasRunInitialQuery.current = true;
    runSearch(initialQuery);
  }, [initialQuery, initialResponse, runSearch]);

  // ------------------------------------------------------------------
  // following a citation down to the verse it came from
  // ------------------------------------------------------------------

  const scrollToY = useCallback(
    (targetY: number) => {
      const doc = document.scrollingElement ?? document.documentElement;
      const maximum = Math.max(0, doc.scrollHeight - doc.clientHeight);
      const destination = Math.max(0, Math.min(maximum, targetY));

      if (reducedMotion) {
        window.scrollTo(0, destination);
        return;
      }

      const from = window.scrollY || 0;
      const distance = destination - from;
      if (Math.abs(distance) < 2) return;

      const durationMs = Math.min(760, Math.max(320, Math.abs(distance) * 0.55));
      const startedAt = performance.now();
      const ease = (progress: number) => 1 - Math.pow(1 - progress, 4);

      if (scrollRafId.current !== null) cancelAnimationFrame(scrollRafId.current);
      const tick = () => {
        const progress = Math.min(1, (performance.now() - startedAt) / durationMs);
        window.scrollTo(0, from + distance * ease(progress));
        if (progress < 1) scrollRafId.current = requestAnimationFrame(tick);
      };
      scrollRafId.current = requestAnimationFrame(tick);
    },
    [reducedMotion],
  );

  const followCitation = useCallback(
    (kuralNumber: number) => {
      setArrivedAt(kuralNumber);
      const element = cardRefs.current[kuralNumber];
      if (element) {
        scrollToY(element.getBoundingClientRect().top + window.scrollY - 96);
      }
      later(2600, () => setArrivedAt(0));
    },
    [later, scrollToY],
  );

  // ------------------------------------------------------------------
  // what to show
  // ------------------------------------------------------------------

  const retrieval = response?.retrieval;
  const answer = response?.answer ?? null;
  const queryIsTamil = retrieval?.queryLanguage === "ta";

  const thinkingSteps = [
    { label: "reading the query", meta: "script detected" },
    { label: `scanning ${corpusSize} verses`, meta: "exhaustive" },
    { label: "ranking by rare-word weight", meta: "idf weighted" },
    {
      label: engine.calibrated
        ? "checking the result against the floor"
        : "reporting what was found, without judging it",
      meta: engine.calibrated ? `floor ${engine.floor.toFixed(2)}` : "uncalibrated",
    },
  ];

  const notices: Notice[] = [];

  if (retrieval) {
    if (isDemo) {
      notices.push({
        kind: "Demo state",
        meta: "not a real search",
        text: "This screen is sample copy written for the design, kept so every state can be looked at. No question was asked and no answer was generated. Type a question above to see what the retriever actually returns.",
      });
    }

    if (retrieval.confidence === "none") {
      notices.push({
        kind: "Nothing matched",
        meta: `top score ${retrieval.topScore.toFixed(2)}`,
        text: `No verse in the ${corpusSize} shared a single word with this question, so nothing is listed. This is the only case the current retriever can be sure about.`,
      });
    } else if (!engine.calibrated && !isDemo) {
      notices.push({
        kind: "Scores are not calibrated",
        meta: `top score ${retrieval.topScore.toFixed(2)}`,
        // MEASURED ON THIS ENGINE, 2026-08-02 — src/calibrate.py.
        //
        // The old text here described the WORD-OVERLAP engine, where "who won
        // the football world cup" scored 0.85. That engine is gone. Leaving
        // its number on screen under a different engine's results was the
        // exact sin this notice exists to prevent, and it sat there for a day.
        //
        // What is true now: 14 of 15 off-topic questions score exactly 0.000
        // — the failure reversed direction. But it did not go away, because a
        // real question ("how do I finish what I start") also scored 0.000.
        // So a refusal threshold anywhere above zero would turn away genuine
        // questions, and the interface still refuses nothing.
        text: "This number ranks the verses against each other, and nothing more. It cannot tell you whether the Thirukkural addresses your question. Measured on this engine: 14 of 15 off-topic questions score 0.000 — but so does at least one real question, so a cut-off would turn away questions the book does answer. Until that separation is clean the interface will not claim confidence and will not refuse on your behalf. A score of 0.00 means the verses were ranked and none stood out; read them and judge for yourself.",
      });
    } else if (retrieval.confidence === "low") {
      notices.push({
        kind: "Low confidence",
        meta: `top score ${retrieval.topScore.toFixed(2)} · marginal`,
        text: "The retrieved verses are related but not addressed to this question. Read them before relying on anything drawn from them.",
      });
    }

    if (retrieval.queryLanguage === "thanglish") {
      notices.push({
        kind: "Read as Thanglish",
        meta: "matched against the transliteration only",
        text: "Romanised Tamil is unstandardised — “sinam” and “chinam” are the same word spelled two ways, and word matching treats them as unrelated. Until the search understands meaning rather than spelling, this is the weakest of the three input languages.",
      });
    }

    if (!isDemo) {
      notices.push(
        answer
          ? {
              kind: "How this was made",
              meta: retrieval.engine,
              text: `${engine.description} The answer above was written by Sarvam-105B from these retrieved verses only. Every citation was checked against the verses actually supplied; a number the model invents is dropped rather than rendered, because a citation that leads nowhere is a lie a reader can click.`,
            }
          : {
              kind: "Retrieval only",
              meta: retrieval.engine,
              text: `${engine.description} No answer was written for this search — the generator or its provider was unavailable, or the search ran degraded — so the verses stand alone. The verses are the product; the answer is an addition.`,
            },
      );
    }
  }

  const results = retrieval?.results ?? [];

  return (
    <div className="page">
      {phase === "rest" && (
        <section className="resting">
          <div className="resting__intro">
            <div className="railhead eyebrow">
              <span lang="en">Semantic search · grounded answers</span>
              <span className="rail" aria-hidden="true" />
              <span lang="en" className="mono">
                3 · 13 · 133 · {corpusSize}
              </span>
            </div>

            <h1 className="resting__title">
              <span lang="en">Ask the Thirukkural a question.</span>
            </h1>

            <p lang="en" className="resting__lede">
              Every answer is assembled only from couplets retrieved for your
              question, and every claim carries the number of the verse it came
              from.
            </p>
          </div>

          <div className="askbox">
            <div className="askbox__field">
              <label lang="en" htmlFor="kural-question" className="eyebrow">
                Your question
              </label>

              <div className="askbox__line">
                <input
                  id="kural-question"
                  className="askbox__input"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") runSearch(query);
                  }}
                  placeholder="e.g. what does it say about restraining anger?"
                  autoComplete="off"
                  spellCheck={false}
                />
                <button
                  type="button"
                  className="button-solid askbox__submit"
                  onClick={() => runSearch(query)}
                  aria-label={`Search ${corpusSize} verses`}
                >
                  <span lang="en">Retrieve</span>
                  <span aria-hidden="true" className="mono" style={{ fontSize: 12 }}>
                    ↩
                  </span>
                </button>
              </div>

              <div className="askbox__langs">
                <span lang="en" className="askbox__lang">
                  <span className="askbox__dot" aria-hidden="true" />
                  English
                </span>
                <span className="askbox__lang">
                  <span className="askbox__dot" aria-hidden="true" />
                  <span lang="ta" style={{ fontFamily: "var(--f-ta-ui)", fontSize: 14 }}>
                    தமிழ்
                  </span>
                </span>
                <span lang="en" className="askbox__lang">
                  <span className="askbox__dot" aria-hidden="true" />
                  Thanglish{" "}
                  <span className="mono" style={{ fontSize: 11, color: "var(--ink-4)" }}>
                    sinam adakkuvadhu eppadi
                  </span>
                </span>
              </div>
            </div>

            <ExampleRow onRun={runSearch} />
          </div>

          <div className="hairline-grid stats">
            {[
              { n: "3", label: "sections", ta: "பால்" },
              { n: "13", label: "subsections", ta: "இயல்" },
              { n: "133", label: "chapters, 10 verses each", ta: "அதிகாரம்" },
              { n: String(corpusSize), label: "couplets, indexed whole", ta: "குறள்" },
            ].map((stat) => (
              <div key={stat.label} className="stat">
                <span className="stat__n">{stat.n}</span>
                <span lang="en" className="stat__label">
                  {stat.label}
                </span>
                <span lang="ta" className="stat__ta">
                  {stat.ta}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      {phase === "thinking" && (
        <ThinkingScreen
          query={query}
          queryIsTamil={/[஀-௿]/.test(query)}
          step={step}
          steps={thinkingSteps}
          reducedMotion={reducedMotion}
        />
      )}

      {phase === "error" && (
        <section className="failure">
          <span aria-hidden="true" className="failure__glyph">
            !
          </span>
          <h2 lang="en" className="failure__title">
            The retrieval service did not answer.
          </h2>
          <p lang="en" className="failure__body">
            The index is unreachable, so nothing was retrieved and nothing was
            generated. No partial answer is shown, because an ungrounded answer
            is worse than none.
          </p>
          <div className="failure__actions">
            <button
              type="button"
              className="button-solid"
              onClick={() => runSearch(query || EXAMPLE_QUERIES[0].query)}
            >
              <span lang="en">Try the query again</span>
            </button>
            <Link href="/browse" className="button-outline">
              <span lang="en">Browse the 133 chapters instead</span>
            </Link>
          </div>
          <p className="failure__trace">retrieve · 503 · index/kural-{corpusSize} · 2 retries</p>
        </section>
      )}

      {phase === "answer" && retrieval && (
        <section className="answer-screen">
          <div data-anim className="answer-head">
            <div style={{ display: "grid", gap: "var(--s3)" }}>
              <div className="railhead">
                <span lang="en" className="eyebrow">
                  Question
                </span>
                <span className="rail" aria-hidden="true" />
                <button type="button" className="button-quiet" onClick={reset}>
                  <span lang="en">New question</span>
                </button>
              </div>
              <p
                lang={queryIsTamil ? "ta" : "en"}
                className="answer-head__question"
                style={{
                  fontFamily: queryIsTamil ? "var(--f-ta)" : "var(--f-text)",
                  lineHeight: queryIsTamil ? 1.8 : 1.35,
                }}
              >
                {retrieval.query}
              </p>
            </div>

            {answer && (
              <div style={{ display: "grid", gap: "var(--s4)" }}>
                <div className="railhead">
                  <span lang="en" className="eyebrow">
                    Grounded answer
                  </span>
                  <span className="rail" aria-hidden="true" />
                </div>

                <p lang="en" className="answer__body">
                  {answer.parts.map((part, index) => (
                    <span key={index}>
                      {part.text}
                      {part.cite !== null && (
                        <button
                          type="button"
                          className="cite"
                          onClick={() => followCitation(part.cite as number)}
                          aria-label={`Go to kural ${part.cite}`}
                        >
                          ⟨{part.cite}⟩
                        </button>
                      )}
                    </span>
                  ))}
                </p>

                <div className="answer__foot">
                  <span className="answer__ground">
                    <span
                      aria-hidden="true"
                      className="answer__dot"
                      style={{
                        background:
                          retrieval.confidence === "high"
                            ? "var(--accent)"
                            : "var(--ink-4)",
                      }}
                    />
                    <span lang="en">
                      grounded in {answer.groundedIn} of {corpusSize} kurals
                    </span>
                  </span>
                  <span lang="en" className="mono" style={{ fontSize: 11.5, color: "var(--ink-4)" }}>
                    {answer.meta}
                  </span>
                </div>
              </div>
            )}
          </div>

          {results.length > 0 && (
            <div className="results">
              <div className="railhead">
                <span lang="en" className="eyebrow">
                  Retrieved verses
                </span>
                <span className="rail" aria-hidden="true" />
                <span lang="en" className="mono" style={{ fontSize: 11, color: "var(--ink-4)" }}>
                  {results.length} of {corpusSize} · ranked
                  {retrieval.elapsedMs > 0 && ` · ${retrieval.elapsedMs} ms`}
                </span>
              </div>

              <ol className="results__list">
                {results.map((result, index) => (
                  <ResultCard
                    key={result.kural.number}
                    ref={(element) => {
                      cardRefs.current[result.kural.number] = element;
                    }}
                    kural={result.kural}
                    score={result.score}
                    position={index}
                    scoreProgress={scoreProgress}
                    highConfidence={engine.highConfidence}
                    isOpen={!!openPanels[result.kural.number]}
                    onToggle={() =>
                      setOpenPanels((current) => ({
                        ...current,
                        [result.kural.number]: !current[result.kural.number],
                      }))
                    }
                    arrived={arrivedAt === result.kural.number}
                    reducedMotion={reducedMotion}
                  />
                ))}
              </ol>
            </div>
          )}

          {retrieval.confidence === "none" && (
            <div data-anim className="nomatch">
              <div style={{ display: "grid", gap: "var(--s3)" }}>
                <span lang="en" className="eyebrow">
                  Nothing retrieved
                </span>
                <p lang="en" className="nomatch__text">
                  Rather than rank five weak verses and let the wording imply an
                  answer, the result set is empty. You can ask something the text
                  does speak to:
                </p>
              </div>
              <ExampleRow onRun={runSearch} withLabel={false} />
            </div>
          )}

          {/*
            The honesty notices sit BELOW the verses, not above them.
            They used to come first, which meant three paragraphs of caveat
            stood between a person and the thing they asked for. The caveats
            are still shown in full and none has been softened — they are just
            no longer the first thing on the screen.
          */}
          {notices.length > 0 && (
            <div className="notices-foot" style={{ display: "grid", gap: "var(--s4)" }}>
              {notices.map((notice) => (
                <NoticeBlock key={notice.kind} notice={notice} />
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  );
}

function ExampleRow({
  onRun,
  withLabel = true,
}: {
  onRun: (query: string) => void;
  withLabel?: boolean;
}) {
  return (
    <div className="examples">
      {withLabel && (
        <span lang="en" className="eyebrow eyebrow--muted">
          Try
        </span>
      )}
      <div className="examples__row">
        {EXAMPLE_QUERIES.map((example) => (
          <button
            key={example.query}
            type="button"
            className="example"
            lang={example.lang}
            onClick={() => onRun(example.query)}
          >
            <span className="example__tag">{example.tag}</span>
            <span
              style={{
                fontFamily: example.font,
                fontSize: example.fontSize,
                lineHeight: 1.45,
                color: "var(--ink-2)",
              }}
            >
              {example.query}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
