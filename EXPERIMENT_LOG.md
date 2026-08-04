# Experiment log — the modern corpus work

Every measurement run, what it was configured with, what it said, and what it
caught. Newest last.

**Read the configuration line before the result.** Half the confusion in this
work came from comparing two numbers produced under different settings. There
are two switches and they are independent:

```
CORPUS_TEXT_MODE   src/pipeline.py       classic | modern | both
                   which English prose each verse is searched by

PROMPT_MODE        src/hyde_prompt.py    classic | modern | in-domain | chapter
                   what the query rewriter is told to produce
```

And two question sets, which are **not** equally trustworthy:

```
Set A   100 questions. Answer key = the question's own chapter PLUS 200 verses
        from other chapters, each read and judged by hand. Cannot be gamed by
        chapter-level matching.

Set B   133 questions, one per chapter. Answer key = that one chapter only.
        Any method that leans on chapter matching is rewarded by how this set
        was built, whether or not retrieval improved.
```

---

## 1. Corpus text, three ways — `src/measure_corpus_text.py`

**Config:** corpus classic/modern/both · prompt classic · reranker unchanged

| corpus text | Set A | Set B | all 233 | p vs classic |
|---|---|---|---|---|
| classic | 90 | 80 | 170 | — |
| modern | 94 | 79 | 173 | 0.66 |
| both | 92 | 82 | 174 | 0.48 |

**Verdict at the time:** nothing established.

**What it actually was: an invalid measurement.** The audit afterwards found
`src/rerank.py` read `english_explanation` directly and ignored the corpus
switch. The reranker picks the final 5 out of 50 — the step that decides what
a reader sees was reading 1880s English in all three runs. Only stage one
changed.

**Caught:** a mode switch that reached half the pipeline. Fixed by giving
`rerankable_text()` the same mode parameter.

---

## 2. Six combinations — `src/measure_modern_stack.py`

**Config:** corpus × prompt, one variable at a time · reranker now respects
the corpus mode

| corpus | prompt | Set A | Set B | all 233 |
|---|---|---|---|---|
| classic | classic | 90 | 80 | 170 |
| modern | classic | **97** | 77 | **174** |
| modern | modern | 90 | 74 | 164 |
| both | modern | 90 | 73 | 163 |
| modern | in-domain | 92 | 77 | 169 |
| both | in-domain | 93 | 73 | 166 |

Every p value against row 1 failed. Highest total was the row predicted to be
worst.

**Two predictions of mine that were wrong:**
- I expected a modern prompt to beat the archaic one. It lost by 10.
- I labelled `modern + classic prompt` the control expected to be poor. It won.

**Vikash was right** that in-domain examples beat out-of-domain ones — 169 vs
164 — and the qualitative difference was visible before any score. The
out-of-domain prompt drifted into self-help language: *"recognizing the
trigger, pausing before reacting"* for a question about anger, which appears
nowhere in the corpus in any version.

**Caught:** reporting only the 233-question total hid that Set A said +7 while
Set B said −3.

---

## 3. Chapter description content — `src/tune_modern.py --sweep chapters`

**Config:** corpus modern · prompt in-domain · tune half only (116 questions)

| chapter description | score |
|---|---|
| `topic` only | 83 |
| `topic+words` (live) | 84 |
| `all` (+ questions) | 84 |
| `glued` (10 verses concatenated) | 76 |

**Verdict:** the *content* of a chapter description is worth about 1 question
in 116. Only gluing is clearly worse.

**Caught:** `build_chapter_descriptions`'s `glued` branch is hardcoded to
`english_explanation`, so that arm tested 1880s English even in modern mode.
Third place with the same bug shape as #1.

**Consequence:** the plan to rewrite all 133 descriptions was dropped. It
improves something worth ~1 question.

---

## 4. Chapter blend weight — `src/tune_modern.py --sweep blend`

**Config:** corpus modern · prompt in-domain · tune half

| blend | score |
|---|---|
| 0.0 | 74 |
| 0.5 (live) | 84 |
| 0.7 | 89 |

Looked like the chapter signal was worth 15 points and 0.7 should ship.

**Split by question set, it collapsed:**

| blend | Set A (of 50) | Set B (of 66) |
|---|---|---|
| 0.0 | 45 | 29 |
| 0.5 | 46 | 38 |
| 0.7 | 47 | 42 |

Set A gained **2**. Set B gained **13**.

