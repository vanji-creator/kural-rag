import { NextResponse } from "next/server";

import { getDemoResponse } from "@/lib/demo";
import { newRequestId, recordError, recordSearch } from "@/lib/logger";
import {
  ACTIVE_ENGINE,
  DEFAULT_RESULT_LIMIT,
  generateAnswer,
} from "@/lib/retrieval";
import type { SearchResponse } from "@/lib/types";

/**
 * One question in, retrieved verses out — and since 2026-08-04, a grounded
 * answer above them when one can be written.
 *
 * The order is deliberate and unchanged: retrieval first, prose last. A
 * perfect model fed the wrong verses produces a confident wrong answer, so
 * the answer is only attempted after retrieval succeeds, and a failed
 * generation degrades to `answer: null` — never to a failed search.
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

  // Generate only when there is something to ground an answer in, and only
  // when the real engine answered — the word-overlap fallback retrieves
  // different verses than the service would, and an answer generated from a
  // degraded ranking must not appear under a normal search.
  let answer = null;
  const retrievalDegraded =
    retrieval.engine.includes("DEGRADED") ||
    retrieval.engine.includes("FALLBACK");
  if (
    retrieval.confidence !== "none" &&
    retrieval.results.length > 0 &&
    !retrievalDegraded
  ) {
    answer = await generateAnswer(query, limit, requestId);
  }

  const response: SearchResponse = { retrieval, answer, requestId };
  return NextResponse.json(response);
}
