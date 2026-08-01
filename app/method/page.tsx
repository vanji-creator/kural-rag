import { CORPUS_SIZE } from "@/lib/corpus";
import { ACTIVE_ENGINE } from "@/lib/retrieval";

export const metadata = {
  title: "Method — Kural RAG",
  description:
    "How retrieval works here, what is measured, and what is not measured yet.",
};

/**
 * The page that says how the thing works and how well.
 *
 * The numbers below were blank until 2026-08-02, because the labelled question
 * set did not exist. It exists now — 100 hand-checked question-to-verse pairs
 * in data/golden_set.json — so the blanks are filled from measurement.
 *
 * Every figure here is reproducible in about a minute:
 *
 *     venv/bin/python src/report_metrics.py
 *
 * If a number on this page does not match that output, this page is wrong.
 * Citation validity stays blank on purpose: nothing generates answers yet, so
 * there are no citations to check.
 */

const PIPELINE = [
  {
    n: "01",
    title: "Normalise",
    body: "The script of the question is detected. Tamil, English and romanised Tamil are each matched against different fields, because word matching cannot cross an alphabet.",
    meta: "built",
  },
  {
    n: "02",
    title: "Retrieve",
    body: `Every one of the ${CORPUS_SIZE} verses is scored against the question and ranked — by meaning and by keyword, blended with a score for the chapter it belongs to. At this size there is no reason to approximate, so the whole book is compared exactly, every time.`,
    meta: "built · measured",
  },
  {
    n: "03",
    title: "Embed",
    body: "Question and verses share one multilingual vector space, so an English question can reach a Tamil verse by meaning rather than by spelling. The top 50 are then reread against the question by a second model that sees both texts together.",
    meta: "built · measured",
  },
  {
    n: "04",
    title: "Augment",
    body: "The top results are assembled into a prompt carrying couplet, explanation and commentary, each tagged with its verse number.",
    meta: "not built yet",
  },
  {
    n: "05",
    title: "Generate",
    body: "The model may assert only what a supplied verse supports, and every clause carries the number of the verse it rests on.",
    meta: "not built yet",
  },
];

/**
 * Measured by src/report_metrics.py against data/golden_set.json.
 * `v: null` means genuinely not measurable yet, and renders as a dash.
 */
const MEASURED_METRICS: { k: string; v: string | null; note: string }[] = [
  {
    k: "recall@5",
    v: "0.85",
    note: "85 of 100 questions found a correct verse in the top 5",
  },
  {
    k: "precision@5",
    v: "0.45",
    note: "2.26 of the 5 verses shown are correct, on average",
  },
  {
    k: "MRR",
    v: "0.71",
    note: "1.00 would mean the first result is always correct",
  },
  {
    k: "citation validity",
    v: null,
    note: "nothing generates answers yet, so there is nothing to check",
  },
];

const GOLDEN_SET_SIZE = 100;

const COLOUR_TOKENS = [
  { k: "--paper", v: "#F8F6F2" },
  { k: "--paper-2", v: "#FDFCFA" },
  { k: "--paper-3", v: "#F2EFE9" },
  { k: "--ink", v: "#1B1A18" },
  { k: "--ink-3", v: "#78736B" },
  { k: "--accent", v: "#9E3F24" },
];

const TYPE_TOKENS = [
  {
    k: "display / Latin",
    font: "var(--f-text)",
    size: "27px",
    lineHeight: "1.1",
    sample: "Ask the Thirukkural",
    spec: "Spectral 300 · lh 1.06 · −0.022em",
    lang: "en",
  },
  {
    k: "couplet / Tamil",
    font: "var(--f-ta)",
    size: "22px",
    lineHeight: "1.85",
    sample: "தன்னையே கொல்லும் சினம்",
    spec: "Noto Serif Tamil 400 · lh 1.85",
    lang: "ta",
  },
  {
    k: "body / Latin",
    font: "var(--f-text)",
    size: "17px",
    lineHeight: "1.64",
    sample: "Guard yourself by guarding anger.",
    spec: "Spectral 400 · 17.5px · lh 1.64",
    lang: "en",
  },
  {
    k: "prose / Tamil",
    font: "var(--f-ta)",
    size: "16px",
    lineHeight: "2",
    sample: "சினம் வராமல் காக்க வேண்டும்.",
    spec: "Noto Serif Tamil · 16.5px · lh 1.95",
    lang: "ta",
  },
  {
    k: "chrome / Latin",
    font: "var(--f-ui)",
    size: "14px",
    lineHeight: "1.5",
    sample: "Retrieved verses, ranked",
    spec: "Instrument Sans 400/500",
    lang: "en",
  },
  {
    k: "numerals",
    font: "var(--f-mono)",
    size: "15px",
    lineHeight: "1.4",
    sample: "0.87 · 1330 · 305",
    spec: "IBM Plex Mono · tabular-nums",
    lang: "en",
  },
];

