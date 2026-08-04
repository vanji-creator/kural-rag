# Kural reranker bake-off — portable package

Tests whether `BAAI/bge-reranker-v2-m3` (568M parameters, reads Tamil)
beats the shipping reranker (`ms-marco-MiniLM-L-6-v2`, 22M, English only)
on the project's 233-question benchmark.

## What's inside

```
run_bakeoff.py        the one command you run
bakeoff/              the code, one small module per job
  config.py           every knob
  loading.py          loads data, refuses to run if anything disagrees
  checkpointing.py    progress saved every 10 questions, atomic writes
  model.py            the reranker (GPU if present, CPU if not)
  scoring.py          the per-arm loop, resumable
  stats.py            McNemar's exact test
  report.py           the table and the verdicts
data/
  piles.json          the frozen 50-candidate piles (computed at home -
                      NEVER recompute these elsewhere, see below)
  texts.json          the verse texts, English and English+Tamil
  baseline.json       the shipping reranker's saved results (arm A)
```

## Why the piles are frozen

Different machines compute embeddings with tiny differences in the last
decimal places — enough to swap the verse at position 50 for the one at 51.
Every arm of every bake-off must reorder the IDENTICAL piles or the
comparison means nothing. So the piles were computed once, at home, and
travel as data.

## Run it on Google Colab

1. Runtime → Change runtime type → **T4 GPU** → Save.
2. Upload the zip using the notebook (`Kural_BGE_Bakeoff.ipynb`) or the
   Files pane.
3. Run the cells. Expected time on a T4: **10–20 minutes** for both arms.
4. The last cell downloads `bge_bakeoff_results.json` — bring it home.

If Colab disconnects mid-run: reconnect, re-run the same cell. The
checkpoint continues from where it stopped, losing at most 10 questions.

## Smoke test (any machine, ~1 minute)

```
python run_bakeoff.py --model cross-encoder/ms-marco-MiniLM-L-6-v2 --limit 20
```

Runs the plumbing with the small model on 20 questions. Arm E with this
model must exactly reproduce the baseline's first 20 answers — same model,
same piles, same texts — so this checks the whole pipeline end to end.
Delete `data/checkpoint.json` afterwards.

## What decides the outcome (written before the run)

- **Ships if:** beats the baseline's 174/233 with p < 0.05, or a clear
  rank-1 gain at no top-5 cost.
- **Ends this line if:** loses, or the gap is too small to establish.
