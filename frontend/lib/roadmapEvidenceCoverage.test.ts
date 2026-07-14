import {
  describe,
  expect,
  it,
} from "vitest";

import type {
  EvidenceAttribution,
} from "./executionEvidenceAttributionApi";
import {
  buildRoadmapEvidenceCoverage,
} from "./roadmapEvidenceCoverage";

const STAGES = [
  {
    id: "define",
    title: "Define the system",
  },
  {
    id: "build",
    title: "Build the MVP",
  },
  {
    id: "validate",
    title: "Validate the system",
  },
];

function attribution({
  evidenceKey,
  stageId,
  status = "accepted",
}: {
  evidenceKey: string;
  stageId: string;
  status?:
    | "suggested"
    | "accepted"
    | "rejected";
}): EvidenceAttribution {
  return {
    attribution_id: null,
    project_direction_id: null,
    evidence_key: evidenceKey,
    roadmap_node_id: stageId,
    source: "manual",
    confidence: 1,
    rationale: "",
    status,
    decided_at:
      "2026-07-13T12:00:00+00:00",
  };
}

describe("roadmap evidence coverage", () => {
  it("indexes accepted evidence by roadmap stage", () => {
    const result =
      buildRoadmapEvidenceCoverage({
        roadmapStages: STAGES,
        attributions: [
          attribution({
            evidenceKey: "commit:1",
            stageId: "build",
          }),
          attribution({
            evidenceKey: "commit:2",
            stageId: "build",
          }),
          attribution({
            evidenceKey: "workflow:1",
            stageId: "validate",
          }),
        ],
      });

    expect(
      result.stageCoverage.build
        .acceptedEvidenceCount,
    ).toBe(2);
    expect(
      result.stageCoverage.build
        .evidenceKeys,
    ).toEqual([
      "commit:1",
      "commit:2",
    ]);
    expect(
      result.stageCoverage.validate
        .acceptedEvidenceCount,
    ).toBe(1);
  });

  it("reports covered and uncovered stages", () => {
    const result =
      buildRoadmapEvidenceCoverage({
        roadmapStages: STAGES,
        attributions: [
          attribution({
            evidenceKey: "commit:1",
            stageId: "build",
          }),
        ],
      });

    expect(
      result.coveredStageIds,
    ).toEqual(["build"]);
    expect(
      result.uncoveredStageIds,
    ).toEqual([
      "define",
      "validate",
    ]);
    expect(
      result.coveragePercent,
    ).toBe(33);
  });

  it("does not count suggested or rejected links as coverage", () => {
    const result =
      buildRoadmapEvidenceCoverage({
        roadmapStages: STAGES,
        attributions: [
          attribution({
            evidenceKey: "commit:1",
            stageId: "define",
            status: "suggested",
          }),
          attribution({
            evidenceKey: "commit:2",
            stageId: "validate",
            status: "rejected",
          }),
        ],
      });

    expect(
      result.coveredStageCount,
    ).toBe(0);
    expect(
      result.stageCoverage.define
        .suggestedEvidenceCount,
    ).toBe(1);
    expect(
      result.stageCoverage.validate
        .rejectedEvidenceCount,
    ).toBe(1);
  });

  it("ignores attributions for roadmap stages that are not present", () => {
    const result =
      buildRoadmapEvidenceCoverage({
        roadmapStages: STAGES,
        attributions: [
          attribution({
            evidenceKey: "commit:1",
            stageId: "removed-stage",
          }),
        ],
      });

    expect(
      result.acceptedAttributionCount,
    ).toBe(0);
    expect(
      result.coveredStageCount,
    ).toBe(0);
  });

  it("returns zero coverage for an empty roadmap", () => {
    const result =
      buildRoadmapEvidenceCoverage({
        roadmapStages: [],
        attributions: [],
      });

    expect(result).toEqual({
      stageCoverage: {},
      coveredStageIds: [],
      uncoveredStageIds: [],
      coveredStageCount: 0,
      totalStageCount: 0,
      coveragePercent: 0,
      acceptedAttributionCount: 0,
    });
  });
});
