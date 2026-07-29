# Design brief — Kural RAG

Design the frontend for **Kural RAG**: a semantic search and grounded-answer
interface over the Thirukkural — 1330 classical Tamil couplets written roughly
2000 years ago by Thiruvalluvar.

A user asks a question in **English, Tamil, or Thanglish** (Tamil written in
English letters, e.g. `sinam adakkuvadhu eppadi`). The system retrieves the
kurals that actually address it, shows them with translation and classical
commentary, and generates a short answer that **cites the specific kurals it
used** and never invents an interpretation.

This is a serious reference instrument for a 2000-year-old text. It should feel
like it was built by people who respect the text and know what they are doing.

---

## The one thing this must not look like

**Do not design another chat interface.** No message bubbles, no avatar circles,
no "regenerate" toolbar, no pinned composer at the bottom of a scrolling
transcript. The moment it reads as a ChatGPT skin, the design has failed.

Also explicitly avoid:

- purple/indigo gradients, glassmorphism, glowing borders, "AI sparkle" icons
- generic SaaS landing tropes: logo cloud, three feature cards, gradient blob
- dark mode as the primary identity
- emoji anywhere in the interface
- heavy drop shadows and uniformly rounded corners on everything
- stock imagery, illustrations of scrolls, temples, lamps, or ornamental borders

The Tamil script and the typography **are** the ornament. Nothing else is needed.

---

## Aesthetic direction

Light, white, minimal, and unmistakably premium — the restraint of Apple's
product pages and the composure of a well-set book.

- **Ground it in near-white, not pure white.** A slightly warm paper tone reads
  as considered; `#FFFFFF` reads as unstyled. Ink should be a soft near-black,
  never `#000000`.
- **Separate with hairlines and space, not shadows.** 1px rules at low opacity.
  If an element needs elevation, question whether it needs to exist.
- **One accent colour only**, used sparingly — for the active state, the
  citation link, and nothing else. Everything else is ink, paper, and grey.
- **Space is the primary design material.** Be generous and consistent. Define
  a spacing scale and never break it.
- **Define a real type scale** with deliberate optical sizes, and use tabular
  figures for kural numbers and similarity scores so they align in columns.

Deliver this as an actual design system — colour tokens, spacing scale, type
scale, motion tokens — not as one-off values per component.

---

## Typography — the hardest and most important part

Tamil and English carry **equal weight**, set as a matched pair. Neither is a
subtitle of the other.

Things that will go wrong unless you handle them deliberately:

1. **Tamil must have an explicitly chosen and loaded typeface.** If you do not
   specify one, Tamil falls back to a system default that looks broken next to
   a well-set Latin face. Choose a specific Tamil family and pair it
   intentionally with the Latin family.
2. **Tamil needs more line-height than Latin.** Its ascenders and descenders are
   taller and its glyph clusters are wider. Latin line-height applied to Tamil
   looks cramped and amateurish. Specify separate values.
3. **Optical size mismatch.** At the same nominal font size, Tamil usually reads
   larger than Latin. Tune the two sizes until they feel equal on the page.
4. **Classical Tamil is dense.** The couplet is seven words carrying an entire
   argument. Give it room. It should feel like a line of poetry, not a data cell.
5. Consider a literary serif for the English translation and a clean grotesque
   for interface chrome — signalling "this is the text" versus "this is the app".

Every Tamil string must carry `lang="ta"` and every English string `lang="en"`,
for screen readers and correct font selection.

---

## The real data you are designing for

One kural record contains exactly these fields. Design only with these — do not
invent fields, and do not assume anything is available that is not listed.

```
number                          1..1330
section_tamil / section_english        3 sections  (e.g. அறத்துப்பால் / Virtue)
subsection_tamil / subsection_english  13 subsections
chapter_tamil / chapter_english        133 chapters (e.g. வெகுளாமை / Restraining Anger)
kural_line1, kural_line2               the couplet, classical Tamil, 2 lines
transliteration                        romanised Tamil
english_translation                    short, poetic, archaic ("Thyself to save, from wrath away!")
english_couplet                        verse translation, archaic ("'Gainst wrath who guards not...")
english_explanation                    plain modern English prose  <- most readable
tamil_meaning_mu_varadarajan           modern Tamil prose
tamil_meaning_solomon_pappaiah         modern Tamil prose
tamil_meaning_karunanidhi              modern Tamil prose (empty for 2 kurals)
parimelazhagar_commentary              13th-century classical commentary, TAMIL ONLY
manakkudavar_commentary                classical commentary, TAMIL ONLY (empty for 3 kurals)
```

Plus, per search result: a **similarity score** between 0 and 1.

Structure of the book: 3 sections → 13 subsections → 133 chapters → exactly 10
kurals per chapter. That regularity is a gift. Use it.

