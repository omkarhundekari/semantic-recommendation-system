import type { RoadmapAdaptation } from "./roadmapAdaptationEvaluator";

export type AdaptationDecisionStatus =
  | "accepted"
  | "rejected"
  | "deferred";

export type AdaptationDecisionRecord = {
  adaptationKey: string;
  status: AdaptationDecisionStatus;
  rationale: string;
  decidedAt: string;
};

export type AdaptationDecisionMap = Record<
  string,
  AdaptationDecisionRecord
>;

export type AdaptationDecisionSummary = {
  totalAdaptations: number;
  pendingCount: number;
  acceptedCount: number;
  rejectedCount: number;
  deferredCount: number;
  acceptedAdaptationKeys: string[];
  pendingAdaptationKeys: string[];
};

export function adaptationKey(
  adaptation: Pick<
    RoadmapAdaptation,
    "targetStageId" | "category"
  >,
): string {
  return `${adaptation.targetStageId}:${adaptation.category}`;
}

export function createAdaptationDecision({
  adaptation,
  status,
  rationale,
  decidedAt = new Date().toISOString(),
}: {
  adaptation: Pick<
    RoadmapAdaptation,
    "targetStageId" | "category"
  >;
  status: AdaptationDecisionStatus;
  rationale?: string;
  decidedAt?: string;
}): AdaptationDecisionRecord {
  return {
    adaptationKey: adaptationKey(adaptation),
    status,
    rationale: rationale?.trim() ?? "",
    decidedAt,
  };
}

export function setAdaptationDecision(
  current: AdaptationDecisionMap,
  record: AdaptationDecisionRecord,
): AdaptationDecisionMap {
  return {
    ...current,
    [record.adaptationKey]: record,
  };
}

export function clearAdaptationDecision(
  current: AdaptationDecisionMap,
  key: string,
): AdaptationDecisionMap {
  const next = { ...current };

  delete next[key];

  return next;
}

export function removeStaleAdaptationDecisions({
  adaptations,
  decisions,
}: {
  adaptations: RoadmapAdaptation[];
  decisions: AdaptationDecisionMap;
}): AdaptationDecisionMap {
  const validKeys = new Set(
    adaptations.map((adaptation) =>
      adaptationKey(adaptation),
    ),
  );

  return Object.fromEntries(
    Object.entries(decisions).filter(([key]) =>
      validKeys.has(key),
    ),
  );
}

export function summarizeAdaptationDecisions({
  adaptations,
  decisions,
}: {
  adaptations: RoadmapAdaptation[];
  decisions: AdaptationDecisionMap;
}): AdaptationDecisionSummary {
  const keys = adaptations.map((adaptation) =>
    adaptationKey(adaptation),
  );

  const acceptedAdaptationKeys = keys.filter(
    (key) => decisions[key]?.status === "accepted",
  );
  const rejectedCount = keys.filter(
    (key) => decisions[key]?.status === "rejected",
  ).length;
  const deferredCount = keys.filter(
    (key) => decisions[key]?.status === "deferred",
  ).length;
  const pendingAdaptationKeys = keys.filter(
    (key) => !decisions[key],
  );

  return {
    totalAdaptations: keys.length,
    pendingCount: pendingAdaptationKeys.length,
    acceptedCount: acceptedAdaptationKeys.length,
    rejectedCount,
    deferredCount,
    acceptedAdaptationKeys,
    pendingAdaptationKeys,
  };
}

export function acceptedAdaptations({
  adaptations,
  decisions,
}: {
  adaptations: RoadmapAdaptation[];
  decisions: AdaptationDecisionMap;
}): RoadmapAdaptation[] {
  return adaptations.filter(
    (adaptation) =>
      decisions[adaptationKey(adaptation)]?.status ===
      "accepted",
  );
}
