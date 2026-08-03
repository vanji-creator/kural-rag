# Where we left off — 2026-08-03, evening

Everything is stopped. Nothing is running. Safe to shut down.

Read this first when you come back.

---

## The one command to resume

```bash
venv/bin/python -u src/measure_modern_stack.py
```

That is the unfinished job. About 60 minutes, ₹0.30. Everything else is done
and committed.

---

## What this session was about

**Your hypothesis:** the English we search is 1880s English, and the embedding
model was trained on modern English, so a modern question cannot reach the
text.

We rewrote all 1330 verse meanings into plain modern English and then found
that the rest of the pipeline was still built for the old English. Fixing that
is what most of the session was.

---

## Done, and audited

### 1. The corpus has a modern version

`data/modern_explanations.jsonl` — 1330 plain-modern-English meanings.

- **1224 written by Sarvam**, ₹4.50, 7 minutes
- **106 written by me** — all 64 that GPT rejected, plus 42 more that carried
  an invented second sentence
- `data/kurals.json` is **untouched**. The old English is never deleted.
- `data/modern_explanations_v1.jsonl` is the first draft, kept for comparison

**GPT reviewed all 1330** (`data/review/gpt_review.jsonl`) and flagged 64.
Reading them against their sources, GPT was right on ~9 of the 10 I checked
closely. The pattern behind every one:

```
group    count   avg sentences   have 2+ sentences
WRONG       64            1.86              80%
OK        1266            1.15              15%
```

**Every invention lived in a second sentence.** Kural 17 gained *"This is like
how a society thrives only when its successful people contribute back to it"*,
which appears in no source. The root cause was my own prompt saying *"write 1
to 2 sentences"* while also saying *"do not interpret"*.

Fixed in two places: the instruction now says write ONE sentence and names the
openers to stop at, and `--check` detects those openers automatically. A rule
nothing checks is a wish.

### 2. The pipeline audit — what was still built for 1800s English

| # | where | status |
|---|---|---|
| 1 | `src/rerank.py` — reranker read the old prose | **FIXED** |
| 2 | `src/hyde_prompt.py` — asked for archaic words | **FIXED** |
| 3 | `src/generate.py` — answer generator reads old prose | not yet |
| 4 | chapter descriptions `modern_words` | not yet |
| 5 | `KEYWORD_WEIGHT = 0.3` swept on old text | not yet |
| 6 | `CHAPTER_BLEND_WEIGHT = 0.5` swept on old text | not yet |
| 7 | `RERANK_CANDIDATE_COUNT = 50` | not yet |
| 8 | `lib/retrieval.ts` word-overlap fallback | low priority |
| 9 | `lib/apparatus.ts` displays old translations | **leave alone** — correct |

**Item 1 was the big find.** The reranker picks the final 5 out of 50 — it
decides what a reader sees — and it read `english_explanation` directly,
ignoring the mode switch. So the first measurement (170 / 173 / 174, p = 0.66)
only ever changed stage one. **It never tested your hypothesis.**

### 3. Three prompt variants exist now

`src/hyde_prompt.py`, chosen by `PROMPT_MODE`:

- `classic` — reach for old-fashioned words (**live today**)
- `modern` — plain modern words, examples about cars/code/plumbing
- `in-domain` — plain modern words, examples from this book's world (**your
  suggestion**)

You were right about in-domain, and there was already evidence before any
numbers. My `modern` prompt drifted into self-help language:

```
Q        how do I control my anger?
classic  anger management, temperance, control of passions and wrathful impulses
modern   recognizing the trigger, pausing before reacting, choosing a calm response
```

*"Recognizing the trigger"* appears nowhere in the corpus in any version. Out-
of-domain examples told the model to be modern but gave it no idea what this
book sounds like, so it invented a register.

What I was right about — copying inflating a benchmark — is kept as a control,
not traded away:

- `src/check_prompt_leakage.py` measures all 9 example sentences against all
  233 test questions. Highest overlap **33%**, one coincidental word. PASS.
- All 9 example statements are in the copy detector.

### 4. Rate-limit handling, fixed in the right place

Sarvam rate-limits. I first put the backoff inside `modernise_corpus.py`,
which fixed one script and left every other caller exposed — and the very next
long run died on a 429 after 100 paid rewrites.

It now lives in `HostedModel.ask()` in `src/llm.py`, so every caller has it.
`measure_modern_stack.py` also saves partial results every 25 rewrites.

---

## The unfinished job

`src/measure_modern_stack.py` — six combinations, one variable at a time:

| # | corpus text | prompt | note |
|---|---|---|---|
| 1 | classic | classic | what ships today, **170/233** |
| 2 | modern | classic | control — corpus moved, question left behind |
| 3 | modern | modern | my out-of-domain examples |
| 4 | both | modern | |
| 5 | modern | in-domain | **your suggestion** |
| 6 | both | in-domain | |

Rows 3 vs 5 answer your question directly. McNemar's exact test on each row
against row 1.

**Written down in advance:** if row 1 still wins, the modern corpus does not
ship, `CORPUS_TEXT_MODE` and `PROMPT_MODE` both stay `"classic"`, and the whole
exercise is recorded as a measured negative.

The 233 modern-prompt rewrites are already cached. The in-domain ones are not
(that run is what hit the rate limit) — it will fetch them, ₹0.30, and resume
if interrupted.

---

## Rollback

```
git checkout 4ab2a81      the state before any of this corpus work
```

Or, without touching git, two switches restore the old behaviour:

```
src/pipeline.py      CORPUS_TEXT_MODE = "classic"    <- already the default
src/hyde_prompt.py   PROMPT_MODE      = "classic"    <- already the default
```

**Both are already on `classic`.** Nothing that runs today has changed
behaviour. The modern text exists but is not being used until the scorecard
says it should be.

---

## Still open from before this session

- **Phase 7 generation is not wired to the screen.** `src/generate.py` works;
  the `/answer` endpoint, web route, and frontend fetch do not exist.
- **Citation validity is unmeasured.** We proved Sarvam cannot judge its own
  answers — it marked them 92% clean and called a word-for-word quote
  "unsupported". GPT was stricter (73% clean). Your 15 hand labels were all
  the same verdict, so they cannot break the tie. The cheap way to finish it
  is to label only the ~30 claims where Sarvam and GPT disagree.
- **The app has never been deployed.** It runs locally.

---

## Quick restart

```bash
venv/bin/python -u src/measure_modern_stack.py   # the unfinished measurement
./run.sh                                          # use the app
venv/bin/python src/audit_wiring.py               # 14 key-safety checks
venv/bin/python src/check_prompt_leakage.py       # prompt examples vs test set
venv/bin/python src/modernise_corpus.py --check   # the 1330 modern meanings
```
