/**
 * ============================================================================
 * THE WEB APP'S LOG. One line of JSON per request.
 * ============================================================================
 *
 * The Python service already writes down what IT did — the rewrite, the
 * scores, which stage was slow. This file writes down what the WEB APP did:
 * that a request arrived, what was asked, what came back, how long the reader
 * actually waited, and whether the answer came from the real engine or the
 * fallback.
 *
 * Both sides write the same `requestId`, and that is the whole point. One
 * question produces one line here and one line there, and the two join on
 * that id. Without it you can see a slow request in one file and have no way
 * to find its other half.
 *
 * WHY THE READER'S TIME IS MEASURED HERE AND NOT THERE
 *
 * The Python service reports how long IT took. That number leaves out the
 * network hop, so it is always smaller than what a person experiences. The
 * only honest place to measure waiting is the place that does the waiting.
 *
 * WHERE IT GOES
 *
 * To a file under logs/ when there is a writable disk, and to the console
 * always. Hosts like Vercel give a read-only filesystem and collect the
 * console instead, so writing to a file is attempted and never depended on.
 *
 * WHAT NEVER GOES IN
 *
 * No API key ever reaches this process — the browser talks to Next.js, Next.js
 * talks to the Python service, and only the Python service holds a key. That
 * is a design choice, not an accident: a secret that never arrives cannot leak.
 *
 * Real questions from real people DO go in. That makes logs/ private data.
 * It is in .gitignore and must stay there.
 */

import { appendFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { randomUUID } from "node:crypto";

const LOG_DIRECTORY = process.env.LOG_DIRECTORY ?? join(process.cwd(), "logs");
const WEB_LOG_PATH = join(LOG_DIRECTORY, "web.jsonl");

/** Set false to silence the console but keep the file. */
const LOG_TO_CONSOLE = process.env.LOG_TO_CONSOLE !== "false";

/**
 * After the first failed write we stop trying. On a read-only host every
 * request would otherwise pay for a filesystem error it can do nothing about.
 */
let fileWritingWorks = true;

/** A short id for one question's journey through the whole system. */
export function newRequestId(): string {
  return randomUUID().replace(/-/g, "").slice(0, 12);
}

export type LogEvent = Record<string, unknown> & { event: string };

/** Append one event. Never throws — a logger must not break the request. */
export function record(event: LogEvent): void {
  const line = { time: new Date().toISOString(), ...event };
  const text = JSON.stringify(line);

  if (LOG_TO_CONSOLE) {
    console.log(`[kural] ${text}`);
  }

  if (!fileWritingWorks) return;
  try {
    mkdirSync(LOG_DIRECTORY, { recursive: true });
    appendFileSync(WEB_LOG_PATH, `${text}\n`, "utf8");
  } catch {
    // Read-only disk, most likely. Say so once, then stop trying.
    fileWritingWorks = false;
    if (LOG_TO_CONSOLE) {
      console.warn(
        `[kural] cannot write ${WEB_LOG_PATH}; logging to the console only`,
      );
    }
  }
}

/** What one finished search looked like from the web app's side. */
export function recordSearch(fields: {
  requestId: string;
  query: string;
  limit: number;
  engine: string;
  resultCount: number;
  topScore: number;
  confidence: string;
  /** measured here, so it includes the wait the reader really experienced */
  waitedMs: number;
  /** true when the answer did NOT come from the full pipeline */
  degraded: boolean;
}): void {
  record({ event: "search", ...fields });
}

/** Something failed. Written down rather than only thrown. */
export function recordError(fields: {
  requestId: string;
  whatFailed: string;
  message: string;
  query?: string;
}): void {
  record({ event: "error", ...fields });
}
