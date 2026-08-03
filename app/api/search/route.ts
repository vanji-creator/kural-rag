import { NextResponse } from "next/server";

import { getDemoResponse } from "@/lib/demo";
import { newRequestId, recordError, recordSearch } from "@/lib/logger";
import { ACTIVE_ENGINE, DEFAULT_RESULT_LIMIT } from "@/lib/retrieval";
import type { SearchResponse } from "@/lib/types";

/**
 * One question in, retrieved verses out.
 *
 * `answer` is null and will stay null until Phase 7 puts a generator behind
 * it. That is not an oversight — retrieval is the ceiling. A perfect model
 * fed the wrong verses produces a confident wrong answer, so the verses come
 * first and the prose comes last.
 *
 * EVERY REQUEST IS WRITTEN DOWN.
 *
 * A `requestId` is created here and travels with the question into the Python
 * service, which writes it into its own log too. One question therefore leaves
 * a line in logs/web.jsonl and a line in logs/searches.jsonl, joinable on that
 * id. The id is also returned to the browser, so a person reporting "this
 * search was wrong" can quote something that finds the exact request.
 */
export async function GET(request: Request) {
  const url = new URL(request.url);
  const requestId = newRequestId();

  const demoKey = url.searchParams.get("demo");
  if (demoKey) {
    const demo = getDemoResponse(demoKey);
    if (!demo) {
      recordError({
        requestId,
        whatFailed: "demo lookup",
        message: `unknown demo state: ${demoKey}`,
      });
      return NextResponse.json(
        { error: "unknown demo state", requestId },
        { status: 404 },
      );
    }
    return NextResponse.json({ ...demo, requestId });
  }

  const query = (url.searchParams.get("q") ?? "").trim();
  if (!query) {
    return NextResponse.json({ error: "empty query", requestId }, { status: 400 });
  }

  const limitParam = Number(url.searchParams.get("limit"));
  const limit =
    Number.isFinite(limitParam) && limitParam > 0 && limitParam <= 20
      ? Math.floor(limitParam)
      : DEFAULT_RESULT_LIMIT;

  // Started BEFORE the call and read after, so this is the wait a reader
  // really experiences — network hop included. The service's own number
  // cannot see that hop and is always smaller.
  const startedAt = performance.now();

  let retrieval;
  try {
    retrieval = await ACTIVE_ENGINE.search(query, limit, requestId);
  } catch (error) {
    const message = error instanceof Error ? error.message : "unknown error";
    recordError({ requestId, whatFailed: "search", message, query });
    return NextResponse.json(
      { error: "search failed", requestId },
      { status: 500 },
    );
  }

  const waitedMs = Math.round((performance.now() - startedAt) * 10) / 10;

  recordSearch({
    requestId,
    query,
    limit,
    engine: retrieval.engine,
    resultCount: retrieval.results.length,
    topScore: retrieval.topScore,
    confidence: retrieval.confidence,
    waitedMs,
    // Both degraded paths announce themselves in the engine name — the
    // rewriter being down, and the whole Python service being down. Counting
    // this field over a day says how healthy the system really was.
    degraded:
      retrieval.engine.includes("DEGRADED") ||
      retrieval.engine.includes("FALLBACK"),
  });

  const response: SearchResponse = { retrieval, answer: null, requestId };
  return NextResponse.json(response);
}
