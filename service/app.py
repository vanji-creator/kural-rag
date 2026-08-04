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
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, Query
from fastapi.responses import JSONResponse

# src/ holds the pipeline. Adding it to the path keeps the service a thin
# wrapper rather than a second copy of anything.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from pipeline import (  # noqa: E402  (import must follow the path insert)
    ENGINE_DESCRIPTION, ENGINE_NAME, EMBEDDING_MODEL_NAME,
    RERANK_CANDIDATE_COUNT, SCORES_ARE_CALIBRATED, KuralRetriever)
from rerank import PRODUCTION_RERANKER_MODEL  # noqa: E402
from search_log import (  # noqa: E402
    SEARCH_LOG_PATH, configure_logging, new_request_id, record, record_error,
    record_search)

MAX_RESULTS = 20
DEFAULT_RESULTS = 5

# Filled in at startup. Module-level so every request shares one instance -
# the entire point of the service.
retriever = None


@asynccontextmanager
async def lifespan(app):
    """Load the models once, before the first request is served."""
    global retriever
    log = configure_logging()
    log.info("loading models - the first request waits for this, none after it")

    started_at = time.perf_counter()
    retriever = KuralRetriever(use_reranker=True)
    startup_seconds = round(time.perf_counter() - started_at, 1)

    rewriter = retriever.rewriter
    # A "started" line means every later line in this file can be traced to a
    # known configuration. Without it, a log of searches cannot tell you WHICH
    # engine produced them, and an old log becomes unreadable the moment
    # anything changes.
    record("service_started",
           engine=ENGINE_NAME,
           embeddingModel=EMBEDDING_MODEL_NAME,
           rerankerModel=PRODUCTION_RERANKER_MODEL,
           rerankCandidates=RERANK_CANDIDATE_COUNT,
           calibrated=SCORES_ARE_CALIBRATED,
           corpusSize=len(retriever.kurals),
           rewriterModel=rewriter.model_name if rewriter else None,
           rewriterReady=rewriter is not None,
           rewritesCached=len(rewriter.cache) if rewriter else 0,
           startupSeconds=startup_seconds)
    log.info("ready in %ss - writing every search to %s",
             startup_seconds, SEARCH_LOG_PATH)
    yield
    record("service_stopped")
    # nothing else to tear down: the models die with the process


app = FastAPI(title="Kural RAG retrieval", lifespan=lifespan)


@app.get("/health")
def health():
    """Is the service up, and what exactly is it running?

    The frontend displays the engine name beside every score. A score with no
    stated source is the thing this project refuses to show, so the service
    has to be able to say what it is.
    """
    rewriter = getattr(retriever, "rewriter", None) if retriever else None
    return {
        "status": "ready" if retriever is not None else "loading",
        "engine": ENGINE_NAME,
        "description": ENGINE_DESCRIPTION,
        "embeddingModel": EMBEDDING_MODEL_NAME,
        "rerankerModel": PRODUCTION_RERANKER_MODEL,
        "rerankCandidates": RERANK_CANDIDATE_COUNT,
        "calibrated": SCORES_ARE_CALIBRATED,
        "corpusSize": len(retriever.kurals) if retriever else 0,
        # The rewriter is the only part that can be missing while everything
        # else is fine, so its state has to be visible from outside.
        #
        # NOTHING HERE TOUCHES THE KEY. Not the key, not a prefix of it, not
        # its length. /health is an unauthenticated endpoint - anything it
        # returns is public, and a key is never a status.
        "rewriterModel": rewriter.model_name if rewriter else None,
        "rewriterReady": rewriter is not None,
        "rewritesCached": len(rewriter.cache) if rewriter else 0,
        "rewritesPaidThisRun": rewriter.calls_made if rewriter else 0,
        "rewriterRupeesThisRun": (round(rewriter.model.rupees_spent(), 4)
                                  if rewriter else 0.0),
    }


@app.get("/search")
def search(q: str = Query(..., description="the question, as typed"),
           limit: int = Query(DEFAULT_RESULTS, ge=1, le=MAX_RESULTS),
           x_request_id: str = Header(default=None)):
    """One question in, ranked verses out. Shaped like RetrievalOutcome.

    `x_request_id` is sent by the web app. Both sides write it into their own
    log, which is the only reason the two logs can be read together
    afterwards. If it is missing we invent one, so no search is ever
    unidentifiable - but then it cannot be joined to the web app's line.
    """
    request_id = x_request_id or new_request_id()

    if retriever is None:
        record_error("search", "models are still loading",
                     request_id=request_id, question=q)
        return JSONResponse({"error": "still loading models",
                             "requestId": request_id}, status_code=503)

    question = q.strip()
    if not question:
        record_error("search", "empty query", request_id=request_id)
        return JSONResponse({"error": "empty query",
                             "requestId": request_id}, status_code=400)

    try:
        outcome = retriever.search(question, top_k=limit)
    except Exception as error:
        # The message has already had the key removed by HostedModel.scrub if
        # it came from there. Everything else is ours and carries no secret.
        record_error("search", error, request_id=request_id,
                     question=question)
        return JSONResponse({"error": "search failed",
                             "requestId": request_id}, status_code=500)

    record_search(outcome, request_id=request_id,
                  rewriter=retriever.rewriter)
    # Handed back so the browser and both log files can all be joined on it.
    outcome["requestId"] = request_id
    return outcome
