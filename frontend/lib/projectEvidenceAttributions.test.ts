import {
  describe,
  expect,
  it,
} from "vitest";

import type {
  EvidenceAttribution,
} from "./executionEvidenceApi";
import {
  selectProjectEvidenceAttributions,
} from "./projectEvidenceAttributions";

function attribution({
  attributionId,
  projectDirectionId,
  evidenceKey,
}: {
  attributionId: string | null;
  projectDirectionId: string | null;
  evidenceKey: string;
}): EvidenceAttribution {
  return {
    attribution_id: attributionId,
    project_direction_id:
      projectDirectionId,
    evidence_key: evidenceKey,
    roadmap_node_id: "build-mvp",
    source: "manual",
    confidence: 1,
    rationale: "",
    status: "accepted",
    decided_at:
      "2026-07-14T12:00:00+00:00",
  };
}

describe("project evidence attribution selection", () => {
  const attributions = [
    attribution({
      attributionId: "attribution-one",
      projectDirectionId: "project-one",
      evidenceKey: "commit:one",
    }),
    attribution({
      attributionId: "attribution-two",
      projectDirectionId: "project-two",
      evidenceKey: "commit:two",
    }),
    attribution({
      attributionId: null,
      projectDirectionId: null,
      evidenceKey: "commit:legacy",
    }),
  ];

  it("returns only the selected project scope", () => {
    expect(
      selectProjectEvidenceAttributions({
        attributions,
        projectDirectionId: "project-two",
      }),
    ).toEqual([attributions[1]]);
  });

  it("excludes legacy attributions", () => {
    expect(
      selectProjectEvidenceAttributions({
        attributions,
        projectDirectionId: "project-one",
      }),
    ).not.toContain(attributions[2]);
  });

  it("returns no trusted records without project identity", () => {
    expect(
      selectProjectEvidenceAttributions({
        attributions,
        projectDirectionId: null,
      }),
    ).toEqual([]);

    expect(
      selectProjectEvidenceAttributions({
        attributions,
        projectDirectionId: " ",
      }),
    ).toEqual([]);
  });

  it("does not mutate the aggregate", () => {
    const original = [...attributions];

    selectProjectEvidenceAttributions({
      attributions,
      projectDirectionId: "project-one",
    });

    expect(attributions).toEqual(original);
  });
});
