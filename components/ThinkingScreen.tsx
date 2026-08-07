"use client";

import { useEffect, useState } from "react";

interface ThinkingScreenProps {
  query: string;
  queryIsTamil: boolean;
  reducedMotion: boolean;
}

/**
 * The pause between asking and answering — drawn as the actual pipeline.
 *
 * Every stage is real: its name, its model, its numbers. And every stage
 * carries a small schematic of its MECHANISM — not decoration, but a
 * picture of what that stage actually does to the data:
 *
 *   01  the question's filler words dim, topic words replace them
 *   02  a point is located inside the vector space of 1330 verses
 *   03  the whole corpus is swept and scored (the bars)
 *   04  1330 marks funnel down to the 50 that survive
 *   05  question and verse are read TOGETHER, pair by pair, and weighed
 *   06  answer lines are written, each ending in a citation chip
 *
 * Honesty rules: the clock is real elapsed time; the long stage (05) never
 * shows a fake percentage — it names the work and lets the clock run. The
 * schedule is shaped like this machine's measured timings, so the reader
 * sees the true shape of the work: the early stages flash past and the
 * cross-encoder is where the time goes.
 */

const CORPUS_SIZE = 1330;

/** When each stage begins, in ms of elapsed search time. */
const STAGE_STARTS_MS = [0, 1600, 3200, 5400, 7200, 20000];

const STAGES = [
  {
    index: "01",
    label: "rewriting the question as an answer",
    detail: "Sarvam-105B · HyDE",
    meta: "~0.5 s",
  },
  {
    index: "02",
    label: "turning it into 768 numbers",
    detail: "LaBSE · multilingual embedding · one point among 1330",
    meta: "768-dim",
  },
  {
    index: "03",
    label: "scoring every verse, exactly",
    detail: "meaning 0.7 · keywords 0.3 · chapter blend 0.5",
    meta: "",
  },
  {
    index: "04",
    label: "keeping the 50 best candidates",
    detail: "a reranker can only reorder what it is given",
    meta: "1330 → 50",
  },
  {
    index: "05",
    label: "rereading all 50 against your question",
    detail: "bge-reranker-v2-m3 · 568M · reads both texts together · the slow stage",
    meta: "50 pairs",
  },
  {
    index: "06",
    label: "writing the answer from the top verses only",
    detail: "every citation checked against the verses supplied",
    meta: "grounded",
  },
];

/** Deterministic pseudo-random in [0,1) — stable between renders. */
function jitter(seed: number): number {
  return ((seed * 2654435761) % 1000) / 1000;
}

// ---------------------------------------------------------------------------
// per-stage schematics (pure SVG, animated by CSS classes in globals.css)
// ---------------------------------------------------------------------------

/** 01 — filler words dim and fall away; topic words take their place. */
function VizRewrite() {
  const questionWords = [46, 22, 12, 58, 22, 48]; // "how do I control my anger"
  const fillers = new Set([0, 1, 2, 4]); // the words the rewrite discards
  const statementWords = [72, 46, 64, 40];
  let qx = 0;
  let sx = 0;
  return (
    <svg className="pipe__viz" viewBox="0 0 560 64" aria-hidden="true">
      {questionWords.map((width, index) => {
        const x = (qx += width + 10) - width - 10;
        return (
          <rect
            key={`q${index}`}
            className={fillers.has(index) ? "viz-word viz-word--drop" : "viz-word viz-word--keep"}
            x={x}
            y={8}
            width={width}
            height={11}
            style={{ animationDelay: `${300 + index * 120}ms` }}
          />
        );
      })}
      <line className="viz-hair" x1={0} y1={32} x2={330} y2={32} />
      <path className="viz-arrow" d="M 336 32 l 8 0 m -3 -3 l 3 3 l -3 3" />
      {statementWords.map((width, index) => {
        const x = (sx += width + 10) - width - 10;
        return (
          <rect
            key={`s${index}`}
            className="viz-word viz-word--new"
            x={x}
            y={44}
            width={width}
            height={11}
            style={{ animationDelay: `${900 + index * 160}ms` }}
          />
        );
      })}
    </svg>
  );
}

