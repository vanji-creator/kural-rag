# LEARNING LOG — Kural RAG

Plain-English record of **what I understood**, not what I coded.

---

## 2026-07-28 — Phase 0 (Setup & orientation)

### The correction that started the session

CLAUDE.md claimed concept 2 (similarity) was "done and felt" after the
pre-work sandbox. That was not true.

I had **run** the cosine similarity code and seen it print `1.000` and `0.36`.
But I could not say where those numbers came from. Running code is not
understanding code.

So we stopped and rebuilt the concept from zero before touching Phase 0.

**Lesson to keep:** if I cannot explain a printed number, I do not know the
concept yet, no matter whose code produced it.

---

### 1. Meaning lives in direction, not distance

We used a pretend model that gives only 2 numbers per word, so it could be
drawn on paper:

```
    anger  [ 3,  1]
    rage   [ 6,  2]     = anger x 2
    fury   [30, 10]     = anger x 10
    car    [ 1,  4]
```

All three anger-words sit on **one straight line** out of the origin. Same
direction, different lengths. A stronger word is just a longer arrow.

I measured straight-line distance by hand:

```
    anger -> fury  =  root(810)  ~ 28.5
    anger -> car   =  root(13)   ~  3.61
```

Distance says **car is 8x closer to anger than fury is**. That is nonsense.

The model was fine. My **ruler** was broken.

**Lesson to keep:** before reaching for a bigger model, ask whether the
measurement is wrong. My instinct was "get a better model" and it was the
wrong instinct here. This will come back in Phase 4 when Tamil scores low.

---

### 2. I re-derived cosine similarity myself

I worked out that the right question is not "how far apart are these points"
but "how much do the two arrows agree in **direction**".

I then designed the score scale before being told it existed:

```
      0 degrees (identical)  ->   1
     90 degrees (unrelated)  ->   0
    180 degrees (opposite)   ->  -1
```

That scale turns out to be exactly `cos(angle)`. Hence the name **cosine
similarity**. I never needed any trigonometry — only multiply, add, square
root, divide.

Computed fully by hand:

```
    anger [3,1] vs rage [6,2]
      dot     = 3*6 + 1*2 = 20
      lengths = root(10) x root(40) = 20
      score   = 20 / 20 = 1.0        exactly

    anger [3,1] vs car [1,4]
      dot     = 3*1 + 1*4 = 7
      lengths = root(10) x root(17) ~ 13.038
      score   = 7 / 13.038 ~ 0.537

    anger [3,1] vs fury [30,10]
      dot     = 3*30 + 1*10 = 100
      lengths = root(10) x root(1000) = 100
      score   = 100 / 100 = 1.0      exactly
```

Same numbers, same model, different ruler — and now the answers are right.

---

### 3. Why we divide by the two lengths

The dot product grows when an arrow gets longer:

```
    anger . anger  =  10
    anger . rage   =  20     (rage is anger x 2)
    anger . fury   = 100     (fury is anger x 10)
```

So the dot product carries **direction AND length mixed together**.

Dividing by both lengths washes the length out. What survives is pure
direction. That is the entire job of the denominator.

---

### 4. Going from 2 numbers to 384 changes nothing in the maths

```
    2 numbers:    dot = a1*b1 + a2*b2
    384 numbers:  dot = a1*b1 + a2*b2 + ... + a384*b384
```

Same three steps, longer loop.

I cannot picture 384 dimensions and I should stop trying. The 2D picture was
scaffolding to build intuition; from here I trust the arithmetic.

What extra dimensions actually buy: **room**. On flat paper, unrelated
meanings get forced to point the same way because there is nowhere else to
go. 384 dimensions gives every shade of meaning its own direction.

---

### 5. Where the numbers come from (intuition only)

Nobody writes the numbers by hand. The 384 slots have **no human-readable
meaning** — slot 7 is not "angriness".

They are learned from **neighbours**: a word is defined by the words that
appear around it. "rage" sits near "control", "temper", "anger"; never near
"used car price".

Training loop, roughly:

```
    take two sentences that mean the same thing
    embed both -> two arrows
    measure the angle  <- cosine similarity
    nudge the numbers to close the gap
    push unrelated pairs apart
    repeat millions of times
```

Important: **cosine similarity is not only how I search — it is how the model
was trained.** That is why it is the correct ruler at search time.

Multilingual models are trained on the same sentence in two languages, pulled
together. **That is the whole reason an English question can find a Tamil
verse.** There is no translation step anywhere in my pipeline.

This also explains my pre-work scores, which are not bugs:
- Tamil ~0.36 — MiniLM saw far less Tamil than English, so the pull was weaker.
- Thanglish ~0.24 — almost nobody writes parallel training data in romanized
  Tamil, so there was barely any pull at all.

Deliberately parked for Phase 4/5.

---

### 6. The map of the whole pipeline

Two separate times. This was the thing LinkGuard never had.

