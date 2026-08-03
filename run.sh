#!/usr/bin/env bash
#
# Start the whole application with one command.
#
# WHY A SCRIPT AND NOT JUST "npm run dev"
#
# This application is two processes, and it has to be. The retrieval models
# take seconds and about a gigabyte of memory to load, so they live in a
# long-running Python process rather than being loaded per request. Next.js
# renders the pages and talks to that process over localhost.
#
# Two processes means two terminals, which means eventually starting one and
# forgetting the other and seeing the fallback engine without knowing why.
# This starts both, waits until each is genuinely ready, and stops both
# together when you press Ctrl-C.
#
#     ./run.sh
#
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

RETRIEVAL_PORT="${RETRIEVAL_PORT:-8000}"
WEB_PORT="${WEB_PORT:-3000}"

if [ ! -f .env ]; then
  echo "no .env file. The question rewriter needs a key:"
  echo "    SARVAM_API_KEY=... from https://dashboard.sarvam.ai/"
  echo "Search still works without it, but every result is DEGRADED."
fi

mkdir -p logs

# Stop both halves together. Without this, Ctrl-C kills the foreground one and
# leaves the other holding its port, and the next start fails confusingly.
cleanup() {
  echo ""
  echo "stopping both processes..."
  kill 0 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "starting the retrieval service on port $RETRIEVAL_PORT"
echo "  (loading LaBSE and the reranker - this is the slow part, once)"
venv/bin/uvicorn service.app:app --port "$RETRIEVAL_PORT" &

# Wait for it to be genuinely ready, not merely started. Starting Next.js
# first would let the first few searches quietly fall back to word overlap.
until curl -fs "http://127.0.0.1:$RETRIEVAL_PORT/health" 2>/dev/null \
      | grep -q '"status":"ready"'; do
  sleep 2
done
echo "retrieval service ready"

curl -fs "http://127.0.0.1:$RETRIEVAL_PORT/health" \
  | venv/bin/python -c "
import json, sys
health = json.load(sys.stdin)
print(f\"  engine    {health['engine']}\")
print(f\"  rewriter  {health['rewriterModel']} \"
      f\"({health['rewritesCached']} rewrites cached)\"
      if health['rewriterReady'] else
      '  rewriter  NOT AVAILABLE - searches will be degraded')
print(f\"  corpus    {health['corpusSize']} kurals\")
"

echo ""
echo "starting the web app on port $WEB_PORT"
RETRIEVAL_SERVICE_URL="http://127.0.0.1:$RETRIEVAL_PORT" \
  npx next dev -p "$WEB_PORT" &

echo ""
echo "  open      http://localhost:$WEB_PORT"
echo "  logs      logs/web.jsonl and logs/searches.jsonl"
echo "  read them venv/bin/python src/read_logs.py"
echo ""

wait