/** 02 — the corpus as a scatter of points; the question's vector is located. */
function VizEmbed() {
  const points = Array.from({ length: 46 }, (_, index) => ({
    x: 14 + jitter(index + 3) * 530,
    y: 8 + jitter(index + 71) * 48,
  }));
  const target = { x: 396, y: 22 };
  return (
    <svg className="pipe__viz" viewBox="0 0 560 64" aria-hidden="true">
      <line className="viz-hair" x1={0} y1={63} x2={560} y2={63} />
      <line className="viz-hair" x1={0.5} y1={0} x2={0.5} y2={64} />
      {points.map((point, index) => (
        <circle
          key={index}
          className="viz-dot"
          cx={point.x}
          cy={point.y}
          r={2.2}
          style={{ animationDelay: `${index * 12}ms` }}
        />
      ))}
      <line
        className="viz-cross viz-cross--h"
        x1={0}
        y1={target.y}
        x2={560}
        y2={target.y}
      />
      <line
        className="viz-cross viz-cross--v"
        x1={target.x}
        y1={0}
        x2={target.x}
        y2={64}
      />
      <circle className="viz-target" cx={target.x} cy={target.y} r={3} />
      <circle className="viz-ping" cx={target.x} cy={target.y} r={3} />
    </svg>
  );
}

/** 04 — the 1330 marks narrow to the 50 that survive. */
function VizFunnel() {
  const tickCount = 62;
  const survivors = new Set([4, 17, 29, 41, 55]);
  return (
    <svg className="pipe__viz" viewBox="0 0 560 64" aria-hidden="true">
      {Array.from({ length: tickCount }, (_, index) => {
        const x = 6 + index * 9;
        const kept = survivors.has(index);
        return (
          <line
            key={`t${index}`}
            className={kept ? "viz-tick viz-tick--kept" : "viz-tick"}
            x1={x}
            y1={6}
            x2={x}
            y2={20}
            style={{ animationDelay: `${index * 14}ms` }}
          />
        );
      })}
      {[...survivors].map((index, position) => {
        const fromX = 6 + index * 9;
        const toX = 236 + position * 22;
        return (
          <path
            key={`p${index}`}
            className="viz-flow"
            d={`M ${fromX} 22 C ${fromX} 40, ${toX} 34, ${toX} 46`}
            style={{ animationDelay: `${1000 + position * 90}ms` }}
          />
        );
      })}
      {[...survivors].map((index, position) => (
        <line
          key={`k${index}`}
          className="viz-tick viz-tick--landed"
          x1={236 + position * 22}
          y1={48}
          x2={236 + position * 22}
          y2={60}
          style={{ animationDelay: `${1250 + position * 90}ms` }}
        />
      ))}
    </svg>
  );
}

/** 05 — question and one verse at a time, read together and weighed. */
function VizRerank() {
  return (
    <svg className="pipe__viz" viewBox="0 0 560 64" aria-hidden="true">
      {/* the question card — fixed */}
      <rect className="viz-card" x={0.5} y={10.5} width={150} height={43} />
      <line className="viz-line" x1={10} y1={22} x2={128} y2={22} />
      <line className="viz-line" x1={10} y1={32} x2={104} y2={32} />
      <line className="viz-line" x1={10} y1={42} x2={118} y2={42} />
      {/* the verse card — swaps as pairs are read */}
      <g className="viz-swap">
        <rect className="viz-card" x={409.5} y={10.5} width={150} height={43} />
        <line className="viz-line" x1={419} y1={22} x2={545} y2={22} />
        <line className="viz-line" x1={419} y1={32} x2={519} y2={32} />
        <line className="viz-line" x1={419} y1={42} x2={533} y2={42} />
      </g>
      {/* read together: the two beams meeting in the middle */}
      <line className="viz-beam viz-beam--left" x1={156} y1={32} x2={274} y2={32} />
      <line className="viz-beam viz-beam--right" x1={404} y1={32} x2={286} y2={32} />
      {/* the weight it emits */}
      <line className="viz-hair" x1={216} y1={48} x2={344} y2={48} />
      <line className="viz-gauge" x1={216} y1={48} x2={344} y2={48} />
    </svg>
  );
}

/** 06 — answer lines written out, each closed by a citation chip. */
function VizCompose() {
  const lines = [
    { width: 470, chip: 486 },
    { width: 380, chip: 396 },
    { width: 424, chip: 440 },
  ];
  return (
    <svg className="pipe__viz" viewBox="0 0 560 64" aria-hidden="true">
      {lines.map((line, index) => (
        <g key={index}>
          <line
            className="viz-write"
            x1={0}
            y1={14 + index * 18}
            x2={line.width}
            y2={14 + index * 18}
            style={{ animationDelay: `${index * 700}ms` }}
          />
          <rect
            className="viz-chip"
            x={line.chip}
            y={8 + index * 18}
            width={30}
            height={12}
            style={{ animationDelay: `${450 + index * 700}ms` }}
          />
        </g>
      ))}
    </svg>
  );
}

