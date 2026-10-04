# Kural RAG

Ask a life question in English, Tamil, or Thanglish. Get back the verses of
the **Thirukkural** that actually answer it, and a short answer that cites
those verses by number.

> *"how do I control my anger?"* → verses from chapter 31 (Restraining
> Anger), plus verse 35 from chapter 4, each shown with the Tamil original,
> translations, modern Tamil readings, and classical commentary.

The Thirukkural is a classical Tamil text of **1330 two-line verses** (each
one is a *kural*), in 133 chapters of 10, on ethics, governance, and love.
It was written about 2,000 years ago.

This is a solo learning project. The goal was to understand every part of a
retrieval system by building it by hand and measuring every change. The
working app is the side effect.

---

## What makes it hard

- **Different languages.** The question is modern English; the verse is
  classical Tamil.
- **Different words.** A reader says *"lazy"*; the 1880s English translation
  says *"sloth"*. They share no letters.
- **No invented meanings.** The answer may only use the verses it was given,
  and every citation is checked in code.

---

## How it works

```
question
   │
   ├─ Tamil script? ──yes──► searched as typed
   │
   ▼ no
1. REWRITE     Sarvam-105B turns the question into a short statement of what
               the answer would say (HyDE). Cached.
   │
   ▼
2. SCORE ALL   every one of the 1330 verses is scored, exactly — no shortcut index
   1330        score = 0.7 × meaning + 0.3 × keyword
               meaning = 0.5 × verse similarity + 0.5 × chapter similarity
               meaning: LaBSE embeddings   keyword: BM25 (written by hand)
   │
   ▼  top 50
3. RERANK      bge-reranker-v2-m3 reads question + verse together and reorders
   │
   ▼  top 5
4. ANSWER      Sarvam-105B writes 3–5 sentences from these 5 verses only.
               Any cited verse number it was not given is dropped and logged.
```

A few words, defined once:

- **Embedding** — text turned into a fixed list of numbers, so texts with
  similar meaning get similar numbers. LaBSE (768 numbers per text) puts a
  sentence and its translation close together, which is how an English
  question can find a Tamil verse.
- **BM25** — classic keyword scoring. Rare shared words count most.
- **HyDE** — rewriting a question as a guess at its answer, then searching
  with that guess.
- **Reranker** — a slower model that reads the question and one verse
  together and scores how well the verse answers it. Too slow for all 1330,
  so it only reorders the top 50.

**Exact only.** Every search compares against all 1330 verses. There is no
approximate index (FAISS was removed on purpose). Any speed-up must be shown
to change zero answers on the test set before it is allowed in.

---

## Results

Measured on 233 hand-written questions (100 in a hand-checked "golden set",
133 with one question per chapter).

How to read this table: **"right verse in top 5"** means at least one
correct verse was among the five shown. **"right verse first"** means the
very first verse shown was correct — this is what a reader feels most.
Bigger is better in both.

| | right verse in top 5 | right verse first |
|---|---|---|
| all 233 questions | **182 / 233 (78%)** | **131 / 233 (56%)** |
| 100-question golden set | **97 / 100** | 80 / 100 |

How it got there, one change at a time (golden set, right verse in top 5):

```
44  plain embedding search
52  + chapter signal
69  + delete question words like "how do I"   ← the biggest single gain
75  + keyword search (BM25)
85  + reranker
90  + hand-written chapter descriptions
93  + HyDE rewriting
97  + corpus rewritten into modern English
```

Each step was checked with a paired significance test (McNemar's exact
test). A change counts as real only when p < 0.05 — that is, luck would
produce a gap this big less than 1 time in 20. Changes that failed this bar
did not ship, and are recorded as failures.

The strongest single result: replacing the small English reranker with
`bge-reranker-v2-m3` moved "right verse first" from **105 to 131 of 233**
(p = 0.0001).

**Not yet measured or not yet good:**

- **Confidence.** Scores cannot yet tell "the book answers this" from "it
  does not". The app says so and does not pretend to be confident.
- **Citation quality.** The code proves every citation points at a verse the
  model was given. Whether the verse really supports the sentence is not
  measured yet — two AI judges disagreed on 30 of 113 claims.
- **Attacking the answer step** with wrong verses and off-topic questions —
  not done yet.
