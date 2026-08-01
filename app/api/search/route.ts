import { NextResponse } from "next/server";

import { getDemoResponse } from "@/lib/demo";
import { ACTIVE_ENGINE, DEFAULT_RESULT_LIMIT } from "@/lib/retrieval";
import type { SearchResponse } from "@/lib/types";

/**
 * One question in, retrieved verses out.
 *
 * `answer` is null and will stay null until Phase 7 puts a generator behind
 * it. That is not an oversight — retrieval is the ceiling. A perfect model
 * fed the wrong verses produces a confident wrong answer, so the verses come
 * first and the prose comes last.
 */
export async function GET(request: Request) {
  const url = new URL(request.url);

  const demoKey = url.searchParams.get("demo");
  if (demoKey) {
    const demo = getDemoResponse(demoKey);
    if (!demo) {
      return NextResponse.json({ error: "unknown demo state" }, { status: 404 });
    }
    return NextResponse.json(demo);
  }

  const query = (url.searchParams.get("q") ?? "").trim();
  if (!query) {
    return NextResponse.json({ error: "empty query" }, { status: 400 });
  }

  const limitParam = Number(url.searchParams.get("limit"));
  const limit =
    Number.isFinite(limitParam) && limitParam > 0 && limitParam <= 20
      ? Math.floor(limitParam)
      : DEFAULT_RESULT_LIMIT;

  const retrieval = await ACTIVE_ENGINE.search(query, limit);

  const response: SearchResponse = { retrieval, answer: null };
  return NextResponse.json(response);
}