const SPACE_TOKENS = [
  { k: "s1", v: "4px" },
  { k: "s2", v: "8px" },
  { k: "s3", v: "12px" },
  { k: "s4", v: "16px" },
  { k: "s5", v: "24px" },
  { k: "s6", v: "32px" },
  { k: "s7", v: "48px" },
  { k: "s8", v: "64px" },
  { k: "s9", v: "96px" },
];

const MOTION_TOKENS = [
  { k: "--d1 … --d5", v: "140 · 260 · 420 · 640 · 900ms" },
  { k: "--e-out", v: "cubic-bezier(.16,1,.3,1)" },
  { k: "--e-emph", v: "cubic-bezier(.62,.03,.1,1)" },
  { k: "--e-std", v: "cubic-bezier(.32,.72,0,1)" },
  { k: "stagger", v: "70ms · rank order" },
  { k: "reduced", v: "opacity 200ms, no travel" },
];

/**
 * Measured by src/calibrate.py on the engine running today: 20 questions the
 * Thirukkural addresses and 15 it does not.
 *
 * A representative slice, ordered by score. The rows that matter are the
 * bottom two: one off-topic question that is not quite zero, and one genuine
 * question that is.
 */
const CALIBRATION_PROBE = [
  { query: "what is the value of penance", score: "0.906", onTopic: true },
  { query: "what happens when a ruler is cruel to his people", score: "0.746", onTopic: true },
  { query: "how do I control my anger", score: "0.494", onTopic: true },
  { query: "is it better to listen than to speak", score: "0.201", onTopic: true },
  { query: "is killing animals a sin", score: "0.089", onTopic: true },
  { query: "should I check someone before becoming friends", score: "0.008", onTopic: true },
  { query: "which king won the most gold in the war", score: "0.003", onTopic: false },
  { query: "who won the football world cup", score: "0.000", onTopic: false },
  { query: "how do I install docker on ubuntu", score: "0.000", onTopic: false },
  { query: "how do I finish what I start", score: "0.000", onTopic: true },
];

const CALIBRATION_PROBE_SIZE = 35;