**Caught: the metric grading its own homework.** For Set B, "correct" is
defined as "in the right chapter", so telling the system to trust chapters
more must raise that score whether or not retrieval improved.
`src/pipeline.py` records this exact trap from July. It was read that morning
and repeated anyway.

The 0.7 that had been saved was reverted.

---

## 5. Modern corpus on Set A alone — `src/check_set_a.py`

**Config:** corpus classic vs modern · prompt classic · McNemar per set

| | Set A | Set B | all 233 |
|---|---|---|---|
| classic corpus | 90/100 | 80/133 | 170 |
| modern corpus | 97/100 | 77/133 | 174 |

```
Set A only   classic right/modern wrong 1,  classic wrong/modern right 8   p = 0.0391  REAL
Set B only   13 vs 10                                                     p = 0.6776  no
all 233      14 vs 18                                                     p = 0.5966  no
```

**The modern corpus works, on the set we can trust.** Reporting the 233 total
had hidden a real effect inside a biased average.

**Caveat kept on the record:** this is a subgroup examined *after* the
pre-registered test failed, and 0.0391 is just under the line. What makes it
more than fishing is that Set A was described as the better-made set in the
code long before this experiment.

**Also reported: the ceiling.** Best Set A score is 97 of 100. **Three
questions of room left.** Any future change can win at most three there, so a
real improvement and a useless one will both come back "not established". The
limit is now the test set, not the pipeline.

---

## 6. Reading the 8 questions the modern corpus fixed

**Config:** corpus classic then modern · prompt classic · the 8 questions from
run #5

Every one of the 8 was fixed the same way — the right chapter was found:

| question | old corpus returned | modern corpus found |
|---|---|---|
| why want children? | Nobility, Courtesy | **The Wealth of Children** |
| stop wanting things? | Renunciation, Fate | **Curbing of Desire** |
| leader rule through fear? | Unreal Friendship | **Absence of Terrorism** |
| stay strong when things go wrong? | Restraining Anger | **Hopefulness in Trouble** |
| are my methods clean? | Modes of Action | **Purity in Action** |
| scared of public speaking? | Evil Friendship | **Not to dread the Council** |
| point of money unshared? | Not Coveting | **Wealth without Benefaction** |
| gossip about lovers? | Recognition of the Signs | **The Announcement of the Rumour** |

All eight are plainly worded questions using everyday words where the corpus
uses formal ones: *leader/king*, *money/wealth*, *scared/dread*,
*gossiping/scandal*, *wanting things/desire*.

**Why this matters more than the p value.** A weak statistical test plus a
mechanism predicted in advance plus eight cases that all fail the same way is
stronger evidence than a p value alone. This is the answer to "how do we
choose when the tests are weak".

---

## 7. What the reranker reads — running

**Config:** corpus modern · prompt classic · reranker
`ms-marco-MiniLM-L-6-v2` · varying whether it also sees the verse couplet

**The diagnosis.** With the correct verses now reaching the top 5, they were
still not first. Rank 1 is decided by the reranker, not by the chapter blend —
the blend only chooses which 50 candidates get there.

```
question: how do I stay strong when things go wrong?

kural 301  score 0.406   shares with the question: strong, when, wrong
kural 625  score 0.016   shares: when
```

Kural 301 is about **anger**. It scored 25 times higher than the correct verse
because the archaic couplet contains *wrong* and *strong* and so does the
question. The reranker was doing word matching, not meaning matching — and
those words come from `english_translation`, which we never modernised.

**Three cases, couplet removed from the reranker's input:**

| question | with couplet | prose only |
|---|---|---|
| stay strong when things go wrong | rank 4 | **rank 1** |
| should a leader rule through fear | rank 2 | **rank 1** |
| are my methods clean | rank 4 | rank 4 |

Those three were hand-picked from known failures.

**The full measurement says the fix does not work.**

```
reranker reads      Set A hit  Set B hit   all hit    rank-1
couplet + prose        97/100     77/133   174/233   105/233
prose only             93/100     77/133   170/233   106/233

hit in top 5       10 vs 6    p = 0.45   NOT ESTABLISHED
correct at rank 1  16 vs 17   p = 1.00   NOT ESTABLISHED
```

Dropping the couplet **loses 4 on Set A** and moves rank-1 by one. It fixes 16
questions and breaks 17. `INCLUDE_COUPLET_IN_RERANK` stays `True`.

**Caught: I fell into a trap I had named in writing two messages earlier.** I
wrote that three hand-picked failing cases are the shape of evidence that had
already misled us twice that day, then proposed the fix on the strength of
them. The mechanism was real for those three cases and net neutral across 233.

