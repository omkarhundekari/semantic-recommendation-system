import type { RoadmapAdaptation } from "./roadmapAdaptationEvaluator";
import {
  adaptationKey,
  type AdaptationDecisionMap,
  type AdaptationDecisionStatus,
} from "./roadmapAdaptationState";

export type AdaptationArtifactStatus =
  | "implemented"
  | "accepted_missing_evidence"
  | "deferred"
  | "rejected";

export type AdaptationArtifactEntry = {
  adaptationKey: string;
  stageId: string;
  category: RoadmapAdaptation["category"];
  title: string;
  rationale: string;
  decisionStatus: AdaptationDecisionStatus;
  artifactStatus: AdaptationArtifactStatus;
  evidence: string;
  suggestedTasks: string[];
  suggestedAcceptanceCriteria: string[];
  suggestedValidationChecks: string[];
  suggestedUnlockCondition: string | null;
};

export type AdaptationArtifactAudit = {
  totalDecided: number;
  implementedCount: number;
  acceptedMissingEvidenceCount: number;
  deferredCount: number;
  rejectedCount: number;
  entries: AdaptationArtifactEntry[];
  implemented: AdaptationArtifactEntry[];
  acceptedMissingEvidence: AdaptationArtifactEntry[];
  deferred: AdaptationArtifactEntry[];
  rejected: AdaptationArtifactEntry[];
};

function artifactStatus({
  decisionStatus,
  evidence,
}: {
  decisionStatus: AdaptationDecisionStatus;
  evidence: string;
}): AdaptationArtifactStatus {
  if (decisionStatus === "accepted") {
    return evidence.trim()
      ? "implemented"
      : "accepted_missing_evidence";
  }

  return decisionStatus;
}

export function buildAdaptationArtifactAudit({
  adaptations,
  decisions,
  evidence,
}: {
  adaptations: RoadmapAdaptation[];
  decisions: AdaptationDecisionMap;
  evidence: Record<string, string>;
}): AdaptationArtifactAudit {
  const entries = adaptations.flatMap((adaptation) => {
    const key = adaptationKey(adaptation);
    const decision = decisions[key];

    if (!decision) {
      return [];
    }

    const savedEvidence = evidence[key]?.trim() ?? "";

    return [
      {
        adaptationKey: key,
        stageId: adaptation.targetStageId,
        category: adaptation.category,
        title: adaptation.title,
        rationale: decision.rationale,
        decisionStatus: decision.status,
        artifactStatus: artifactStatus({
          decisionStatus: decision.status,
          evidence: savedEvidence,
        }),
        evidence: savedEvidence,
        suggestedTasks: adaptation.suggestedTasks,
        suggestedAcceptanceCriteria:
          adaptation.suggestedAcceptanceCriteria,
        suggestedValidationChecks:
          adaptation.suggestedValidationChecks,
        suggestedUnlockCondition:
          adaptation.suggestedUnlockCondition,
      },
    ];
  });

  const implemented = entries.filter(
    (entry) => entry.artifactStatus === "implemented",
  );
  const acceptedMissingEvidence = entries.filter(
    (entry) =>
      entry.artifactStatus === "accepted_missing_evidence",
  );
  const deferred = entries.filter(
    (entry) => entry.artifactStatus === "deferred",
  );
  const rejected = entries.filter(
    (entry) => entry.artifactStatus === "rejected",
  );

  return {
    totalDecided: entries.length,
    implementedCount: implemented.length,
    acceptedMissingEvidenceCount:
      acceptedMissingEvidence.length,
    deferredCount: deferred.length,
    rejectedCount: rejected.length,
    entries,
    implemented,
    acceptedMissingEvidence,
    deferred,
    rejected,
  };
}

export function formatAdaptationArtifactEntry(
  entry: AdaptationArtifactEntry,
): string {
  const parts = [
    `[${entry.category}] ${entry.title}`,
    `Status: ${entry.artifactStatus.replaceAll("_", " ")}`,
  ];

  if (entry.rationale) {
    parts.push(`Rationale: ${entry.rationale}`);
  }

  if (entry.evidence) {
    parts.push(`Evidence: ${entry.evidence}`);
  }

  return parts.join(" | ");
}
