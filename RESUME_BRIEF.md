# Kural RAG — project brief for a resume

Paste this whole file to Claude and say: *"Add this project to my resume."*

Everything below is a measured fact from this repository. Nothing is rounded
up, and the two things that are **not yet true** are marked as such at the
bottom — do not let them into the resume until they are.

---

## One line

A cross-lingual retrieval system that answers plain-English questions from the
Thirukkural, a 2,000-year-old Tamil text of 1,330 verses, and cites the
specific verses behind every claim.

## Two lines

Ask *"how do I control my anger?"* in English and it retrieves the relevant
classical Tamil verses, ranks them, and writes a short answer with a citation
after every sentence. Retrieval accuracy went from **44 to 90 out of 100** on
a hand-labelled question set, one measured change at a time.

---

## The problem, stated honestly

The verses are in classical Tamil. The English translations are 19th-century
verse. A person asks *"my uncle has money and will not spend it on anyone"*;
the book says **avarice** and **miserliness**. The two share no words. Plain
keyword search finds nothing, and plain meaning-search finds the wrong things
for a reason that took a week to diagnose.

Three hard parts, all real:

1. **Cross-lingual retrieval** — an English question has to find a Tamil verse.
2. **Vocabulary gap** — modern everyday words versus archaic translation words.
3. **Strict grounding** — the system must never invent an interpretation of a
   sacred text.

---

## Measured results — the part that matters

**Retrieval accuracy on a 100-question hand-labelled set** (a "hit" = at least
one correct verse in the top 5):

| change | score | what it did |
|---|---|---|
| plain embedding search | 44 / 100 | the starting point |
| + rewrite the question | 69 | biggest single gain |
| + blend in the chapter signal (weight 0.5) | 72 | |
| + BM25 keyword search alongside (weight 0.3) | 75 | |
| + cross-encoder rerank of the top 50 | 85 | |
| + 133 hand-written chapter descriptions | **90** | |

Each row was measured on its own. **This more than doubled retrieval
accuracy — a 105% relative improvement.**

**A second, wider set of 233 questions**, used to choose the question rewriter.
Everything else held identical; only the rewrite changed:

| rewriter | score | note |
|---|---|---|
| rule-based word list | 144 / 233 | free, no model |
| Qwen3-1.7B, run locally on CPU | 155 / 233 | 5.1 s per question |
| **Sarvam-105B via API** | **170 / 233** | 0.5 s, ₹0.00125 per question |

**Statistical significance was tested, not assumed.** McNemar's exact test:
the hosted rewriter beats the rule-based one at **p = 0.0000**. Against the
local model it scored 15 higher but at **p = 0.0534** — just outside the 0.05
threshold — so that claim was *not* made.

**Ceiling analysis.** When stage one hands 50 candidates to the reranker, only
94 of the 100 questions have a correct verse in that pile at all. 90 of a
reachable 94 means the remaining headroom is in stage one, not in ranking.

**Performance and cost:**

| | |
|---|---|
| end-to-end latency | ~1.5 s (rewrite 0.5 s · search 0.2 s · rerank 1.2 s) |
| corpus scanned per query | all 1,330 verses, exhaustively, no approximation |
| cost per query | ~₹0.005 (about US$0.00005) |
| cost reduction vs. the obvious default | **130× cheaper**, chosen by measurement |

---

## Architecture

```
browser
  │
  ▼
Next.js 15 / React / TypeScript          rendering, API routes, structured logging
  │  HTTP + shared request id
  ▼
FastAPI (Python)                          long-running, models loaded once
  │
  ├─ HyDE query rewriter ──► Sarvam-105B API   question → the book's vocabulary
  ├─ LaBSE embeddings (768-dim)                exhaustive scan of all 1,330 verses
  ├─ BM25 keyword index                        implemented from scratch
  ├─ chapter-level signal blend                133 hand-written descriptions
  └─ cross-encoder reranker                    rereads the top 50 against the question
```

Two processes on purpose: the embedding models take seconds and ~1 GB to load,
so they live in a long-running service rather than loading per request.

---

## Techniques implemented

- **HyDE (Hypothetical Document Embeddings)** — rewrite the question into the
  shape of an *answer* before searching. Diagnosed from a concrete failure: one
  verse about eating meat was answering 26 of 100 questions purely because it
  is *phrased* as a question.
- **Hybrid retrieval** — dense embeddings + BM25, per-query min-max normalised
  before combining (cosine runs 0–0.5, BM25 runs 0–20; added raw, BM25 drowns
  the embeddings out).
- **BM25 built from scratch** — rare-word weighting, term-frequency saturation,
  document-length penalty, all derived before any library was used.
- **Cross-encoder reranking** — bi-encoder for the exhaustive first pass, then a
  cross-encoder that reads question and verse *together* over the top 50.
- **Document expansion** — 133 hand-written chapter descriptions that inject
  vocabulary the source text never contains (the chapter on *Unsluggishness*
  never says "lazy").
- **Reciprocal Rank Fusion**, evaluated against weighted blending.
- **Exhaustive exact search** — approximate nearest-neighbour indexing was
  explicitly evaluated and rejected: at 1,330 documents an exact scan is 4 ms,
  and accuracy is the product.

