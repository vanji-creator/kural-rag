# The web app

Next.js 15 (App Router) + React 19 + TypeScript. No CSS framework — the design
is a token system, so `app/globals.css` carries it directly.

**Retrieval runs in a separate Python process.** Start it first, or the app
falls back to word overlap and says so:

```bash
# terminal 1 — the retriever (holds LaBSE + the reranker in memory)
venv/bin/uvicorn service.app:app --port 8000

# terminal 2 — the interface
npm install
npm run dev          # http://localhost:3000
npm run build        # production build
npm run typecheck    # tsc --noEmit
```

Two processes because LaBSE takes seconds and about a gigabyte to load. Paying
that per request is not a product, so one process loads it once and holds it.
`RETRIEVAL_SERVICE_URL` overrides where the app looks for it.

## What is real and what is not

| Part | State |
| --- | --- |
| All 1330 kurals, chapters, sections | real, from `data/kurals.json` |
| Browse, verse pages, commentary | real, complete |
| Search | **real** — embeddings + keyword + cross-encoder rerank, 85/100 measured |
| Grounded answer | **not built** — no generator is connected |
| Evaluation numbers on `/method` | **measured** — n = 100, `src/report_metrics.py` |
| Confidence / refusal | **not calibrated** — measured, and it does not separate |

Search stopped being a placeholder on 2026-08-02. Word overlap scored 44 of
100 on the golden set; what runs now scores 85. The old engine is still in
`lib/retrieval.ts` as the fallback when the Python service is unreachable —
and when it takes over, the engine name shown to the reader changes to say so.

`/method` carries real numbers now, except citation validity, which stays
blank because nothing generates answers yet. Confidence is still declared
uncalibrated: `src/calibrate.py` shows that off-topic questions collapse to
zero but so do a few genuine ones, so no threshold earns its place. Nothing in
the interface presents a fabricated answer or an unmeasured metric.

## Where things live

```
app/
  page.tsx              search — the one page with phases (rest → thinking → answer)
  browse/page.tsx       the book: 3 sections → 13 subsections → 133 chapters
  kural/[number]/       one verse, with the full apparatus
  method/page.tsx       how retrieval works, what is measured, what is not
  api/search/route.ts   question in, retrieved verses out
  globals.css           every design token, then one class per element

components/
  SearchExperience.tsx  the search state machine
  ResultCard.tsx        one retrieved verse, expandable
  ThinkingScreen.tsx    the retrieval animation
  NoticeBlock.tsx       the band that says what is wrong with a result

lib/
  corpus.ts             loads the corpus, builds chapter/section indices
  retrieval.ts          RetrievalEngine, the real engine, and the fallback
  apparatus.ts          translations / meanings / commentaries for one verse
  demo.ts               canned states, so every screen can be looked at
```

## Swapping in real retrieval

`lib/retrieval.ts` defines one interface:

```ts
interface RetrievalEngine {
  name: string;          // shown to the reader
  description: string;   // shown to the reader
  highConfidence: number;
  floor: number;
  calibrated: boolean;   // false = this engine's absolute scores mean nothing
  search(query, limit): RetrievalOutcome;
}
```

Write a second engine that embeds the query and ranks by cosine similarity,
then change `ACTIVE_ENGINE`. Nothing in the UI changes: the thresholds, the
confidence notices and the refusal policy are all read from whichever engine is
active.

`calibrated` is the important one. The current engine sets it to `false`
because its scores were measured and found not to separate on-topic questions
from off-topic ones — "who won the football world cup" outscores most real
questions. While that flag is false the interface will not claim confidence and
will not refuse on the reader's behalf. See the comment block in
`lib/retrieval.ts` for the numbers.

## Deploying

Vercel, root directory = repo root. `data/kurals.json` is imported statically
by `lib/corpus.ts`, so the corpus is bundled at build time and nothing is read
from disk at runtime — no file-tracing configuration needed.

`lib/corpus.ts` and `lib/retrieval.ts` both import `server-only`. Importing
either from a client component is a build error rather than a 5 MB payload sent
to a browser.

## Known gaps

- **Chapter preambles are not split out.** 57 kurals open their Parimelazhagar
  commentary with the chapter's preamble. The corpus flags this with a boolean
  but does not separate the text, and there is no reliable boundary to split
  on, so the interface marks it rather than inventing a division.
- **`npm audit` reports 3 high-severity advisories** in `postcss` and `sharp`,
  both transitive dependencies of Next 15.5.22. The suggested fix downgrades
  Next to version 9, which is not a fix. Waiting on an upstream Next release.
- **Verse pages are server-rendered per request** rather than prerendered.
  1330 static pages would build fine and would be faster to serve; it was left
  dynamic to keep build times short while the app is changing.
