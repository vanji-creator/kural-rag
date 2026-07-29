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
 * The design for this page carried a full table of retrieval scores. Those
 * numbers are not here, because they have not been measured — the labelled
 * question set is a later phase. Printing a plausible 0.92 next to the word
 * "recall" would be exactly the failure this product is built to refuse, and
 * a methodology page is the worst possible place to start making things up.
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
    body: `Every one of the ${CORPUS_SIZE} verses is scored against the question and ranked. At this size there is no reason to approximate — the whole book is compared, every time.`,
    meta: "built · stand-in engine",
  },
  {
    n: "03",
    title: "Embed",
    body: "Question and verses share one multilingual vector space, so an English question can reach a Tamil verse by meaning rather than by spelling.",
    meta: "not built yet",
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

const PLANNED_METRICS = [
  { k: "recall@5", note: "does a labelled question find its gold verse in the top 5" },
  { k: "precision@5", note: "how many of the five returned verses are actually relevant" },
  { k: "MRR", note: "how far down the list the first correct verse sits" },
  { k: "citation validity", note: "share of claims traceable to a supplied verse" },
];

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

const CALIBRATION_PROBE = [
  { query: "what does it say about friendship", score: "1.00", onTopic: true },
  { query: "why should I not envy others", score: "0.86", onTopic: true },
  { query: "who won the football world cup", score: "0.85", onTopic: false },
  { query: "the greatness of rain", score: "0.81", onTopic: true },
  { query: "how do I fix a flat tyre on my bicycle", score: "0.50", onTopic: false },
  { query: "how should a king choose his ministers", score: "0.48", onTopic: true },
  { query: "what is the best language for machine learning", score: "0.37", onTopic: false },
  { query: "how do I stop being controlled by my anger", score: "0.36", onTopic: true },
  { query: "recommend a restaurant in Chennai", score: "0.31", onTopic: false },
  { query: "is it wrong to eat meat", score: "0.28", onTopic: true },
];

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
            Method · retrieval not yet evaluated
          </span>
          <h2 className="display-title">
            <span lang="en">How retrieval works, and how well.</span>
          </h2>
          <p lang="en" className="method__lede">
            {CORPUS_SIZE} verses is a small corpus, which makes exhaustive
            scoring cheap and makes the failure modes measurable. The second
            half of that sentence is not true yet: nothing on this page has
            been measured, and the numbers are missing rather than estimated.
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
              n = 0
            </span>
          </div>

          <div className="hairline-grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))" }}>
            {PLANNED_METRICS.map((metric) => (
              <div key={metric.k} className="metric">
                <span className="metric__v" style={{ color: "var(--ink-4)" }}>
                  —
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
            These are blank because the labelled question set does not exist
            yet. Roughly a hundred hand-written question-to-verse pairs come
            first; then these numbers get filled in from that set, and the
            interesting sentence — retrieval recall went from X to Y by
            changing Z — becomes possible to write. An unmeasured system with
            confident numbers on its methodology page is worse than one with
            blanks.
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
              n = 17
            </span>
          </div>

          <p lang="en" className="method__note">
            The design specified a refusal policy — answer above 0.70, show
            doubt above 0.45, refuse below. Before wiring those numbers up, ten
            questions the Thirukkural does address and seven it does not were
            run through the current engine, to find where the two groups
            separate.
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
            They did not separate. “Who won the football world cup” scored
            0.85, above all but two genuine questions, because <em>won</em>,{" "}
            <em>world</em> and <em>cup</em> each appear somewhere in the
            translations. Meanwhile a real question about eating meat scored
            0.28. No line drawn through this column puts the one group above it
            and the other below.
          </p>

          <p lang="en" className="method__note">
            That is not a bug to tune away — it is the limit of matching words
            instead of matching meaning, and it is the clearest possible
            argument for the phase that comes next. The threshold returns when
            there is a score worth thresholding.
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