## Evaluation and rigour

- **233 hand-labelled question→verse pairs** built as the primary artifact,
  before optimisation began.
- **recall@5, precision@5, MRR** measured and published in-app.
- **McNemar's exact test** on every paired comparison — improvements that
  failed significance were not claimed.
- **Three separate data-leakage incidents found and corrected**, including 121
  verbatim test questions that had leaked into a data file, which invalidated
  a 97/100 result.
- **Improvements rejected on evidence:** a multilingual reranker that gained
  +6 points for 24× the latency; a chapter weight that scored best on a biased
  test and *worse than nothing* on an honest one.
- **Silent-failure defences** after four separate incidents where a library
  returned wrong results with no error — cache fingerprinting, empty-response
  guards, degraded-mode labelling that reaches the user interface.

## Production engineering

- **Structured JSONL logging across both services**, joined by a request id
  that travels browser → Next.js → Python, with per-stage timing breakdown.
- **Persistent rewrite cache** keyed by prompt + model, so a prompt change
  correctly invalidates it. Repeat queries cost zero.
- **Circuit breaker** on the external API — three consecutive failures pause
  calls for 60 s; search degrades to un-rewritten queries rather than failing.
- **Degradation is visible to the user** — a search running without the
  rewriter says so on screen instead of quietly serving worse results.
- **Secret handling audited** — 14 automated checks covering git history, log
  files, error messages, and the health endpoint.
- **Calibration measured and honestly reported** — the confidence scores were
  tested and found *not* calibrated, so the interface is forbidden from
  refusing or claiming confidence. This is stated in the product itself.

---

## Tech stack

**ML / retrieval:** Python, sentence-transformers, LaBSE, HuggingFace
transformers, cross-encoder reranking, NumPy, BM25, HyDE, Sarvam-105B API,
llama.cpp (evaluated), Qwen3 (evaluated)

**Backend:** FastAPI, Uvicorn

**Frontend:** Next.js 15, React, TypeScript

**Practices:** evaluation harnesses, statistical significance testing,
structured logging, distributed request tracing, graceful degradation,
secret-handling audits

---

## Suggested resume bullets

Pick three or four. They are ordered by strength.

- Built a cross-lingual retrieval system over 1,330 classical Tamil verses that
  answers English questions with verse-level citations; **improved retrieval
  accuracy from 44 to 90 out of 100** on a hand-labelled evaluation set through
  six independently measured changes.

- Designed and hand-labelled a **233-question evaluation harness** before
  optimising, then validated every improvement with **McNemar's exact test** —
  and declined to claim a 15-point gain that landed at p = 0.0534.

- Implemented **hybrid retrieval** combining dense embeddings (LaBSE) with a
  from-scratch BM25 index and cross-encoder reranking, plus **HyDE** query
  rewriting that closed the vocabulary gap between modern English questions and
  19th-century translations.

- Cut per-query LLM cost **130×** by benchmarking four providers on the project's
  own scorecard rather than defaulting to the best-known model; final cost
  ~₹0.005 (US$0.00005) per query at ~1.5 s latency.

- Found and corrected **three data-leakage incidents** in the evaluation
  pipeline, including 121 test questions that had leaked into a training data
  file and inflated a result to 97/100.

- Built **structured logging with distributed request tracing** across a
  Next.js frontend and FastAPI retrieval service, including per-stage latency
  breakdown, cost tracking, and a circuit breaker with user-visible degraded
  mode.

## One-paragraph version

> **Kural RAG** — Retrieval-augmented generation over the Thirukkural, 1,330
> classical Tamil verses. Answers plain-English questions with citations to the
> specific verses used. Built a 233-question hand-labelled evaluation harness
> first, then improved retrieval accuracy from 44 to 90 out of 100 through six
> independently measured changes: HyDE query rewriting, hybrid dense + BM25
> retrieval, chapter-level signal blending, cross-encoder reranking, and 133
> hand-written chapter descriptions for vocabulary expansion. Every improvement
> validated with McNemar's exact test. ~1.5 s end-to-end at ~US$0.00005 per
> query. Next.js / TypeScript frontend, FastAPI retrieval service, structured
> logging with distributed request tracing.

---

## NOT YET TRUE — finish these before the resume goes out

Two things in this brief describe the finished system, and are not done today.
Both are small.

1. **The generated answer is not wired to the screen.** `src/generate.py`
   works and produces correct answers from the retrieved verses, but the
   `/answer` endpoint, the web route, and the frontend fetch do not exist.
   The app currently shows ranked verses with no written answer.

2. **Citation validity is not measured.** The metric is displayed as blank
   in-app. The first generation run produced a correct answer that cited
   **nothing** — `groundedIn: 0`. Until citation accuracy is measured on the
   233-question set, do not put a citation number on the resume.

Also true and worth knowing: **the app has never been deployed.** It runs
locally. "Deployed on Vercel" is not yet a claim you can make.

Until those are closed, the honest framing is *"retrieval system with
generation in progress"* — which is still a strong project, because the
retrieval work and the evaluation rigour are the hard parts and they are done.