**ONCE (slow, offline):**

```
  1330 kurals            [1]            [2]              [3]
  + meanings      -->   CLEAN   -->   CUT INTO   -->    EMBED
  + commentary          DATA          PIECES           EACH PIECE
                                                          |
                                                          v
                                                   1330 arrows saved
```

**EVERY QUESTION (fast, live):**

```
   question -> [4] EMBED IT (same model!)
                   |
                   v
               [5] COMPARE against all 1330, keep top 5
                   |
                   v
               [6] PROMPT: question + those 5 + "answer only from these"
                   |
                   v
                  LLM -> answer with kural citations
```

Mapping to phases: [1] Phase 1, [2] Phase 4, [3] Phase 2, [4] Phase 2,
[5] Phase 3 then Phase 6, [6] Phase 7.

The names: [5] **R**etrieve, [6a] **A**ugment, [6b] **G**enerate. That is all
RAG is. Frameworks are wrappers around these six boxes.

Nothing here trains a model. I use a model someone else trained and never
change it.

---

### 7. Four consequences of the map

1. **Same embedding model on both sides.** Steps 3 and 4 must match.
2. **The LLM never sees all 1330 kurals** — only the ~5 retrieved.
3. **Retrieval is the ceiling.** Bad retrieval + perfect LLM = confidently
   wrong answer. This is why Phase 5 (evaluation) is not skippable.
4. **Stopping after step 5 is already a product** — working semantic search
   over Thirukkural, no LLM needed. Phase 3 is the first real milestone.

---

### 8. Why "just send all 1330 kurals to the LLM" fails

Three reasons, strongest first:

1. **Capacity** — verses alone might fit a long-context model, but with word
   meanings and Parimelazhagar commentary it is not practical.
2. **Cost** — paid on every single question, forever.
3. **Accuracy** — burying 5 relevant kurals in 1325 irrelevant ones makes
   answers *worse*. More context is not better context.

---

### 9. The mismatched-model bug (best thing I worked out today)

If the kurals and the question are embedded by different models:

- **Different dimensions (384 vs 768)** — the pairwise multiply has nothing to
  pair with. Python crashes. **This is the lucky case.** A crash is a gift.
- **Same dimensions, different model** — no crash. Clean-looking score like
  `0.41`. Completely meaningless.

Why: the numbers start as random noise and get nudged into place. Nothing
anchors slot 7 to any idea. Two separately trained models have no reason to
agree on which direction means "anger". Each builds its own private space.

I would blame my chunking, my data, my model's Tamil — and the real bug would
be one wrong model name.

**General pattern to keep:** the bug that crashes is cheap; the bug that
returns a plausible number is expensive.

---

---

## 2026-07-29 — Phase 1 (Corpus)

### Joining data: identity, never position

Two raw sources. One has all 1330 kurals but no Parimelazhagar commentary. The
other has the commentary but is **missing kurals 395 and 648**.

I asked whether we could just map them in order, since the order is the same.
We tested it: a positional join silently mis-pairs **934 of 1330 records**,
because a hole at 395 slides everything after it up by one.

```
                thirukkural.json         all_info.json
   position         kural                    kural
      393             394                     394     ok
      394             395                     396     <-- shifted
```

**Rule:** join on identity, never on position. Same reason I use a primary key
in PostgreSQL instead of row order — I just had never applied it to a poem.

### Six defects found by a written audit

`src/audit_corpus.py` runs 11 checks and modifies nothing. It found:

1. kural 1000's first line truncated — `ண்பிலான்` instead of `பண்பிலான்`
2. 664 Manakkudavar commentaries with English text glued onto the end
3. 21 Karunanidhi meanings with the same problem
4. kurals 319, 320 running two commentators together in one field
5. kural 870 carrying kural 810's meaning
6. kural 524 carrying kural 468's meaning

**None of these crashed anything.** All 1330 records were present and populated
throughout. The only way to find them was to count and compare on purpose.

Two things that *looked* like bugs and were not: 70 English couplets starting
with an apostrophe (`'Tis rain works all`), and 18 kurals sharing an identical
second line — Valluvar genuinely reuses lines. **An audit reports; it does not
auto-fix.** A script that "deduplicated" those 18 would have destroyed real data.

### Copies are not witnesses

Kural 524 was wrong in **both** raw sources. I checked three websites: two had
the same wrong text, one had it right.

Majority vote would have "confirmed" the error 3-to-1. Those sites are not
independent — they all copy the same upstream dataset.

**Counting copies is not verification.** Every hand-sourced value in the corpus
now records how many genuinely independent sources backed it; five of nine are
single-sourced, and that is stated rather than hidden.

### Using embeddings as an audit instrument

The six defects above were found by text rules. But 524 and 870 only surfaced
because they were *exact copies* — a merely wrong meaning would have been
invisible to all 11 checks.