export default function MethodPage() {
  const policy = [
    {
      range: "planned",
      title: "Answer normally",
      body: "Show the ranked verses, and once a generator exists, write 2–4 sentences with every clause carrying a verse number.",
    },
    {
      range: "planned",
      title: "Answer with the doubt shown",
      body: "A low-confidence notice sits above the result, in the same visual weight as the result itself.",
    },
    {
      range: "planned",
      title: "Refuse",
      body: "No answer, and no ranked list either. Weak results presented as strong are the failure mode this product exists to avoid.",
    },
  ];

  return (
    <div className="page page--method">
      <section className="method">
        <div className="method__intro">
          <span lang="en" className="eyebrow">
            Method · retrieval measured, generation not built
          </span>
          <h2 className="display-title">
            <span lang="en">How retrieval works, and how well.</span>
          </h2>
          <p lang="en" className="method__lede">
            {CORPUS_SIZE} verses is a small corpus, which makes exhaustive
            scoring cheap and makes the failure modes measurable. Both halves
            of that sentence are now true: every verse is compared exactly on
            every question, and retrieval is measured against{" "}
            {GOLDEN_SET_SIZE} hand-checked question-to-verse pairs. What is
            still missing from this page is missing, not estimated.
          </p>
        </div>

        <div className="method__block">
          <div className="railhead">
            <span lang="en" className="eyebrow">
              Pipeline
            </span>
            <span className="rail" aria-hidden="true" />
          </div>

          <div className="hairline-grid pipeline">
            {PIPELINE.map((stage) => (
              <div key={stage.n} className="pipeline__stage">
                <div className="pipeline__stage-head">
                  <span className="pipeline__n">{stage.n}</span>
                  <span lang="en" className="pipeline__title">
                    {stage.title}
                  </span>
                </div>
                <p lang="en" className="pipeline__body">
                  {stage.body}
                </p>
                <span className="pipeline__meta">{stage.meta}</span>
              </div>
            ))}
          </div>

          <div className="pipeline__flow">
            <span lang="en">retrieve</span>
            <span className="pipeline__tick" aria-hidden="true" />
            <span lang="en">augment</span>
            <span className="pipeline__tick" aria-hidden="true" />
            <span lang="en">generate</span>
            <span className="rail" aria-hidden="true" />
            <span lang="en">no claim without a verse number</span>
          </div>
        </div>

        <div className="method__block">
          <div className="railhead">
            <span lang="en" className="eyebrow">
              What runs today
            </span>
            <span className="rail" aria-hidden="true" />
          </div>

          <div className="method__pending">
            <span lang="en" className="notice__kind">
              {ACTIVE_ENGINE.name}
            </span>
            <p lang="en" className="notice__text">
              {ACTIVE_ENGINE.description}
            </p>
            <p lang="en" className="notice__text">
              It finds the anger chapter when you use the word “anger”, because
              that word is in the English translation. Ask about keeping your
              temper and it finds much less, because no translation happens to
              use the word “temper”. That gap between matching words and
              matching meaning is the whole reason the next phase exists.
            </p>
          </div>
        </div>

        <div className="method__block">
          <div className="railhead">
            <span lang="en" className="eyebrow">
              Measured
            </span>
            <span className="rail" aria-hidden="true" />
            <span lang="en" className="mono" style={{ fontSize: 11, color: "var(--ink-4)" }}>
              n = {GOLDEN_SET_SIZE}
            </span>
          </div>

          <div className="hairline-grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))" }}>
            {MEASURED_METRICS.map((metric) => (
              <div key={metric.k} className="metric">
                <span
                  className="metric__v"
                  style={metric.v === null ? { color: "var(--ink-4)" } : undefined}
                >
                  {metric.v ?? "—"}
                </span>
                <span lang="en" className="metric__k">
                  {metric.k}
                </span>
                <span lang="en" className="metric__note">
                  {metric.note}
                </span>
              </div>
            ))}
          </div>

          <p lang="en" className="method__note">
            These were blank until the labelled question set existed. It exists
            now: {GOLDEN_SET_SIZE} hand-checked question-to-verse pairs, where
            a verse counts as correct if it sits in the question&rsquo;s own
            chapter <em>or</em> is one of 200 verses from other chapters that
            were read and judged to answer it anyway. Without that second
            source the scorecard would have marked a correct retrieval wrong.
          </p>

          <p lang="en" className="method__note">
            The sentence this page was waiting to be able to write:{" "}
            <strong>
              retrieval went from 44 of 100 to 85 of 100 by rewriting the
              question to its bare topic, blending in the chapter signal,
              adding keyword search alongside the embeddings, and rereading the
              top 50 with a cross-encoder.
            </strong>{" "}
            Each of those four was measured on its own, one change at a time.
            The largest single gain — 44 to 69 — came from deleting words:
            stripping &ldquo;how do I my&rdquo; from the question, because the
            model had been matching the <em>shape</em> of a question rather
            than its subject.
          </p>

          <p lang="en" className="method__note">
            Citation validity stays blank because nothing generates answers
            yet, so there are no citations to check. Every other figure here is
            reproducible with{" "}
            <span className="mono">venv/bin/python src/report_metrics.py</span>.
          </p>
        </div>

        <div className="method__block">
          <div className="railhead">
            <span lang="en" className="eyebrow">
              Refusal policy
            </span>
            <span className="rail" aria-hidden="true" />
          </div>

          <div className="hairline-grid">
            {policy.map((rule) => (
              <div key={rule.title} className="policy-row">
                <span className="policy-row__range">{rule.range}</span>
                <span className="policy-row__text">
                  <span lang="en" className="policy-row__title">
                    {rule.title}
                  </span>
                  <span lang="en" className="policy-row__body">
                    {rule.body}
                  </span>
                </span>
              </div>
            ))}
          </div>

          <p lang="en" className="method__note">
            Every range above says “planned” because the engine running today
            has no thresholds that would mean anything. Thresholds are read
            from whichever engine is active rather than written into the
            interface, and this one declares itself uncalibrated — so the
            interface neither claims confidence nor refuses on your behalf.
          </p>
        </div>

        <div className="method__block">
          <div className="railhead">
            <span lang="en" className="eyebrow">
              Why there is no threshold yet
            </span>
            <span className="rail" aria-hidden="true" />
            <span lang="en" className="mono" style={{ fontSize: 11, color: "var(--ink-4)" }}>
              n = {CALIBRATION_PROBE_SIZE}
            </span>
          </div>

          <p lang="en" className="method__note">
            The design specified a refusal policy — answer above one score,
            show doubt above another, refuse below. Before wiring any number
            up, {CALIBRATION_PROBE_SIZE} questions were run through the engine
            that ships: 20 the Thirukkural addresses and 15 it plainly does
            not. A threshold only means something if those two groups separate.
          </p>

          <div className="method__table">
            <div className="method__table-head">
              <span lang="en">Query</span>
              <span lang="en" style={{ textAlign: "right" }}>
                score
              </span>
              <span lang="en" style={{ textAlign: "right" }}>
                in the book?
              </span>
              <span />
            </div>
            {CALIBRATION_PROBE.map((probe) => (
              <div key={probe.query} className="method__table-row">
                <span lang="en" style={{ fontSize: 13.5, color: "var(--ink)" }}>
                  {probe.query}
                </span>
                <span
                  className="method__cell-num"
                  style={{ color: probe.onTopic ? "var(--ink)" : "var(--accent)" }}
                >
                  {probe.score}
                </span>
                <span
                  className="method__cell-num"
                  style={{ color: probe.onTopic ? "var(--ink-3)" : "var(--accent)" }}
                >
                  {probe.onTopic ? "yes" : "no"}
                </span>
                <span />
              </div>
            ))}
          </div>

          <p lang="en" className="method__note">
            They still do not separate — but the way they fail has reversed,
            and that is worth saying precisely. Fourteen of the fifteen
            off-topic questions scored <em>exactly</em> zero. The one that did
            not, about a king winning gold in a war, borrows three words the
            book genuinely uses. The engine this replaced put “who won the
            football world cup” at 0.85, above almost every real question.
          </p>

          <p lang="en" className="method__note">
            The overlap now comes from the other side: “how do I finish what I
            start” is a question the Thirukkural answers, and it also scored
            zero. So a floor set anywhere above 0.003 would refuse four genuine
            questions in order to catch one fake. That is a worse trade than
            refusing nothing.
          </p>

          <p lang="en" className="method__note">
            Failing this way round is the safer of the two — unhelpful rather
            than confidently wrong — but it is still a failure, so the engine
            declares itself uncalibrated and the interface does not refuse on
            your behalf. Ranking within a question is a different claim from
            knowing whether the book has anything to say, and only the first
            one is measured at {" "}
            <span className="mono">0.85</span>. The threshold returns when a
            measurement earns it.
          </p>
        </div>

        <div className="method__block">
          <div className="railhead">
            <span lang="en" className="eyebrow">
              Design system
            </span>
            <span className="rail" aria-hidden="true" />
          </div>

          <div className="tokens">
            <div className="tokens__column">
              <span lang="en" className="eyebrow eyebrow--muted eyebrow--small">
                Colour
              </span>
              {COLOUR_TOKENS.map((token) => (
                <div key={token.k} className="token-swatch">
                  <span
                    aria-hidden="true"
                    className="token-swatch__chip"
                    style={{ background: token.v }}
                  />
                  <span className="token-swatch__name">{token.k}</span>
                  <span className="token-swatch__value">{token.v}</span>
                </div>
              ))}
            </div>

            <div className="tokens__column">
              <span lang="en" className="eyebrow eyebrow--muted eyebrow--small">
                Type · Latin ↔ Tamil pairs
              </span>
              {TYPE_TOKENS.map((token) => (
                <div key={token.k} className="token-type">
                  <span className="token-swatch__value" style={{ marginLeft: 0 }}>
                    {token.k}
                  </span>
                  <span
                    lang={token.lang}
                    style={{
                      fontFamily: token.font,
                      fontSize: token.size,
                      lineHeight: token.lineHeight,
                      color: "var(--ink)",
                    }}
                  >
                    {token.sample}
                  </span>
                  <span className="token-swatch__value" style={{ marginLeft: 0 }}>
                    {token.spec}
                  </span>
                </div>
              ))}
            </div>

            <div className="tokens__column">
              <span lang="en" className="eyebrow eyebrow--muted eyebrow--small">
                Space · 4px base
              </span>
              {SPACE_TOKENS.map((token) => (
                <div key={token.k} className="token-space">
                  <span className="token-space__k">{token.k}</span>
                  <span
                    aria-hidden="true"
                    className="token-space__bar"
                    style={{ width: token.v }}
                  />
                  <span className="token-space__v">{token.v}</span>
                </div>
              ))}

              <span
                lang="en"
                className="eyebrow eyebrow--muted eyebrow--small"
                style={{ marginTop: "var(--s4)" }}
              >
                Motion
              </span>
              {MOTION_TOKENS.map((token) => (
                <div key={token.k} className="token-motion">
                  <span className="token-motion__k">{token.k}</span>
                  <span className="token-motion__v">{token.v}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
