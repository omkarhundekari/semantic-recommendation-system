import { describe, expect, it } from "vitest";

import {
  CURRENT_WORKSPACE_SCHEMA_VERSION,
  migrateWorkspace,
  parseWorkspace,
  serializeWorkspace,
} from "./workspacePersistence";

type ReadyResult = {
  status: "ready";
  directions: unknown[];
};

const readyResult: ReadyResult = {
  status: "ready",
  directions: [],
};

describe("workspace persistence", () => {
  it("migrates an unversioned workspace with safe defaults", () => {
    const result = migrateWorkspace<ReadyResult>({
      goal: "Build a retrieval project",
      result: readyResult,
      selectedDirectionId: "retrieval",
      activeRoadmapNodeId: "define",
      completedRoadmapNodeIds: ["define"],
      savedAt: "2026-07-12T18:00:00.000Z",
    });

    expect(result).toEqual({
      schemaVersion: CURRENT_WORKSPACE_SCHEMA_VERSION,
      goal: "Build a retrieval project",
      result: readyResult,
      selectedDirectionId: "retrieval",
      activeRoadmapNodeId: "define",
      completedRoadmapNodeIds: ["define"],
      guidedStepProofs: {},
      decisionAnswers: {},
      completedGuidedStepIds: [],
      adaptationDecisions: {},
      adaptationEvidence: {},
      savedAt: "2026-07-12T18:00:00.000Z",
    });
  });

  it("preserves current adaptation state", () => {
    const result = migrateWorkspace<ReadyResult>({
      schemaVersion: 2,
      goal: "Build a retrieval project",
      result: readyResult,
      selectedDirectionId: "retrieval",
      activeRoadmapNodeId: "validate",
      completedRoadmapNodeIds: ["define"],
      guidedStepProofs: {
        "define:scope": "Saved scope.",
      },
      decisionAnswers: {
        "define:scope": "Use precision@3.",
      },
      completedGuidedStepIds: ["define:scope"],
      adaptationDecisions: {
        "validate:validation": {
          adaptationKey: "validate:validation",
          status: "accepted",
          rationale: "Use the selected metric.",
          decidedAt: "2026-07-12T18:00:00.000Z",
        },
      },
      adaptationEvidence: {
        "validate:validation": "precision@3 = 0.81",
      },
      savedAt: "2026-07-12T18:00:00.000Z",
    });

    expect(
      result?.adaptationDecisions["validate:validation"]
        .status,
    ).toBe("accepted");
    expect(
      result?.adaptationEvidence["validate:validation"],
    ).toBe("precision@3 = 0.81");
  });

  it("filters malformed collection values", () => {
    const result = migrateWorkspace<ReadyResult>({
      goal: 123,
      result: readyResult,
      completedRoadmapNodeIds: ["define", 4, null],
      guidedStepProofs: {
        valid: "proof",
        invalid: 9,
      },
      completedGuidedStepIds: "not-an-array",
      adaptationEvidence: {
        valid: "evidence",
        invalid: false,
      },
    });

    expect(result?.goal).toBe("");
    expect(result?.completedRoadmapNodeIds).toEqual([
      "define",
    ]);
    expect(result?.guidedStepProofs).toEqual({
      valid: "proof",
    });
    expect(result?.completedGuidedStepIds).toEqual([]);
    expect(result?.adaptationEvidence).toEqual({
      valid: "evidence",
    });
  });

  it("rejects missing or non-ready results", () => {
    expect(migrateWorkspace({ goal: "Missing result" })).toBeNull();

    expect(
      migrateWorkspace({
        goal: "Clarification",
        result: {
          status: "clarification_required",
        },
      }),
    ).toBeNull();
  });

  it("returns null for malformed JSON", () => {
    expect(parseWorkspace("{bad-json")).toBeNull();
    expect(parseWorkspace(null)).toBeNull();
  });

  it("serializes using the current schema version", () => {
    const raw = serializeWorkspace({
      goal: "Build a retrieval project",
      result: readyResult,
      selectedDirectionId: null,
      activeRoadmapNodeId: null,
      completedRoadmapNodeIds: [],
      guidedStepProofs: {},
      decisionAnswers: {},
      completedGuidedStepIds: [],
      adaptationDecisions: {},
      adaptationEvidence: {},
      savedAt: "2026-07-12T18:00:00.000Z",
    });

    expect(JSON.parse(raw)).toMatchObject({
      schemaVersion: CURRENT_WORKSPACE_SCHEMA_VERSION,
      goal: "Build a retrieval project",
    });
  });
});