So we used the embedding model as a detector: embed each kural's English
explanation and its Tamil meaning, and measure the angle between them. A record
whose two arrows disagree is a record whose two texts are not saying the same
thing.

**We tested the detector before trusting it.** We planted 22 known errors — the
2 historical ones recreated, plus 20 random meaning-swaps — and measured how many
it caught.

```
                                    caught in the 22 most suspicious
   paraphrase-multilingual-MiniLM     0 / 22    (0%)     384 dims
   LaBSE                             15 / 22   (68%)     768 dims
```

MiniLM was **useless** for this. Its English-to-Tamil similarities were all
squashed near zero (median 0.098), so a wrong pair looked no different from a
right one. LaBSE separated them cleanly (median 0.575), and ranked the planted
kural 524 error **4th out of 1330**.

Two lessons:

- **A detector nobody has tested is worth nothing.** Plant known errors first
  and measure recall. This is exactly the LinkGuard evaluation habit, in a new
  setting.
- **Task fit beats size.** LaBSE was built to decide "is text A a translation of
  text B", which is precisely this question. It is not simply "bigger".

Also: the "same model on both sides" rule is about **both sides of one
comparison**, not "one model per project". The audit and retrieval are separate,
self-contained comparisons and may legitimately use different models — as long as
arrows from different models are never compared to each other.

### Low similarity is suspicion, not evidence

A low score has two possible causes: the translation is loose, or the meaning
belongs to another kural. To tell them apart, compare each Tamil meaning against
**all 1330** English explanations:

- a loose translation still matches its own kural best
- a misassigned meaning matches some other kural best

### What the embedding audit actually found

Not what I expected. **25 kurals had an `english_explanation` that was really a
slice of the poetic couplet**, not an explanation at all. Kural 1156 read
`"Is hard, when he could stand, and of departure speak to me"`. The prose
explanation was simply absent.

No text check could have seen this. Not empty, not duplicated, not mixed-script
— just the wrong content. All 25 were repaired from the alternate source, and
the build now refuses to write if an explanation is a verbatim slice of its own
couplet.

After the repair, the top remaining candidates were all false positives — loose
English translations, with the Tamil correct.

**Honest limits of the detector:** it caught 68% of planted errors at 22, and it
completely missed the historical kural 870 error (rank 398 of 1330), because the
wrong text happened to be topically similar. There may be more errors it cannot
see. Recall was measured, not assumed.

### Final corpus state

1330 records, 21 fields, every field complete. No script mixing, no label
leakage, no spurious duplicates. 133 chapters of exactly 10, 3 contiguous
sections — cross-checked against the derivable structure.

`REQUIRED_FIELDS` in the build gate went from 8 to 17. Every defect found today
is now something that stops the build rather than shipping silently.

---

### Status

- Concept 1 (embeddings) — done in pre-work.
- Concept 2 (similarity / cosine) — done 2026-07-28, derived by hand.
- Phase 0 — complete. Map understood.
- Phase 1 — **corpus complete and audited.** 1330 records, 21 fields, no holes.
- Next: **Phase 2 — embeddings over the real corpus.**

Carried into Phase 2:
- The embedding model is still undecided. MiniLM is demonstrably too weak for
  cross-lingual work on this corpus. LaBSE proved itself for translation
  equivalence; `multilingual-e5-large` and `bge-m3` are the retrieval
  candidates, to be decided by Phase 5 measurement, not by argument.
- This machine is **CPU only** (`torch.cuda.is_available()` is False).
- Parimelazhagar commentary runs up to ~1684 characters, and Tamil produces more
  tokens per character than English. Against a 512-token model limit that risks
  truncation. `bge-m3` allows 8194 — relevant if Phase 4 favours commentary.

---

## 2026-07-29 — Phase 8 (out of order): the frontend, built early

The design came back from Claude Design and I asked for it to be built now,
rather than waiting until after retrieval works. So Phase 8 landed before
Phases 2–7. The app is real: all 1330 kurals, real chapters, real commentary,
real search. What it does **not** have is embeddings, a vector database, or a
generator, because those are still ahead.

### What was actually learned

**A frontend built before the model forces an honest interface.**

Every screen the design specified had to answer the question "what do you show
when the thing behind you does not exist yet?" The answers turned out to be the
most valuable part of the build:

- The "grounded answer" block renders from data. There is no generator, so it
  simply does not appear, and a notice says why. It was tempting to write a
  plausible paragraph. That is the exact failure this product is supposed to
  prevent, and it would have been invisible once written.
- The Method page in the design carried measured numbers — recall@5 of 0.92 and
  so on. Those are Phase 5 numbers and Phase 5 has not happened. They are shown
  as blanks with an explanation. A methodology page is the worst possible place
  to start making things up.

**The measurement that changed the build.**

The design specified a refusal policy: answer above 0.70, show doubt above
0.45, refuse below. Before wiring those numbers up I ran ten questions the
Thirukkural does address, and seven it does not, through the placeholder
word-overlap retriever:

