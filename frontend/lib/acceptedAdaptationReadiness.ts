import type { RoadmapAdaptation } from "./roadmapAdaptationEvaluator";
import {
  adaptationKey,
  type AdaptationDecisionMap,
} from "./roadmapAdaptationState";

export type AcceptedAdaptationReadinessStatus =
  | "not_applicable"
  | "blocked"
  | "ready";

export type AcceptedAdaptationReadiness = {
  status: AcceptedAdaptationReadinessStatus;
  stageId: string;
  acceptedCount: number;
  completedCount: number;
  blockingAdaptationKeys: string[];
  requiredTasks: string[];
  requiredAcceptanceCriteria: string[];
  requiredValidationChecks: string[];
  requiredUnlockConditions: string[];
  missingEvidence: string[];
};

function unique(items: string[]): string[] {
  return [...new Set(items.map((item) => item.trim()).filter(Boolean))];
}

export function acceptedAdaptationsForStage({
  stageId,
  adaptations,
  decisions,
}: {
  stageId: string;
  adaptations: RoadmapAdaptation[];
  decisions: AdaptationDecisionMap;
}): RoadmapAdaptation[] {
  return adaptations.filter((adaptation) => {
    const key = adaptationKey(adaptation);

    return (
      adaptation.targetStageId === stageId &&
      decisions[key]?.status === "accepted"
    );
  });
}

export function evaluateAcceptedAdaptationReadiness({
  stageId,
  adaptations,
  decisions,
  evidence,
}: {
  stageId: string;
  adaptations: RoadmapAdaptation[];
  decisions: AdaptationDecisionMap;
  evidence: Record<string, string>;
}): AcceptedAdaptationReadiness {
  const accepted = acceptedAdaptationsForStage({
    stageId,
    adaptations,
    decisions,
  });

  if (accepted.length === 0) {
    return {
      status: "not_applicable",
      stageId,
      acceptedCount: 0,
      completedCount: 0,
      blockingAdaptationKeys: [],
      requiredTasks: [],
      requiredAcceptanceCriteria: [],
      requiredValidationChecks: [],
      requiredUnlockConditions: [],
      missingEvidence: [],
    };
  }

  const blockingAdaptationKeys = accepted
    .map((adaptation) => adaptationKey(adaptation))
    .filter((key) => !(evidence[key] ?? "").trim());

  const completedCount =
    accepted.length - blockingAdaptationKeys.length;

  return {
    status:
      blockingAdaptationKeys.length > 0 ? "blocked" : "ready",
    stageId,
    acceptedCount: accepted.length,
    completedCount,
    blockingAdaptationKeys,
    requiredTasks: unique(
      accepted.flatMap(
        (adaptation) => adaptation.suggestedTasks,
      ),
    ),
    requiredAcceptanceCriteria: unique(
      accepted.flatMap(
        (adaptation) =>
          adaptation.suggestedAcceptanceCriteria,
      ),
    ),
    requiredValidationChecks: unique(
      accepted.flatMap(
        (adaptation) =>
          adaptation.suggestedValidationChecks,
      ),
    ),
    requiredUnlockConditions: unique(
      accepted.flatMap((adaptation) =>
        adaptation.suggestedUnlockCondition
          ? [adaptation.suggestedUnlockCondition]
          : [],
      ),
    ),
    missingEvidence: accepted
      .filter((adaptation) =>
        blockingAdaptationKeys.includes(
          adaptationKey(adaptation),
        ),
      )
      .map(
        (adaptation) =>
          `Save evidence for: ${adaptation.title}`,
      ),
  };
}

export function canCompleteMissionWithAdaptations(
  readiness: AcceptedAdaptationReadiness,
): boolean {
  return readiness.status !== "blocked";
}
