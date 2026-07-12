import { describe, expect, it } from "vitest";

import type {
  PersistedWorkspace,
} from "./workspacePersistence";
import {
  sanitizeWorkspaceReferences,
  type SanitizableWorkspaceResult,
} from "./workspaceReferenceSanitizer";

type TestResult = SanitizableWorkspaceResult & {
  status: "ready";
};

function createWorkspace(): PersistedWorkspace<TestResult> {
  return {
    schemaVersion: 2,
    goal: "Build a grounded retrieval system",
    result: {
      status: "ready",
      directions: [
        {
          id: "retrieval",
          roadmap: [
            {
              id: "define",
              guided_steps: [
                {
                  step_id: "scope",
                },
              ],
            },
            {
              id: "validate",
              guided_steps: [
                {
                  step_id: "measure",
                },
              ],
            },
          ],
        },
        {
          id: "classifier",
          roadmap: [
            {
              id: "train",
              guided_steps: [
                {
                  step_id: "baseline",
                },
              ],
            },
          ],
        },
      ],
    },
    selectedDirectionId: "retrieval",
    activeRoadmapNodeId: "validate",
    completedRoadmapNodeIds: ["define"],
    guidedStepProofs: {
      "define:scope": "Saved project scope.",
    },
    decisionAnswers: {
      "define:scope": "Use precision at three.",
    },
    completedGuidedStepIds: ["define:scope"],
    adaptationDecisions: {
      "validate:validation": {
        adaptationKey: "validate:validation",
        status: "accepted",
        rationale: "",
        decidedAt: "2026-07-12T18:00:00.000Z",
      },
    },
    adaptationEvidence: {
      "validate:validation": "Saved evaluation output.",
    },
    savedAt: "2026-07-12T18:00:00.000Z",
  };
}

describe("workspace reference sanitization", () => {
  it("preserves valid references for the selected direction", () => {
    expect(
      sanitizeWorkspaceReferences(createWorkspace()),
    ).toEqual(createWorkspace());
  });

  it("clears roadmap state when the selected direction is stale", () => {
    const workspace = createWorkspace();

    workspace.selectedDirectionId = "removed-direction";

    const result = sanitizeWorkspaceReferences(workspace);

    expect(result.selectedDirectionId).toBeNull();
    expect(result.activeRoadmapNodeId).toBeNull();
    expect(result.completedRoadmapNodeIds).toEqual([]);
    expect(result.guidedStepProofs).toEqual({});
    expect(result.decisionAnswers).toEqual({});
    expect(result.completedGuidedStepIds).toEqual([]);
    expect(result.adaptationDecisions).toEqual({});
    expect(result.adaptationEvidence).toEqual({});
  });

  it("removes roadmap stage IDs from another direction", () => {
    const workspace = createWorkspace();

    workspace.activeRoadmapNodeId = "train";
    workspace.completedRoadmapNodeIds = [
      "define",
      "train",
      "removed-stage",
    ];

    const result = sanitizeWorkspaceReferences(workspace);

    expect(result.activeRoadmapNodeId).toBeNull();
    expect(result.completedRoadmapNodeIds).toEqual([
      "define",
    ]);
  });

  it("removes stale guided-step state", () => {
    const workspace = createWorkspace();

    workspace.guidedStepProofs["train:baseline"] =
      "Proof from another direction.";
    workspace.guidedStepProofs["define:removed"] =
      "Proof from a removed step.";
    workspace.decisionAnswers["removed:decision"] =
      "Stale decision.";
    workspace.completedGuidedStepIds.push(
      "train:baseline",
      "validate:removed",
    );

    const result = sanitizeWorkspaceReferences(workspace);

    expect(result.guidedStepProofs).toEqual({
      "define:scope": "Saved project scope.",
    });
    expect(result.decisionAnswers).toEqual({
      "define:scope": "Use precision at three.",
    });
    expect(result.completedGuidedStepIds).toEqual([
      "define:scope",
    ]);
  });

  it("removes malformed and stale adaptation decisions", () => {
    const workspace = createWorkspace();

    workspace.adaptationDecisions["train:security"] = {
      adaptationKey: "train:security",
      status: "deferred",
      rationale: "",
      decidedAt: "2026-07-12T18:00:00.000Z",
    };
    workspace.adaptationDecisions["validate:unknown"] = {
      adaptationKey: "validate:unknown",
      status: "accepted",
      rationale: "",
      decidedAt: "2026-07-12T18:00:00.000Z",
    };
    workspace.adaptationDecisions["define:scope"] = {
      adaptationKey: "wrong:key",
      status: "rejected",
      rationale: "Not needed.",
      decidedAt: "2026-07-12T18:00:00.000Z",
    };

    const result = sanitizeWorkspaceReferences(workspace);

    expect(result.adaptationDecisions).toEqual({
      "validate:validation":
        workspace.adaptationDecisions[
          "validate:validation"
        ],
    });
  });

  it("keeps evidence only for valid adaptation decisions", () => {
    const workspace = createWorkspace();

    workspace.adaptationEvidence["define:scope"] =
      "Stale adaptation evidence.";
    workspace.adaptationEvidence["validate:security"] =
      "Evidence without a decision.";

    const result = sanitizeWorkspaceReferences(workspace);

    expect(result.adaptationEvidence).toEqual({
      "validate:validation": "Saved evaluation output.",
    });
  });
});