```
    on topic                                        off topic
    1.000  what does it say about friendship        0.847  who won the football world cup
    0.856  why should I not envy others             0.500  how do I fix a flat tyre
    0.809  the greatness of rain                    0.368  best language for machine learning
    0.479  how should a king choose his ministers   0.306  recommend a restaurant in Chennai
    0.363  how do I stop being controlled by anger  0.295  should I move my savings into crypto
    0.283  is it wrong to eat meat                  0.000  how do I install postgresql
```

**The two groups do not separate.** "Who won the football world cup" scored
0.847 — higher than all but two real questions — because *won*, *world* and
*cup* each appear somewhere in the translations. Meanwhile a genuine question
about eating meat scored 0.283.

There is no threshold that puts one group above it and the other below. So the
refusal policy cannot be implemented on this engine at all, and picking a
number anyway would have been decoration dressed as rigour.

What I did instead: the engine declares `calibrated: false`, and the interface
reads that flag. It refuses to claim confidence, refuses to refuse on the
reader's behalf, and shows a notice explaining the football result. When
embeddings arrive, the engine changes and the flag flips — the interface does
not change.

**Why this matters more than the UI.** This is the clearest evidence I have
produced so far for *why embeddings are needed*. Not an argument from a
tutorial — a measured failure of the alternative, on my own corpus. Word
matching cannot tell a question about the book from a question about football.
Meaning matching is supposed to be able to. Phase 5 will show whether it does.

**Retrieval is the ceiling — now visible in the product.** Search, browse and
the verse pages are all wired to one `RetrievalEngine` interface. Swapping the
placeholder for a real embedding retriever is one line (`ACTIVE_ENGINE`).
Everything else — cards, citations, thresholds, notices — reads from whatever
that engine reports about itself.

### Smaller things learned

- A single-column CSS grid sizes its track to `auto`, which is at least
  max-content. One long unbreakable Tamil line therefore widened the track,
  widened the page, and produced a horizontal scrollbar on a phone.
  `minmax(0, 1fr)` is the fix. Found by measuring, not by looking.
- Tamil needs far more line height than Latin — 1.85 to 2.1 against 1.5 to 1.7
  — because the vowel signs hang above and below the line and collide
  otherwise.
- The corpus has no empty commentaries at all, so the design's "no commentary
  survives for this verse" state is implemented but never fires. Left in place
  deliberately: the day a source changes, it will.

### Status after this session

- Phase 8 — **frontend complete and deployed-ready**, running on the real
  corpus with a placeholder retriever that is labelled as one everywhere it
  appears.
- Phases 2–7 — still ahead, unchanged. Nothing about the UI shortcuts them.
- Next is still **Phase 2 — embeddings over the real corpus**, and there is now
  a working product to plug them into and a measured baseline to beat.

---

---

## 2026-07-30 — Phase 1 close-out, and an answer to yesterday's open question

### The question Phase 8 left open

Yesterday's frontend session ended with this, unresolved:

> Word matching cannot tell a question about the book from a question about
> football. Meaning matching is supposed to be able to. Phase 5 will show
> whether it does.

Today I ran that test early, with real LaBSE embeddings instead of word overlap.

**Meaning matching does not fix it either.**

```
   word overlap (Phase 8 placeholder)
     0.847  who won the football world cup        <- garbage
     0.363  how do I stop being controlled by anger

   LaBSE embeddings (today)
     0.386  what happened during the world cup this year   <- garbage
     0.320  what does Thirukkural say about controlling anger?
```

Different engine. Same failure, same direction: **the garbage question outranks
the real one.** Switching from words to meaning changed the numbers and did not
change the verdict.

So the `calibrated: false` flag in the frontend does not flip when embeddings
arrive. That was my assumption yesterday and it was wrong.

### Why no number can fix it

Retrieval keeps the top k. It has no way to keep zero. Sort 1330 numbers and
there is always a winner, even when all 1330 are meaningless.

LaBSE did read the whole sentence — it is not matching words. It was asked
"which is nearest?" and answered correctly. It was **never asked "is any of this
relevant?"** That second question cannot be carried by a similarity score at all.

Something that **reads the text** can tell that a verse about yesterday and
today does not answer a football question. A cosine number never can. In the
pipeline that reader is the LLM in Phase 7 — which makes grounding a load-bearing
part of the design, not a finishing touch.

Pure gibberish (`asdfgh qwerty zxcvbn`) did score low at 0.173, so a threshold
catches noise. It is fluent, plausible, off-topic English that walks through.

I checked whether score-shape signals (gap between top and 5th, tightness of the
top 5) separate good queries from bad. They do not, cleanly. Candidates to
measure in Phase 5, not fixes.

### Retrieval is already visibly weak on real questions

```
   "what does Thirukkural say about controlling anger?"
     1. kural 301  0.320  He restrains his anger who restrains it when...  correct
     2. kural  57  0.291  The chief guard of a woman is her chastity...    nonsense
     3. kural  54  0.262  What is more excellent than a wife...            nonsense
```

