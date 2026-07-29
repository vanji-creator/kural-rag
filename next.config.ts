import path from "node:path";

import type { NextConfig } from "next";

/**
 * data/kurals.json is imported statically by lib/corpus.ts, so the whole
 * corpus goes through the bundler once at build time and lives in the server
 * bundle. Nothing has to be read from disk at runtime, which is what makes
 * this deployable to a serverless host without any file-tracing configuration.
 */
const nextConfig: NextConfig = {
  // this repo is the root; without this, a lockfile further up the filesystem
  // can be picked instead and traces the wrong directory
  outputFileTracingRoot: path.join(__dirname),
};

export default nextConfig;
