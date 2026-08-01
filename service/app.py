"""The retrieval service. One long-running process that holds the models.

WHY THIS EXISTS AT ALL

Loading LaBSE takes seconds and about a gigabyte of memory. A design where the
web app shells out to Python per request would pay that on every single search,
which is not a product. So one process loads everything once at startup and
answers over HTTP for as long as it lives.

That single fact is the whole architecture: Next.js renders and serves the
interface, this process does the retrieval, and they talk over localhost.

WHAT IT PROMISES

The JSON it returns matches `RetrievalOutcome` in lib/types.ts exactly, so the
frontend's contract does not change when the engine behind it does.

Run it:

    venv/bin/uvicorn service.app:app --port 8000
"""

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

# src/ holds the pipeline. Adding it to the path keeps the service a thin
# wrapper rather than a second copy of anything.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from pipeline import (  # noqa: E402  (import must follow the path insert)
    ENGINE_DESCRIPTION, ENGINE_NAME, EMBEDDING_MODEL_NAME,
    RERANK_CANDIDATE_COUNT, SCORES_ARE_CALIBRATED, KuralRetriever)
from rerank import RERANKER_MODEL_NAME  # noqa: E402

MAX_RESULTS = 20
DEFAULT_RESULTS = 5

# Filled in at startup. Module-level so every request shares one instance -
# the entire point of the service.
retriever = None


@asynccontextmanager
async def lifespan(app):
    """Load the models once, before the first request is served."""
    global retriever
    print("loading models - the first request waits for this, none after it")
    retriever = KuralRetriever(use_reranker=True)
    yield
    # nothing to tear down: the models die with the process


app = FastAPI(title="Kural RAG retrieval", lifespan=lifespan)


@app.get("/health")
def health():
    """Is the service up, and what exactly is it running?

    The frontend displays the engine name beside every score. A score with no
    stated source is the thing this project refuses to show, so the service
    has to be able to say what it is.
    """
    return {
        "status": "ready" if retriever is not None else "loading",
        "engine": ENGINE_NAME,
        "description": ENGINE_DESCRIPTION,
        "embeddingModel": EMBEDDING_MODEL_NAME,
        "rerankerModel": RERANKER_MODEL_NAME,
        "rerankCandidates": RERANK_CANDIDATE_COUNT,
        "calibrated": SCORES_ARE_CALIBRATED,
        "corpusSize": len(retriever.kurals) if retriever else 0,
    }


@app.get("/search")
def search(q: str = Query(..., description="the question, as typed"),
           limit: int = Query(DEFAULT_RESULTS, ge=1, le=MAX_RESULTS)):
    """One question in, ranked verses out. Shaped like RetrievalOutcome."""
    if retriever is None:
        return JSONResponse({"error": "still loading models"}, status_code=503)

    question = q.strip()
    if not question:
        return JSONResponse({"error": "empty query"}, status_code=400)

    return retriever.search(question, top_k=limit)