Thirukkural has a whole chapter on anger (301–310). One of those ten came back.
This was English explanations only, one kural per chunk — exactly the chunking
choice Phase 4 exists to question.

---

### The audit detector, revisited

Yesterday's misassignment hunt ranked candidates by how much better some other
kural matched. Its number one candidate in the whole corpus, largest gap of all
1330:

```
   kural 977    own 0.116    matches kural 489 at 0.413    gap +0.297
```

I read both texts. Kural 977's English explanation and its Tamil meaning say the
same thing — high status landing on base people produces behaviour that exceeds
its bounds. Kural 489 is about seizing a rare opportunity. Unrelated.

**The strongest accusation in the run is a false positive.**

### Mismatch is not error

```
   305 of 1330 Tamil meanings match some other kural better
```

23% of a corpus I had already audited and repaired. It does not contain 305
misassigned meanings. So a mismatch does not mean an error.

The pipeline is three stages, not two:

```
   pass 1   a score               ->  suspicion
   pass 2   a ranked accusation   ->  a candidate, and a lead to check
   me       reading the text      ->  the verdict
```

Pass 2's contribution is not proof. It hands over **a specific lead** — "compare
977 against 489" — instead of a bare number I can do nothing with. It shrinks
1330 records to a list a human can read. Still a large win, just not proof.

Kural 524 was the case where the lead was real: pass 2 said "compare 524 against
468", and reading the text settled it. Same tool, opposite outcome.

### What a threshold would actually have done

I assumed a cutoff would drown me in false alarms. Measured, it does not:

```
   cutoff   flagged   mismatched   self-matched
   ──────────────────────────────────────────────
    0.20        1          1             0
    0.30       14         14             0
    0.40       74         69             5
    0.50      295        215            80
```

Only 5 kurals score below 0.40 and still match themselves. The threshold was not
the weak part. The weak part is that "mismatched" was never the same thing as
"wrong", at any cutoff.

**Lesson to keep: check the assumption before building the argument on it.**

---

### Two changes to the plan, both from my own questions

1. **The Phase 5 golden set needs out-of-domain questions** — ones that should
   return *nothing*. Otherwise evaluation only measures "did the right kural show
   up", never "did a wrong kural show up when nothing should have". A system that
   answers everything scores perfectly on the first and fails in real use.

2. **Build the golden set chapter-first, not memory-first.** I cannot judge
   retrieval from memory — I did not know Thirukkural has a chapter on abstaining
   from meat (26, புலால் மறுத்தல், 251–260). That limit is real and cannot be
   fixed by trying harder.

```
   WRONG   think of a question  ->  guess which kurals answer it
           (limited by what I happen to remember)

   RIGHT   open a chapter -> read its 10 kurals -> write the questions
           they answer
           (ground truth comes from the text, not my memory)
```

133 chapters, one question each, already exceeds the ~100 the plan asks for.

### Status after this session

- Phase 1 — closed. Corpus complete, audited, and the audit tool's own limits
  now measured rather than assumed.
- Phase 8 — unchanged, and its `calibrated: false` flag is now known to survive
  the arrival of embeddings.
- Next is still **Phase 2 — embeddings over the real corpus**, now with a
  measured embedding baseline (LaBSE, English explanations only) to beat.

---

## 2026-08-01 — Phase 5 opens: the scorecard, and what the baseline is really doing

### The scorecard exists now

`data/golden_set.json` — 100 questions, each with the kurals that genuinely
answer it. Two sources of "correct":

1. the question's own chapters (10 kurals each)
2. **200 hand-checked kurals from OTHER chapters** that still answer it

Source 2 matters. Kural 35 ("Four ills eschew: lust, anger, envy, evil-speech")
genuinely answers the anger question, but lives in chapter 4, not chapter 31.
Without source 2 the scorecard would mark a correct retrieval as WRONG.

How the 200 were found: a whole-word keyword sweep proposed candidates, a
rare-word filter cut the noise (a word appearing in 200 kurals points nowhere),
and then every candidate was read and judged by hand.

### BASELINE: 44 of 100

Plain kural-level embedding search. Question vs each of the 1330 kurals
(English translation + English explanation + Tamil meaning glued), cosine, top 5.

```
questions with a correct kural in top 5   44 of 100
average correct kurals per top 5          0.77 of 5
median rank of the first correct kural    7 of 1330
```

**Prediction vs reality.** I guessed most questions would get at least one hit.
It was under half. The gap was the lesson.

### NOTES TO RETURN TO after all methods are measured

**Note 1 — we are barely missing, not lost.**
Median rank of the first correct kural is **7**. The right answer usually sits
at position 6-8, just outside the top 5. Small improvements should move the
number a lot.