**What the run was actually worth — a number this project never had:**

```
top-5 hit        174/233   75%
correct at rank 1 105/233   45%
```

In **30% of questions the right verse is in the five but not first.** Every
score quoted in this project has been the 75%. The number a reader experiences
— the first result being right — is 45%. All future work should report both.

---

## 8. Where the archaic couplet still lives

**Not an experiment — a fact found while explaining run #7.**

"Modern corpus mode" only ever replaced the PROSE. `english_translation`, the
compressed Victorian couplet, was never rewritten and is present in every
mode, in two places:

```
searchable_text   = couplet + prose(mode) + tamil_meaning    embeddings, BM25
rerankable_text   = couplet + prose(mode)                    the reranker
```

So the "modern corpus" that scored 97/100 on Set A was half modern.

Run #7 tested removing the couplet from the RERANKER only, and it did not
help. Removing it from `searchable_text` — which feeds the embeddings and
BM25 — is **untested**. BM25 is where it would matter most, because rare words
carry the most weight there and the couplets are full of them: *wrath*, *ire*,
*thraldom*.

---

## 9. The old poem in the search stage — four arms

**Config:** corpus prose modern · prompt classic · reranker reads the poem in
all four arms · varying whether the poem is in the embeddings, the keyword
index, both, or neither

The first version of this test removed the poem from both halves at once.
Vikash caught it: the same text feeds the embeddings and the keyword index, so
a single number could not say which half caused any change - and the argument
for removing it was about rare words, which is the keyword half only.

| arm | Set A hit | Set B hit | all hit | rank-1 | reachable |
|---|---|---|---|---|---|
| poem in both | 97/100 | 77/133 | 174/233 | 105/233 | 214/233 |
| poem in embeddings only | 96/100 | 77/133 | 173/233 | 111/233 | 215/233 |
| poem in keywords only | 97/100 | 75/133 | 172/233 | 105/233 | 213/233 |
| poem in neither | 95/100 | 76/133 | 171/233 | 107/233 | 214/233 |

Every p value failed. The poem stays.

**A hint, not a result:** removing the poem from the keyword half only moved
rank-1 from 105 to 111, the direction the rare-words argument predicted. 2
versus 8 disagreements, p = 0.11.

**THE FINDING THAT MATTERS — the `reachable` column**

```
correct verse reaches the 50 candidates    214/233    92%
correct verse survives into the top 5      174/233    75%
correct verse is FIRST                     105/233    45%
```

Stage one - embeddings, keyword search, chapter blend, corpus text, prompt
wording - **is at 92%**. It finds a correct verse and hands it over in 214 of
233 questions. There are 19 questions of room left in the whole of stage one.

The reranker then drops 40 of those out of the top 5, and mis-orders most of
what remains.

**The bottleneck is the reranker.** Everything measured in runs 1 through 8 -
the corpus rewrite, the prompt variants, the chapter descriptions, the chapter
blend - was stage one work. `cross-encoder/ms-marco-MiniLM-L-6-v2` is a small
6-layer model trained on English web-search snippets, it has never seen a
verse of Thirukkural, and it is the component that decides what a reader sees
first.

---

## 10. Vikash's requested settings — `src/measure_requested_settings.py`

**Config:** modern prompt + poem out of the embeddings (in keywords) + meaning
0.7 / word list 0.3, against the shipping row

| configuration | Set A | Set B | all | rank-1 |
|---|---|---|---|---|
| previous best | 97/100 | 77/133 | 174/233 | 105/233 |
| requested | 89/100 | 75/133 | 164/233 | 106/233 |

Set A: lost 9, won 1, **p = 0.0215, REAL loss.** Rolled back same day.

**Why the logic failed:** the classic prompt asks for old words ALONGSIDE
everyday ones — both vocabularies. The modern prompt carries only half. The
164 exactly matches run #2's modern-prompt row, so the poem removal cost ~0
and the prompt caused the whole drop.

---

## 11. Tickets — `src/count_tickets.py`, `src/tickets_vs_success.py`

**Config:** live pipeline, stage one only, then crossed with saved hits

A "ticket" = one correct verse inside the 50 candidates. Average 7.2 per
question; 62% of all correct verses reach the pile; the most common count is
exactly 10 — a full chapter arriving intact. Top-5 hit rate climbs with
tickets and never flattens: 0%, 45%, 59%, 76%, 85%, 92%.

**Flagged in advance:** a correlation — easy questions may be easy for both
stages. Decided nothing on its own; run #12 was the test.

