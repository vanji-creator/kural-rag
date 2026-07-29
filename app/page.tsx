import { SearchExperience } from "@/components/SearchExperience";
import { CORPUS_SIZE } from "@/lib/corpus";
import { getDemoResponse } from "@/lib/demo";
import { ACTIVE_ENGINE } from "@/lib/retrieval";

export default async function SearchPage({
  searchParams,
}: {
  searchParams: Promise<{ demo?: string; state?: string; q?: string }>;
}) {
  const params = await searchParams;

  const demoResponse = params.demo ? getDemoResponse(params.demo) : null;
  const initialQuery = demoResponse ? "" : (params.q ?? "").trim();
  const initialPhase = demoResponse
    ? "answer"
    : params.state === "error"
      ? "error"
      : "rest";

  return (
    <SearchExperience
      engine={{
        name: ACTIVE_ENGINE.name,
        description: ACTIVE_ENGINE.description,
        highConfidence: ACTIVE_ENGINE.highConfidence,
        floor: ACTIVE_ENGINE.floor,
        calibrated: ACTIVE_ENGINE.calibrated,
      }}
      corpusSize={CORPUS_SIZE}
      initialResponse={demoResponse}
      initialPhase={initialPhase}
      initialQuery={initialQuery}
      isDemo={Boolean(demoResponse)}
    />
  );
}