**Note 2 — the model is matching question SHAPE, not meaning.**
All 100 questions x 5 slots = 500 slots, filled by only **170 distinct kurals**.
The hogs:

```
26 of 100 questions | kural  251  "What graciousness can one command who feeds his flesh..."
22 of 100 questions | kural  862  "Loveless, aidless, powerless king Can he withstand..."
22 of 100 questions | kural  175  "What is one's subtle wisdom worth If it deals ill..."
18 of 100 questions | kural   53  "What is rare when wife is good What can be there when she is bad?"
```

Kural 251 is about **eating meat**. It answered 26 unrelated questions.

Every hog is phrased as a question. Our golden questions are phrased as
questions. The model is matching *question-shaped text*. This is the same
failure seen earlier when "how do I control my anger?" returned "How to hide
this lust which shows...".

This is the thing to come back to. It predicts that **query rewriting**
(turning a chatty question into a bare topic) should help more than anything
else — but that stays a prediction until it is measured.

### Method note — how this phase runs

Change ONE thing, re-measure against the same 100 questions, keep it only if
the number goes up. No eyeballing five results and forming a view. That was
the mistake that wasted the first half of the session.

### Measured, in order. Each row changes ONE thing.

```
method                      hits/100  avg in top5  median rank
kural only (BASELINE)             44         0.77            7
chapter only                      33         1.47           21
blend  chapter=0.5                52         1.33            4
keyword only (BM25)               45         0.80            7
hybrid rescaled kw=0.3            52         1.16            5
hybrid RRF (rank-based)           49         1.04            6
--- questions rewritten ---
REWRITE kural only                69         1.60            2
REWRITE blend=0.5                 67         2.12            2
REWRITE keyword only              53         1.09            5
REWRITE hybrid kw=0.3             75         2.03            1   <- best
REWRITE hybrid RRF                65         1.81            2
```

### Lesson 1 — the scorecard caught a wrong answer I had already given

Earlier the same day, on a test that defined "correct" as "in the right
chapter", chapter weight **0.8** measured as the best blend. On the honest
scorecard 0.8 scores **42 - below the 44 baseline**. The old test was grading
its own homework: chapter scores are built to find the right chapter, so
adding more of them always looked better. The honest answer is 0.5.

Chapter-only told the same story. It looked like the clear winner before.
Here it scores 33, eleven points BELOW baseline.

**A metric that rewards the thing you are testing is not a metric.**

### Lesson 2 — deleting words beat everything we built

`REWRITE kural only` is the plain baseline method with "how do I my" stripped
from the question. 44 -> 69. That one change is worth more than the chapter
blend and hybrid search put together.

No information was added. Noise was removed.

Why it works, and it was measured twice before it was believed:
  - kural 251 is about eating meat and answered 26 of 100 questions, because
    it opens "What graciousness can one command..." - question-SHAPED text
  - BM25 weighted "how" at 3.78 against "anger" at 4.13, because the corpus is
    old verse translation that rarely writes "how do I my"

### Lesson 3 — ORDER OF TESTING CHANGES THE CONCLUSION

Before rewriting, keyword search added nothing: 52 -> 52. I called it useless.
After rewriting, keyword search adds six points: 69 -> 75.

Same code. Opposite verdict.

It was never useless - it was blocked. Two methods that make the SAME mistake
cannot cover for each other. Hybrid search only pays when the two methods fail
DIFFERENTLY. Stripping the question words is what made them fail differently.

Had we tested rewriting first, we would have concluded keyword search was
great. Testing it first, we concluded it was worthless. Both from identical
code. **A single measurement is not a fact about a technique - it is a fact
about that technique in that pipeline at that moment.**

### Where it stands

44 -> 75, and the median rank of the first correct kural went from 7 to 1:
the top result is now usually right.

Note that the rewrite that did this is the CHEAP version - a hardcoded word
list, no LLM. Whether a real LLM rewrite beats a word list is now a
measurable question rather than an assumption.

### VOID — the LLM-rewrite rows do not count

```
LLM* hybrid kw=0.3   97/100    <- VOID, do not cite
LLM* keyword only    94/100    <- VOID
LLM* kural only      89/100    <- VOID
```

Rejected for two separate reasons, and the second is the stronger one:

1. **Leakage.** The rewrites were written by an LLM that had the chapter list
   in front of it. The rewrite for the anger question was "restraining anger" -
   the correct chapter's exact title. The answer was written into the question.