### Three constraints that must shape the design

1. **There are three different English translations of the same couplet**, and
   two of them are deliberately archaic. Decide which is primary and how a user
   reaches the others without clutter.
2. **The classical commentary exists in Tamil only.** An English-speaking user
   will see Tamil there, and there is no English version anywhere. Handle this
   with dignity — do not hide it, and do not apologise for it in a grey box.
   Range: 124 to 1684 characters. It is long. 57 kurals also carry a chapter
   preamble, making them longer still.
3. **Commentary length varies enormously.** The layout must hold a 124-character
   commentary and a 1684-character one without either looking broken.

---

## What to design

### 1. The core flow, on one continuous page

**Resting state.** Before any query. This is the first impression and it must be
the most confident screen in the product. A single input, and enough presence
that the page feels finished rather than empty. Make it clear, without a
paragraph of explanation, that questions can be asked in English, Tamil, or
Thanglish.

**Thinking state.** Retrieval and generation take real time. Design what happens
in that gap. A generic spinner wastes the best motion opportunity in the app.

**Answer state.** Structured as:

```
   the question, restated

   ── a short generated answer, 2–4 sentences,
      with inline citation chips ⟨305⟩ ⟨302⟩ ⟨129⟩

   ── an honest line about grounding
      ("grounded in 3 of 1330 kurals")

   ── the retrieved kurals, ranked, each showing its
      similarity score
```

Citations are the heart of this product. A citation chip must be visibly
interactive and must take the user to the exact verse it refers to, with a clear
arrival state so they know where they landed. The user must always be able to
verify the answer against the source. Design that path as a first-class flow,
not a footnote.

**Verse card, collapsed and expanded.** Collapsed shows number, chapter, the
couplet, the plain English explanation, and the score. Expanded reveals the
alternate translations, the modern Tamil meanings, and the classical
commentaries. Design the transition between the two — it is the most-used
interaction in the app.

### 2. Chapter browsing

The 133 chapters as a structure worth exploring, not a dropdown. Section →
subsection → chapter → its 10 kurals. This is where the book becomes an object
rather than a search index, and it is a strong differentiator. Give it real
design attention.

### 3. Verse detail

One kural, given the full page. Everything known about it, well composed.
Shareable — this is the screen people will link to.

### 4. Methodology page

How the system works and how well it works: the retrieval pipeline, and measured
numbers such as recall@5 and precision@5. Design a page that presents an
engineering result with clarity and confidence — closer to a well-made technical
report than a marketing page. Include a diagram of the retrieve → augment →
generate pipeline.

---

## States that must be designed, not left to chance

- **No good match.** The top score is low and no kural genuinely answers the
  question. The product must say so plainly rather than presenting weak results
  as if they were strong. This is a point of integrity — design it well.
- **Low-confidence answer.** Results exist but are marginal. Show the doubt.
- **A question the Thirukkural does not address at all.**
- **A Thanglish query**, which retrieves measurably worse than English. If the
  interface can help the user without scolding them, design that.
- **Empty commentary**, for the handful of kurals that lack one.
- **A very long commentary** that dominates the card.
- **First load**, with no query yet, and **error** when the backend fails.

---

## Motion

Expressive and choreographed — but engineered, never decorative. Every movement
should explain something about the system.

Opportunities worth taking:

- the transition from resting state to answer state — the single most important
  moment in the app
- the retrieval wait, which can honestly express "searching 1330 verses"
- ranked results arriving in sequence, so rank is felt rather than read
- similarity scores resolving to their value rather than appearing finished
- the collapse/expand of commentary, handling a large and variable height change
- arriving at a cited verse from a citation chip

Define motion tokens: durations, easing curves, and stagger intervals. Use real
easing, not `ease-in-out`. Respect `prefers-reduced-motion` with a genuinely
considered reduced variant, not motion simply switched off.

---

## Non-negotiables

- **Responsive**, and genuinely good on a phone. Tamil text does not reflow like
  Latin — long unbroken clusters can force horizontal scroll. Test the narrow
  case deliberately.
- **Accessible.** Real focus states, AA contrast minimum, full keyboard path
  through search → results → citation → verse, correct `lang` attributes.
- **Fast-feeling.** No layout shift when results arrive.
- **Dark mode is optional.** If included, it must be a deliberate second theme,
  not an inverted palette. The light theme is the identity.

---

## Deliverable

A working, self-contained front-end demonstrating every screen and state above,
using realistic Thirukkural content — real Tamil couplets, real translations,
real commentary, real chapter names. Placeholder lorem text will hide exactly
the problems this design needs to solve.

Include the design system explicitly: colour tokens, type scale with both Latin
and Tamil settings, spacing scale, motion tokens.

Show your reasoning on the three or four decisions you consider most important,
especially the Tamil/Latin typographic pairing.