// ---------------------------------------------------------------------------

export function ThinkingScreen({
  query,
  queryIsTamil,
  reducedMotion,
}: ThinkingScreenProps) {
  const [elapsedMs, setElapsedMs] = useState(0);

  useEffect(() => {
    const startedAt = performance.now();
    const interval = setInterval(() => {
      setElapsedMs(performance.now() - startedAt);
    }, 100);
    return () => clearInterval(interval);
  }, []);

  let activeStage = 0;
  for (let index = STAGE_STARTS_MS.length - 1; index >= 0; index -= 1) {
    if (elapsedMs >= STAGE_STARTS_MS[index]) {
      activeStage = index;
      break;
    }
  }

  // The scan counter climbs while stage 03 is live, then rests at 1330.
  const scanStart = STAGE_STARTS_MS[2];
  const scanEnd = STAGE_STARTS_MS[3];
  const scanProgress = Math.max(
    0,
    Math.min(1, (elapsedMs - scanStart) / (scanEnd - scanStart)),
  );
  const scannedCount = Math.round(scanProgress * CORPUS_SIZE);

  // deterministic bar heights, so nothing shifts between renders
  const bars = Array.from({ length: 76 }, (_, index) => ({
    height: 10 + ((index * 37) % 9) * 4,
    delay: index * 11,
  }));

  const seconds = (elapsedMs / 1000).toFixed(1);

  const visuals = [
    <VizRewrite key="v0" />,
    <VizEmbed key="v1" />,
    null, // stage 03 keeps its bar sweep, rendered below
    <VizFunnel key="v3" />,
    <VizRerank key="v4" />,
    <VizCompose key="v5" />,
  ];

  return (
    <section className="thinking" aria-live="polite">
      <div style={{ display: "grid", gap: "var(--s3)" }}>
        <div className="railhead">
          <span lang="en" className="eyebrow">
            Retrieving
          </span>
          <span className="rail" aria-hidden="true" />
          <span className="pipe__clock" lang="en">
            t = {seconds} s
          </span>
        </div>
        <p
          className="thinking__query"
          lang={queryIsTamil ? "ta" : "en"}
          style={{
            fontFamily: queryIsTamil ? "var(--f-ta)" : "var(--f-text)",
            lineHeight: queryIsTamil ? 1.8 : 1.45,
          }}
        >
          {query}
        </p>
      </div>

      <ol className="pipe" data-motion={reducedMotion ? "off" : "on"}>
        {STAGES.map((stage, index) => {
          const done = activeStage > index;
          const active = activeStage === index;
          const isScanStage = index === 2;

          return (
            <li
              key={stage.index}
              className="pipe__stage"
              data-state={done ? "done" : active ? "active" : "pending"}
            >
              <span className="pipe__node" aria-hidden="true" />
              <div className="pipe__body">
                <div className="pipe__row">
                  <span className="pipe__index" aria-hidden="true">
                    {stage.index}
                  </span>
                  <span lang="en" className="pipe__label">
                    {stage.label}
                  </span>
                  <span className="pipe__meta">
                    {isScanStage
                      ? `${done ? CORPUS_SIZE : scannedCount} / ${CORPUS_SIZE}`
                      : index === 4 && active
                        ? `50 pairs · ${seconds} s`
                        : stage.meta}
                  </span>
                </div>
                <span lang="en" className="pipe__detail">
                  {stage.detail}
                </span>

                {/* the stage's mechanism, drawn while it is live */}
                {active && !isScanStage && visuals[index]}

                {isScanStage && (active || done) && (
                  <div
                    className="pipe__bars"
                    aria-hidden="true"
                    data-running={active && !reducedMotion ? "yes" : "no"}
                  >
                    {bars.map((bar, barIndex) => (
                      <span
                        key={barIndex}
                        className="pipe__bar"
                        style={{
                          height: `${bar.height}px`,
                          animationDelay: `${bar.delay}ms`,
                          opacity:
                            done || barIndex / bars.length <= scanProgress
                              ? undefined
                              : 0.25,
                        }}
                      />
                    ))}
                  </div>
                )}
              </div>
            </li>
          );
        })}
      </ol>

      {reducedMotion && (
        <span className="eyebrow eyebrow--muted eyebrow--small" lang="en">
          Motion reduced at your system’s request
        </span>
      )}
    </section>
  );
}
