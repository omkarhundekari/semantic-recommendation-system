import type {
  EvidenceAttribution,
} from "./executionEvidenceAttributionApi";

export type RoadmapStageReference = {
  id: string;
  title: string;
};

export type RoadmapStageEvidenceCoverage = {
  stageId: string;
  stageTitle: string;
  acceptedEvidenceCount: number;
  suggestedEvidenceCount: number;
  rejectedEvidenceCount: number;
  evidenceKeys: string[];
  isCovered: boolean;
};

export type RoadmapEvidenceCoverage = {
  stageCoverage: Record<
    string,
    RoadmapStageEvidenceCoverage
  >;
  coveredStageIds: string[];
  uncoveredStageIds: string[];
  coveredStageCount: number;
  totalStageCount: number;
  coveragePercent: number;
  acceptedAttributionCount: number;
};

export function buildRoadmapEvidenceCoverage({
  roadmapStages,
  attributions,
}: {
  roadmapStages: RoadmapStageReference[];
  attributions: EvidenceAttribution[];
}): RoadmapEvidenceCoverage {
  const stageCoverage: Record<
    string,
    RoadmapStageEvidenceCoverage
  > = {};

  for (const stage of roadmapStages) {
    stageCoverage[stage.id] = {
      stageId: stage.id,
      stageTitle: stage.title,
      acceptedEvidenceCount: 0,
      suggestedEvidenceCount: 0,
      rejectedEvidenceCount: 0,
      evidenceKeys: [],
      isCovered: false,
    };
  }

  let acceptedAttributionCount = 0;

  for (const attribution of attributions) {
    const coverage =
      stageCoverage[
        attribution.roadmap_node_id
      ];

    if (!coverage) {
      continue;
    }

    if (
      attribution.status === "accepted"
    ) {
      coverage.acceptedEvidenceCount += 1;
      coverage.isCovered = true;
      coverage.evidenceKeys.push(
        attribution.evidence_key,
      );
      acceptedAttributionCount += 1;
      continue;
    }

    if (
      attribution.status === "suggested"
    ) {
      coverage.suggestedEvidenceCount += 1;
      continue;
    }

    coverage.rejectedEvidenceCount += 1;
  }

  const coveredStageIds: string[] = [];
  const uncoveredStageIds: string[] = [];

  for (const stage of roadmapStages) {
    if (
      stageCoverage[stage.id].isCovered
    ) {
      coveredStageIds.push(stage.id);
    } else {
      uncoveredStageIds.push(stage.id);
    }
  }

  const totalStageCount =
    roadmapStages.length;
  const coveredStageCount =
    coveredStageIds.length;

  return {
    stageCoverage,
    coveredStageIds,
    uncoveredStageIds,
    coveredStageCount,
    totalStageCount,
    coveragePercent:
      totalStageCount > 0
        ? Math.round(
            (coveredStageCount /
              totalStageCount) *
              100,
          )
        : 0,
    acceptedAttributionCount,
  };
}
