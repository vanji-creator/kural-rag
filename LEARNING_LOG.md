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

### Status

- Concept 1 (embeddings) — done in pre-work.
- Concept 2 (similarity / cosine) — **properly done today**, derived by hand.
- Phase 0 — complete. Map understood.
- Next: **Phase 1 — build the corpus.** 1330 kurals + meanings + commentary
  into clean structured data. Mostly data wrangling; my normal skills apply.

Open housekeeping: repo is not a git repo yet; folder structure
(`data/ src/ experiments/`) proposed but not created; `sandbox.py` still at
the repo root.
