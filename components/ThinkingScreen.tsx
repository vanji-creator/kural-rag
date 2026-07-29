"use client";

interface ThinkingScreenProps {
  query: string;
  queryIsTamil: boolean;
  /** how many of the steps have finished */
  step: number;
  steps: { label: string; meta: string }[];
  reducedMotion: boolean;
}

/**
 * The pause between asking and answering.
 *
 * The bars are not a loading spinner dressed up — they stand for the 1330
 * verses being scanned, and the three Tamil labels underneath mark where the
 * three books fall along that width. The point is that the reader sees the
 * shape of the work: the whole book is compared, every time, because 1330 is
 * small enough that there is no reason to approximate.
 */
export function ThinkingScreen({
  query,
  queryIsTamil,
  step,
  steps,
  reducedMotion,
}: ThinkingScreenProps) {
  // deterministic heights, so nothing shifts between renders
  const bars = Array.from({ length: 76 }, (_, index) => ({
    height: 16 + ((index * 37) % 9) * 5,
    delay: index * 11,
  }));

  return (
    <section className="thinking" aria-live="polite">
      <div style={{ display: "grid", gap: "var(--s3)" }}>
        <span lang="en" className="eyebrow">
          Retrieving
        </span>
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

      <div className="scanner">
        <div className="scanner__bars" aria-hidden="true">
          {bars.map((bar, index) => (
            <span
              key={index}
              data-scan
              className="scanner__bar"
              style={{
                height: `${bar.height}px`,
                animationDelay: `${bar.delay}ms`,
              }}
            />
          ))}
        </div>
        <div className="scanner__legend" aria-hidden="true">
          <span lang="ta">அறத்துப்பால்</span>
          <span lang="ta">பொருட்பால்</span>
          <span lang="ta">காமத்துப்பால்</span>
        </div>
      </div>

      <ol className="steps">
        {steps.map((stepDefinition, index) => {
          const done = step > index;
          const active = step === index;
          return (
            <li
              key={stepDefinition.label}
              className="step"
              style={{ opacity: done ? 1 : active ? 0.85 : 0.28 }}
            >
              <span
                className="step__icon"
                style={{ color: done ? "var(--accent)" : "var(--ink-4)" }}
                aria-hidden="true"
              >
                {done ? "✓" : active ? "·" : " "}
              </span>
              <span lang="en" className="step__label">
                {stepDefinition.label}
              </span>
              <span className="step__val">{stepDefinition.meta}</span>
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
