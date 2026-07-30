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
