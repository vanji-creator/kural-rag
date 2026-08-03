"""Write down what actually happened, in a shape we can analyse later.

WHY A SEPARATE LOG AND NOT JUST print()

A print is for a person watching a terminal right now. It is thrown away.
The questions people really ask are the most valuable data this project will
ever produce, and none of it exists yet - our 233 test questions were written
by us, guessing at what people would type.

So every search writes ONE LINE of JSON to logs/searches.jsonl. One line per
search, every field named, nothing free-form. That shape is chosen so that
questions like these can be answered by reading the file:

    which questions came back with a low top score?
    how often is the rewriter down?
    which stage is the slow one - the rewrite, the search, or the reranker?
    what do people actually ask about?
    what have we spent today?

A log of sentences could not answer any of those without a parser. A log of
JSON lines answers all of them with a few lines of Python - see
src/read_logs.py.

TWO KINDS OF OUTPUT, ON PURPOSE

    the terminal   short, human, for whoever is watching a server start
    the file       complete, machine-readable, for questions asked later

WHAT NEVER GOES IN

The API key, obviously - it is never passed to this module at all, so it
cannot arrive by accident.

Real questions from real people DO go in, and that is the point of the file,
but it makes logs/ private data. logs/ is in .gitignore and must stay there.
"""

import json
import logging
import os
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# A deployed copy should point this at a disk that survives a restart.
LOG_DIRECTORY = Path(os.environ.get("LOG_DIRECTORY", PROJECT_ROOT / "logs"))
SEARCH_LOG_PATH = LOG_DIRECTORY / "searches.jsonl"

# How chatty the terminal is. Set LOG_LEVEL=DEBUG to see everything.
TERMINAL_LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

# Two requests can be served at the same time, and two half-written lines
# interleaved in one file is a corrupted log. One lock, held only for the
# instant it takes to append.
_write_lock = threading.Lock()

logger = logging.getLogger("kural")


def configure_logging():
    """Set up terminal logging once, at process start."""
    if logger.handlers:          # already configured; do not double up
        return logger
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s  %(levelname)-7s %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, TERMINAL_LOG_LEVEL, logging.INFO))
    logger.propagate = False
    return logger


def new_request_id():
    """A short id for one question's journey through the whole system.

    The browser asks Next.js, Next.js asks this Python service. Each writes
    its own log line. Without a shared id those two files cannot be joined and
    a question like "why did THAT search take four seconds" has no answer -
    you can see the slow request in one file and never find its other half.
    """
    return uuid.uuid4().hex[:12]


def _now():
    """The time, in a format that sorts correctly as plain text."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def record(event_name, **fields):
    """Append one event to the log file. Never raises.

    A logger that can crash the request it is logging is worse than no logger
    at all, so every failure here is swallowed and reported to the terminal.
    """
    line = {"time": _now(), "event": event_name}
    line.update(fields)
    try:
        LOG_DIRECTORY.mkdir(parents=True, exist_ok=True)
        with _write_lock:
            with open(SEARCH_LOG_PATH, "a", encoding="utf-8") as open_file:
                json.dump(line, open_file, ensure_ascii=False)
                open_file.write("\n")
    except Exception as error:
        logger.warning("could not write to the log file: %s", error)
    return line


def record_search(outcome, request_id=None, rewriter=None):
    """Write one finished search down, in full.

    `outcome` is exactly what KuralRetriever.search returned, so this function
    cannot describe something different from what was served.
    """
    results = outcome.get("results", [])
    rewritten_by = outcome.get("rewrittenBy", "")
    timings = outcome.get("timingMs", {})

    fields = {
        "requestId": request_id,
        "question": outcome.get("query"),
        "questionLanguage": outcome.get("queryLanguage"),
        "searchedFor": outcome.get("searchedFor"),
        "rewrittenBy": rewritten_by,
        # True when the question was searched WITHOUT a rewrite. This is the
        # field to count when asking "how healthy was the system yesterday".
        "degraded": rewritten_by.startswith("none (rewriter"),
        "resultKurals": [item["kural"]["number"] for item in results],
        "resultScores": [round(item["score"], 4) for item in results],
        "topScore": round(outcome.get("topScore", 0.0), 4),
        "confidence": outcome.get("confidence"),
        "calibrated": outcome.get("calibrated"),
        "engine": outcome.get("engine"),
        "timingMs": timings,
        "totalMs": outcome.get("elapsedMs"),
        "servedFromQueryCache": outcome.get("cached", False),
    }
    if rewriter is not None:
        # Running totals, so a day's spend can be read straight off the last
        # line of the log instead of being reconstructed.
        fields["rewritesPaidSoFar"] = rewriter.calls_made
        fields["rupeesSpentSoFar"] = round(rewriter.model.rupees_spent(), 5)

    logger.info("search %s  %.0fms  %s  -> %s",
                request_id or "-",
                outcome.get("elapsedMs", 0),
                (outcome.get("query") or "")[:48],
                fields["resultKurals"][:5])
    return record("search", **fields)


def record_error(what_failed, message, request_id=None, **extra):
    """Write down something that went wrong."""
    logger.error("%s failed: %s", what_failed, message)
    return record("error", requestId=request_id, whatFailed=what_failed,
                  message=str(message), **extra)