2. **It does not transfer.** Even with zero leakage, the number measures a
   large frontier model. Production would run a small cheap model whose
   rewrites are worse. **A measurement that cannot transfer to what you ship
   is not a measurement.** (Vikash's call, and it was the right one.)

Query rewriting gets re-tested when a real, small, local model is wired up.
The honest number remains the word-list rewrite: **75 of 100.**

One thing worth remembering from the void run: `LLM* keyword only` scored 94.
Once the query used the corpus's own vocabulary, plain keyword search beat the
embeddings. That is a hint about where the ceiling lives - not a result.

### Stage 2 — the reranker. 75 -> 85

```
REWRITE hybrid kw=0.3     75    stage 1 alone
RERANK top-50             85    <- +10
top-50 ceiling            94    the most a reranker could reach
```

Model: `cross-encoder/ms-marco-MiniLM-L-6-v2` (~90 MB, English-only).
Cost measured on this CPU: **418 ms per question**, against ~4 ms for the
embedding search. Roughly 100x slower.

It captured 10 of the 19 points available. Nine cases still had a correct
kural inside the top 50 that the reranker failed to lift into the top 5.

**Why a cross-encoder helps.** Every earlier method encoded the question and
the kural SEPARATELY, and the kural's numbers were frozen before any question
existed. One fixed summary had to serve every possible question. That is
exactly how kural 251 (about eating meat) answered 26 of 100 questions - its
frozen summary captured "this text asks a rhetorical question".

A cross-encoder puts both texts into the model together and scores the pair.
Nothing is cached, so it cannot be fooled by surface shape - but a new
question voids every score, which is why it only ever sees 50 candidates
instead of 1330.

**The ceiling rule.** A reranker only REORDERS what stage 1 hands it. If the
correct kural is not in the top 50, no reranker can find it. Measured ceilings
for our stage 1:

```
cutoff    ceiling
     5    75 of 100   (where stage 1 leaves us)
    10    85
    20    88
    50    94
   100    99
   200    99   <- completely flat, nothing left to find
```

Cost rises in a straight line with the cutoff; the gain flattens. That shape
is the whole reason to pick a cutoff rather than rerank everything.

### FULL RESULT FOR PHASE 5: 44 -> 85

```
kural only (BASELINE)             44
blend  chapter=0.5                52
keyword only (BM25)               45
hybrid rescaled kw=0.3            52
REWRITE kural only                69
REWRITE hybrid kw=0.3             75
RERANK top-50                     85
```

Every row is the same 100 questions, one change at a time.

### The multilingual reranker — tested, measured, REJECTED

```
method                      hits/100  avg in top5   time per question
RERANK en-only (ms-marco)        85       2.25             498 ms   <- KEPT
RERANK bge en-only               91       2.68          11,840 ms
RERANK bge en+tamil              91       2.77          17,483 ms
ceiling at top-50                94
```

**Decision: keep the English-only ms-marco reranker.** +6 points is not worth
24x the latency. Twelve seconds per search is not a product.

**Tamil added nothing.** 91 either way. The whole reason to go multilingual was
"our corpus is bilingual, our judge is monolingual, that's a mismatch." Measured:
the mismatch costs zero, because the English explanation already paraphrases
what the Tamil meaning says. The Tamil that MIGHT matter is the Parimelazhagar
commentary - the only Tamil column whose content the English does not duplicate.
Untested.

### Two library traps found the hard way

**1. `trust_remote_code=True` is a maintenance liability.**
`gte-multilingual-reranker-base` was the first choice - the ONLY candidate that
DECLARES Tamil ('ta') in its own metadata. It never ran. It ships custom model
code written against an older transformers; under transformers 5.x it reads an
uninitialised `position_ids` buffer (garbage like 124101626708704), and returns
NaN even after that is patched. A model that carries its own code carries code
that rots when the library moves under it.

**2. sentence-transformers' CrossEncoder wrapper FAILED SILENTLY on bge.**
It returned 0.000 for every pair - no error, no warning, just a ranking made of
noise. Loading the identical checkpoint with plain transformers gave real
numbers (-6.9 for a match, -11.0 for a mismatch). `rerank.py` now uses plain
transformers for every model.

**A wrapper that fails loudly is a bug. One that fails silently is a trap.**
Nothing in the scorecard would have caught this as anything but "that model is
bad" - the smoke test on three known pairs is what caught it.

Re-measuring ms-marco through the new plain-transformers path returned exactly
85, confirming the wrapper bug never touched it.

---

## 2026-08-02 — the measured pipeline becomes the served pipeline

Yesterday's 85 existed only inside `src/evaluate.py`. The web app was still
running word overlap — the 44-point method. Today closed that gap.

### The rule that shaped the design

**The thing we measure must be the exact thing we serve.**

`src/pipeline.py` is now the single definition of how a question is answered.
`evaluate.py` imports from it. `service/app.py` imports from it. There is no
second copy of the blend arithmetic to drift.

And the harness proves it rather than assuming it. A new row calls the real
`KuralRetriever` object end to end:

```
RERANK en-only top-50             85         2.25            1
PIPELINE (what ships)             85         2.26            1
```

Both 85. The 0.01 gap in the second column is one kural out of 500 slots,
caused by a batched matrix multiply and a single-vector multiply differing in
the last floating-point bits and flipping a near-tie.

### FAISS removed from the project

Decided today: this project is **exact only**. Every question is compared
against all 1330 verses, every time. An approximate index would trade real
accuracy for speed we do not need at this size. Written into CLAUDE.md §3.5 as
a standing rule that outranks speed everywhere, and Phase 6 is deleted.

### Calibration — measured, and the answer was no

`src/calibrate.py` ran 20 on-topic and 15 off-topic questions.

```
median on-topic   0.125          median off-topic  0.000
worst on-topic    0.000          best  off-topic   0.003
```

**Not calibrated** — but the failure mode REVERSED, and that is the finding.

Fourteen of fifteen off-topic questions scored *exactly* zero. The only one
that did not — "which king won the most gold in the war" — borrows three words
the book genuinely uses. The old word-overlap engine put "who won the football
world cup" at 0.85, above almost every real question.

So the overlap now comes from real questions scoring low ("how do I finish
what I start" scored 0.000), not fake ones scoring high. Unhelpful rather than
confidently wrong — the safer direction — but still an overlap, so a floor
above 0.003 would refuse four genuine questions to catch one fake.

`calibrated: false` stays in both Python and TypeScript. **Ranking well inside
a question and knowing whether the book has anything to say are two different
claims, and only the first is measured.**

### Published numbers

```
n = 100
recall@5      0.85    85 of 100 questions found a correct verse in the top 5
precision@5   0.45    2.26 of the 5 shown are correct, on average
MRR           0.71    1.00 would mean the first result is always right
latency       766 ms  (the reranker is ~500 of that)
```

Regenerate with `venv/bin/python src/report_metrics.py`. If /method disagrees
with that output, /method is wrong.

### Two processes, and an honest fallback

LaBSE takes seconds and ~1 GB to load, so it cannot be loaded per request.
`service/app.py` holds the models; Next.js calls it over localhost.

A process can be down, so the word-overlap engine stays as a fallback — and
when it takes over it **changes the engine name the reader sees**:

```
engine: word overlap · no embeddings yet — FALLBACK, the embedding service is unreachable
```

Verified by stopping the service mid-session. Silently degrading would be the
same sin as an unmeasured metric.

### A failure worth keeping

`lib/retrieval.ts` was written months ago predicting that word overlap would
fail on "how do I keep my temper", because no translation uses the word
"temper", and that embeddings would fix it. Tested today through the whole
stack:

```
820  Evil Friendship                Keep aloof from those that smile...
793  Investigation in Friendships   Temper, descent, defects and kins...
876  Knowing the Quality of Hate    Trust or distrust; during distress...
305  Restraining Anger              Thyself to save, from wrath away!
308  Restraining Anger              Save thy soul from burning ire
```

Partly fixed. Anger verses now reach the top 5 where word overlap found none —
but positions 1 to 3 are wrong, and the reason is visible: after the rewrite
strips "how do I my", BM25 searches for "keep temper", and kural 793 contains
the literal word "temper" meaning *disposition*, not anger. Kural 820 contains
"Keep".

The keyword half that is worth six points on the golden set is the half that
loses this question. That is what a blend is: an average of two different
mistakes, and the golden set only tells us the average is better.

### Session close — what I actually learned (2026-08-02)

Not what got coded. What I understand now that I did not this morning.

**1. A metric that rewards the thing you are testing is not a metric.**
Chapter weight 0.8 measured "best" on a test that defined correct as "in the
right chapter". On an honest scorecard it scores below doing nothing at all.
I now check what a metric is structurally biased toward before trusting it.

**2. The order you test things in changes the conclusion.**
Keyword search was worth zero before the query rewrite and six points after.
Same code. A measurement is a fact about a technique *in that pipeline at that
moment*, not about the technique.

**3. Removing noise beat adding cleverness.**
The biggest single gain of the whole project — 44 to 69 — came from deleting
four words from the question. Every clever thing I built afterwards was worth
less than that.

**4. Calibration is a separate claim from ranking.**
A retriever can order five verses well and still have no idea whether the book
addresses the question. Same split as a classifier that ranks well but whose
0.7 does not mean 70%. Only the first one is measured here.

**5. Libraries fail silently, and the scorecard will not catch it.**
sentence-transformers returned 0.000 for every pair on one model - no error. A
smoke test on three pairs where I already knew the answer caught it. The
scorecard would only have said "that model is bad".

**6. Exact beats approximate when you can afford exact.**
1330 verses compared in full, every time, 4 ms. I chose to delete FAISS from
the project rather than trade accuracy I do not need to trade.

**7. Measured and served must be the same code.**
An 85 that lives in the test harness is not an 85. The harness now calls the
production object so the two cannot drift.

### Where things stand

- Phases 0-5: done. Retrieval 44 -> 85, measured, committed, and running in
  the app.
- Phase 6: deleted (see §3.5 - exact only).
- Phase 7: not started. Generation with citations. This is the actual product.
- Phase 9: not started.

Branch `phase5-evaluation-harness`, four commits, not yet merged to main.
