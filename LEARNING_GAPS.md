# Learning gaps — Vikash

**Goal: ML/AI engineer in 12–18 months.**

This file is the honest tracker. `LEARNING_LOG.md` records what the project
did; this records **what I can and cannot do yet**, and what to fix next.

It is only useful if it is uncomfortable. Nothing here is flattery, and every
claim points at a moment in this repo where the thing actually happened.

**Maintained by Claude.** Updated at the end of every session: new gaps found,
gaps closed, evidence added. Never edited to look better.

---

## Confirmed strengths — demonstrated, not assumed

These are not "he says he can". Each one happened.

**Challenging an unmeasured claim.** 2026-08-01. I said score squashing was
caused by sentence length. Response: *"but what do u mean because of the
sentence length"*. It was a hypothesis stated as fact, and it turned out to be
wrong (corpus-side length correlation was −0.011 to −0.049, i.e. nothing).
**This is the single most valuable research instinct there is.**

**Rejecting a result that would not transfer.** 2026-08-02. LLM-written query
rewrites scored 97/100. Response: *"thats cheating, u r the best llm in world,
i wont get u in production"*. Correct on two counts — the rewrites leaked chapter
titles, AND the number measured a frontier model nobody would deploy. Knowing
that **a measurement which cannot transfer to what you ship is not a
measurement** is senior-level judgment.

**Cost/benefit discipline.** Rejected the multilingual reranker at +6 points
for 24× the latency without hesitation.

**Thinking about failure modes before building.** Asked *"what if a great kural
from bad chapter gets lost because of our mechanism"* — before the chapter
blend existed. That question is why the design filters nothing and only
penalises.

**Scope discipline.** Caught me drifting into future-phase tuning: *"idk are we
trying to solve future problems too early"*. Correct, and I conceded.

**Setting a quality bar and holding it.** Deleted FAISS from the project rather
than accept approximate search: full accuracy over speed, written into
CLAUDE.md §3.5 as a standing rule.

---

## GAP 1 — Statistics: "is this difference real?"

**Severity: high. This is the biggest gap right now.**

We have compared roughly twenty methods on 100 questions and never once asked
whether a difference was real or noise.

Measured today, on our own numbers:

```
95% confidence interval, n = 100
  44/100  ->  0.44 ± 9.7 points
  85/100  ->  0.85 ± 7.0 points
```

Treated as independent samples, several of our conclusions collapse:

```
44 vs 52   z = 1.13   NOT significant
75 vs 85   z = 1.77   NOT significant
85 vs 91   z = 1.31   NOT significant
```

**But that is the wrong test**, and knowing why is the actual lesson. Our
comparisons are *paired* — the same 100 questions, two methods. The correct
test is **McNemar's**, which looks only at the questions where the two methods
disagree. Run properly:

```
baseline 44   -> blend 52            b= 2 c=10   p=0.039   REAL
blend 52      -> rewrite+hybrid 75   b= 3 c=26   p=0.000   REAL
rewrite 75    -> PIPELINE 85         b= 1 c=11   p=0.006   REAL
baseline 44   -> PIPELINE 85         b= 1 c=42   p=0.000   REAL
```

Every step survives. Going from baseline to blend, only 2 questions got worse
while 10 got better — that asymmetry is the signal, and the aggregate score
throws it away.

**What to learn:** confidence intervals on a proportion; paired vs unpaired
comparison; McNemar's test; why n=100 is small; bootstrap resampling.

**How to close it:** add a significance column to `evaluate.py` so no future
change gets accepted on a difference that could be noise. Half a day.

**Why it matters for the career:** "we improved recall by 2%" with n=100 is a
claim that will be challenged in any serious interview or review. Knowing which
test applies, and that the paired one is stronger, is table stakes.

---

## GAP 2 — Spotting data leakage without help

**Severity: high.**

Leakage appeared **twice** in this project and I caught it both times:

1. `CHAPTER name only` scored 0.992 because the question string *was* the
   corpus string.
2. LLM rewrites scored 97/100 because I had the chapter list in context and
   wrote "restraining anger" — the correct chapter's exact title.

The second one *was* caught independently — the objection was "you're too good
a model", which is a different and also valid reason. But the mechanical form
of leakage ("the answer is inside the input") has not yet been spotted unaided.

**What to learn:** the standard forms — target leakage, train/test
contamination, temporal leakage, group leakage, feature leakage from
preprocessing done before the split.

**How to close it:** before every experiment, ask one question — *could the
answer have reached the input by any path?* Also revisit LinkGuard: were URLs
from the same domain split across train and test? If so, that was group
leakage and its metrics were optimistic.

---

## GAP 3 — Intuition for how good these systems actually are

**Severity: medium. Closes by itself with exposure.**