---

## 12. Pile 50 vs 75 — `src/measure_candidate_count.py`

**Config:** identical stage one, only the candidate count changes

| pile | tickets | all | rank-1 | rerank ms |
|---|---|---|---|---|
| 50 | 7.2 | 174/233 | 105/233 | 540 |
| 75 | 8.2 | 165/233 | 103/233 | 861 |

**Tickets UP, score DOWN, p = 0.0352 REAL.** The intervention broke the
correlation: extra candidates are distractors this reranker falls for. The
pile stays at 50, stage-one enrichment is closed as a direction, and the
reranker is convicted — given 7 correct verses on average it still fails
rank-1 on more than half of all questions.

---

## 13. Small-reranker bake-off — `src/bakeoff_rerankers.py`

**Config:** frozen piles, four arms varying one axis each

| arm | all | rank-1 | ms |
|---|---|---|---|
| A: L6 english (ships) | 174/233 | 105/233 | 623 |
| B: L12 english (depth only) | 177/233 | 107/233 | 1267 |
| C: L12 multilingual (language only) | 168/233 | 95/233 | 1460 |
| D: C + tamil input | 176/233 | 104/233 | 2288 |

Every p failed. Directions, not results: depth is nearly worthless (+3),
same-size multilingualism costs (−9 vs B), Tamil input wins back +8 for a
model that can read it. Conclusion: the small-model family is exhausted;
the candidate must be large AND Tamil-capable.

---

## 14. bge-reranker-v2-m3 on a rented GPU — `colab_bakeoff/`

**Config:** the frozen piles and texts exported as data; Colab T4 only
reranks. Package validated first: arm E with the shipping model reproduced
arm A's saved answers with ZERO disagreements, resumed from checkpoints,
and survived kill -9.

| arm | Set A | Set B | all | rank-1 | ms (T4) |
|---|---|---|---|---|---|
| A: small, ships | 97/100 | 77/133 | 174/233 | 105/233 | 623 |
| E: bge english | 97/100 | 85/133 | 182/233 | 131/233 | 875 |
| F: bge + tamil | 97/100 | 90/133 | 187/233 | 124/233 | 1321 |

```
E vs A, rank-1   won 35, lost 9    p = 0.0001   REAL
F vs A, top-5    won 19, lost 6    p = 0.0146   REAL
F vs A, rank-1   won 35, lost 16   p = 0.0110   REAL
E vs F           not established either way
```

**The strongest result this project has produced.** E's rank-1 gain sits on
the honest set: Set A 68 → 80. F's extra top-5 sits mostly on Set B, the
chapter-biased key, so the Tamil-input question stays open until the test
set grows. **Decision: E is the chosen model, pending a serving plan** — it
needs ~20 s/question on the laptop, 875 ms on a T4.

The pre-registered rule it passed: "a clear rank-1 gain at no top-5 cost."
Rank-1 +26 while top-5 rose 8.

---

## Mistakes worth keeping

**A mode switch that reached half the pipeline.** Twice — the reranker (#1)
and the glued chapter fallback (#3). Both were invisible because they read a
field directly instead of going through the switch.

**Tuning against a biased answer key** (#4), one day after reading the note in
our own code describing the same mistake.

**Reporting an average over two disagreeing halves** (#2, #5). The average
said "no effect". One half said +7 and the other said −3.

**A speed measurement too short to see the limit it was measuring.** 16
parallel calls looked 3.2× faster on 24 kurals. Run on 1,225 it produced 783
rate-limit errors, because a rate limit is counted per minute and the test
took 30 seconds.

**A retry fixed in one script instead of the shared component.** The backoff
went into `modernise_corpus.py`; the next long run, in a different file, died
on the same error and lost 100 paid rewrites. It now lives in
`HostedModel.ask`.

**An embedding cache that existed and went unused.** `pipeline.py` had
fingerprinted vector caching from the start. Every analysis script called
`model.encode()` directly and paid three minutes per run to recompute
identical vectors.

**A save-at-the-end script, AGAIN (2026-08-04).** The first bge run kept all
scores in memory and wrote once at the end. Stopped at question ~120 for an
overheating laptop; 40 minutes of compute produced no file. The identical
lesson was already in this log ("a crash should cost the one in flight") and
did not transfer, because past bake-offs took minutes and this one took hours.
The rule that should have fired: **checkpoint by expected runtime, not by
habit.** Every long runner now checkpoints atomically every 10 questions, and
the fix was proven by kill -9.