- **Thanglish and Tamil-language questions** — supported, not measured.
- **Speed.** About 16–25 seconds per new question on a laptop CPU, almost all
  of it the reranker (875 ms on a T4 GPU). Repeat questions are cached.
- **Cost.** About ₹0.005 per question (rewrite + answer).

---

## Run it locally

Needs Python 3, Node.js, and about 5 GB of free memory (all models loaded).

```bash
# Python side: retrieval service
python3 -m venv venv
venv/bin/pip install -r requirements.txt

# Web side
npm install

# Key for the rewriter and answer writer (https://dashboard.sarvam.ai/)
echo "SARVAM_API_KEY=..." > .env

# Start both processes together
./run.sh                      # opens on http://localhost:3000
```

The first start downloads LaBSE and the reranker and builds the verse
vectors, so it is slow once.

Without a key, search still works but every result is marked **degraded**
(the question is searched as typed). If the Python service is not running,
the web app falls back to simple word overlap and says so on screen.

Other commands:

| command | what it does |
|---|---|
| `npm run service` | start only the Python service (port 8000) |
| `npm run dev` | start only the web app |
| `npm run typecheck` | TypeScript check |
| `npm run logs` | read the search logs |
| `npm run audit` | check the wiring and that no key leaks |
| `venv/bin/python src/evaluate.py` | run every method on the 100 golden questions |

`RETRIEVAL_SERVICE_URL` changes where the web app looks for the service.

**Why two processes:** the models take seconds and gigabytes to load. One
long-running Python process loads them once and answers over HTTP; Next.js
only renders pages. The API key lives only in the Python process, never in
the browser or the web app.

---

## What is where

```
app/              Next.js pages: search, /browse, /kural/[number], /method
components/       search screen, verse cards, the loading animation
lib/              corpus loading, retrieval client + word-overlap fallback
service/app.py    FastAPI service: /health, /search, /generate
src/
  build_corpus.py      builds data/kurals.json from two raw sources
  audit_corpus.py      11 text checks on the corpus
  modernise_corpus.py  rewrites the old English meanings into modern English
  retrieve.py          the first version: a plain Python loop, by hand
  pipeline.py          the real retriever: embeddings + BM25 + chapters
  keyword_search.py    BM25, written by hand
  rerank.py            the reranker stage
  llm.py               one client for hosted models (Sarvam by default)
  generate.py          writes the answer and checks every citation
  evaluate.py          the scorecard, with McNemar's test
  benchmark_*.py, measure_*.py, bakeoff_*.py   one script per experiment
colab_bakeoff/    portable package that ran the reranker test on a free GPU
data/
  kurals.json                  the clean corpus: 1330 verses × 17 text fields
  modern_explanations.jsonl    the modern-English meanings
  chapter_descriptions.json    133 hand-written chapter summaries
  golden_set.json              100 hand-checked questions (the honest set)
  benchmark_questions_a.json   133 questions, one per chapter
  raw/                         the two source files
experiments/      early one-off scripts
design/           the design brief and mockup for the web app
```

---

## The corpus

Built from two public JSON sources in `data/raw/`. Joined on verse number,
never on position: one source is missing verses 395 and 648, so a join by
position would have mis-paired 934 of 1330 records.

Every verse carries: its location (section, chapter), the Tamil verse,
transliteration, three English renderings, three modern Tamil prose
readings, and two classical commentaries (Parimelazhagar and
Manakkudavar). Audits found and fixed, with notes, errors such as verse 1000
being truncated and verses 524 and 870 carrying another verse's meaning.

---

## Further reading in this repo

- [`PROJECT_UNIVERSE.md`](PROJECT_UNIVERSE.md) — the full reference: every
  experiment, every number, every mistake, and which claims are safe to make.
- [`EXPERIMENT_LOG.md`](EXPERIMENT_LOG.md) — each experiment with its exact
  results.
- [`LEARNING_LOG.md`](LEARNING_LOG.md) — what was learned, session by
  session.
- [`LEARNING_GAPS.md`](LEARNING_GAPS.md) — what I still cannot do.
- [`CLAUDE.md`](CLAUDE.md) — the teaching rules this project was built
  under.

## Status

Runs locally end to end. Not hosted yet. Next steps, in order: attack the
answer step, shrink the reranker for CPU (only if it changes zero answers),
host it, and grow the test set — the golden set is at 97 / 100, so it can no
longer show improvements.