Predicted the baseline retriever would get *"at least 1 correct out of 5"* for
most questions. Actual: **44 of 100**. The gap between expectation and reality
was large.

This is normal at this stage and is exactly what predict-before-run is for. It
matters because an engineer who cannot estimate "is 0.85 good here?" cannot
tell when to stop optimising or when something is silently broken.

**How to close it:** keep predicting before every run, out loud, and record
when wrong. Read published baselines for standard retrieval benchmarks so
there is a reference scale.

---

## GAP 4 — Training a model end to end

**Severity: medium now, high for the career goal.**

Everything in this project uses **pre-trained** models. Nothing has been
trained or fine-tuned. LinkGuard trained a classifier, so the loop is not
totally unfamiliar, but transformer fine-tuning has not been touched.

Deliberately out of scope for Kural RAG v1 (CLAUDE.md §5), and that is the
right call — but it cannot stay out of scope for the 12–18 month goal.

**What to learn, in order:** fine-tuning a small cross-encoder on our own
golden set; loss functions and why the choice matters; overfitting on 100
examples; learning rate and batch size as things with consequences.

**Natural next step for this repo:** we have 100 labelled questions. Fine-tuning
the reranker on them is a real, small, measurable experiment — and the
scorecard already exists to judge it. It is also a perfect lesson in
train/test discipline, because using all 100 to train and then evaluating on
those same 100 would be exactly GAP 2.

---

## GAP 5 — Reading the failure cases

**Severity: medium.**

15 of 100 questions still fail and **none of them have been read**. One is
unreachable at any cutoff, which usually means the golden entry itself is
wrong.

Error analysis — sitting with the failures until a pattern appears — is where
most real ML improvement comes from, and it is the step most often skipped
because it is slow and unglamorous.

**How to close it:** read all 15. Sort them into buckets: bad golden entry,
genuinely hard question, retrieval limitation. The bucket sizes tell you what
to fix.

---

## GAP 6 — Multilingual retrieval, the thing this project promised

**Severity: medium. It is a stated project goal that is not delivered.**

CLAUDE.md §2 names Tamil and Thanglish queries as core. Reality:

- the 85 is **English-only**
- Tamil questions skip the rewrite and are labelled unmeasured — never scored
- Thanglish has **no handling at all** and has never been measured
- the Parimelazhagar commentary — the only Tamil column the English does not
  duplicate — has never been fed to anything

Pre-work measured Thanglish similarity at ~0.24, which is poor, and it was
parked. It is still parked.

**What to learn:** why romanised text is hard for multilingual models
(no consistent spelling, underrepresented in training); transliteration
normalisation; script detection.

---

## GAP 7 — Production ML: serving, latency, cost

**Severity: low-medium. Started today, not finished.**

Now partly real: the pipeline runs as a service, holds models in memory, has a
measured latency (766 ms, of which ~500 is the reranker), a measured memory
footprint (~1 GB), and an honest fallback path.

Still missing: no load testing, no concurrency story, no monitoring, nothing
deployed. Quantization was researched but not done.

Existing web-dev skills carry most of this — the ML-specific parts are the
model memory profile, cold-start cost, and the fact that accuracy and latency
trade against each other in a way ordinary web services do not.

---

## Concepts genuinely covered

Not "read about" — used, measured, and explainable.

| concept | evidence |
| --- | --- |
| Embeddings | 768-dim vectors, cosine by hand, Phase 0–2 |
| Cosine similarity | derived on paper before any library call |
| Why vectors are unit length | measured: all 1330 at exactly 1.0000 |
| float32 vs float64 | disagreement of 4.33e-08 traced to `.tolist()` |
| Chunking | chapter vs kural, measured, blended at 0.5 |
| precision@k / recall@k / MRR | computed on a real golden set |
| Building a golden set | 100 questions, 200 hand-checked cross-chapter answers |
| Metric bias | chapter weight 0.8 "best" on a biased test, worse than nothing on an honest one |
| BM25 / IDF | built by hand, three ideas derived from first principles |
| Hybrid search | and why order of testing changed the verdict |
| Bi-encoder vs cross-encoder | frozen vectors vs reading both texts together |
| Reranking and its ceiling | measured at every cutoff from 5 to 200 |
| Query rewriting | the single biggest gain, 44 → 69 |
| Calibration vs ranking | measured; the answer was no, and it stayed no |
| Exact vs approximate search | chose exact, deleted FAISS |

---

## Not needed now — do not get dragged in

Per CLAUDE.md §5: backprop from scratch, calculus, transformer internals,
training a model from zero, RLHF. Short intuition answers only, then back to
the work.

---

## Changelog

- **2026-08-02** — file created. GAP 1 found by computing confidence intervals
  on our own results and discovering the question had never been asked. GAP 2
  through GAP 7 recorded from evidence across Phases 3–5.
