# Where we left off — 2026-08-02, evening

Everything is stopped. Nothing is running. Read this first when you come back.

---

## Processes that were running, and are now stopped

| what | how long it ran | why it was running | state when stopped |
|---|---|---|---|
| `uvicorn service.app:app --port 8000` | 16 min | the app you were using | stopped cleanly |
| `venv/bin/python src/evaluate.py` | 3 min | re-measuring the shipped pipeline | **KILLED BEFORE IT FINISHED** |

**The evaluation never produced a number.** That is the one loose end. It got
as far as "reranking 50 candidates x 100 questions" and was stopped there.

To finish it:

```bash
venv/bin/python -u src/evaluate.py
```

Takes about 10 minutes and uses all 8 cores. **Do not pass `--full`** — that
adds the `bge` reranker rows, which take 13 seconds per question for a
reranker we already rejected. That mistake cost 25 minutes today.

What it should say: **90 of 100** on the golden set. Every other measurement
today agrees on that number; this run is the confirmation that the wiring did
not break it, and it has not happened yet.

---

## What got built today

### 1. The question rewriter moved off the laptop and onto Sarvam

`src/rewrite_hyde.py` is now the production rewriter. `pipeline.py` calls it.

Measured on 233 questions, top-5 hit, everything else held identical:

| method | set A (100) | set B (133) | all 233 |
|---|---|---|---|
| word list, no model | 90 | 54 | 144 |
| Qwen3-1.7B on this laptop | 84 | 71 | 155 |
| **Sarvam-105B, hosted** | **90** | **80** | **170** |

- vs word list: **p = 0.0000**, settled, Sarvam is better
- vs the laptop model: **p = 0.0534**, just the wrong side of the line.
  **Not proven better.** It ships because the laptop model needs ~100 seconds
  per question on a real host and Sarvam needs 0.5.

### 2. Cost, and the guard against wasting it

₹100 of free credit. One rewrite costs about **₹0.00125**.

Every rewrite is written to `data/rewrite_cache.jsonl` and reused forever.
The cache key includes the instruction text and the model name, so changing
the instruction correctly invalidates every old entry. 233 rewrites are
already seeded, so re-running the scorecard costs nothing.

### 3. Full logging

Two files, joined by one `requestId` that travels browser → Next.js → Python:

- `logs/web.jsonl` — what arrived, what went back, the wait the reader felt
- `logs/searches.jsonl` — the rewrite, every score, stage-by-stage timing, cost

`npm run logs` reads them back. Verified working: 3 of 3 requests joined.

`logs/` is in `.gitignore` — once real people use it, that file holds their
questions.

### 4. One command starts everything

```bash
./run.sh          # or npm run stack
```

Starts the Python service, **waits until it is genuinely ready**, then starts
Next.js, and stops both together on Ctrl-C.

### 5. Key safety, audited

`venv/bin/python src/audit_wiring.py` — 14 checks, all passing. Key not in
git, not in history, not in the cache, not in `/health`, scrubbed from error
messages, `.env` ignored.

---

## What is half-built and needs you

### Phase 7 — the written answer. STARTED TONIGHT, NOT FINISHED.

`src/generate.py` exists and works. It takes the 5 retrieved verses, sends
them to Sarvam, and gets back an answer. Cost about **₹0.004** each.

**It is not wired to the screen yet.** These do not exist:

- an `/answer` endpoint in `service/app.py`
- `app/api/answer/route.ts`
- the fetch in `components/SearchExperience.tsx`

**And it already failed in an interesting way.** First run, this came back:

> To control your anger, you must restrain it, especially when it is directed
> at those who cannot fight back. Anger can harm you more than anyone else...

Correct, readable, drawn only from the given verses — and it **cited nothing**.
`groundedIn: 0`. The model obeyed "use only these verses" and ignored "cite
them". I added a format example to the instruction and did not get to test it.

**This is the Phase 7 lesson and it is yours to do, not mine.** `CLAUDE.md`
says: *"Deliberately test hallucination; show me how grounding fails and how
to tighten it."* The machinery to see the failure is built —
`check_citations()` reports exactly which numbers were invented — but no
decision about how strict to be has been made. Do not let me make it for you.

---

## Two things on screen that are worth knowing

**The notice boxes moved to the bottom.** They used to sit between you and
your results. Nothing was softened.

**One of them was lying and is now fixed.** It claimed *"who won the football
world cup scores 0.85"* — that was the old word-overlap engine, deleted today.
On the current engine that question scores **0.000**. A dead engine's number
was displayed under a live engine's results for a full day.

**Your screenshot caught a real problem.** "how to control crying" scored
**0.00** — a genuine question given zero. Same failure as "how do I finish
what I start". This is exactly why there is still no refusal threshold: any
cut-off above zero would have thrown your question away.

---

## Uncommitted

Nothing has been committed today. `git status` shows about 25 changed and new
files. They are all listed by `git status --short`.

---

## The shortest possible restart

```bash
venv/bin/python -u src/evaluate.py     # finish the measurement (10 min)
./run.sh                                # use the app
npm run logs                            # see what happened
venv/bin/python src/audit_wiring.py     # prove the key is still safe
```
