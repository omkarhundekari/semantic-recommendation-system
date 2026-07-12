import { describe, expect, it } from "vitest";

import {
  evaluateRoadmapProgress,
  type ProgressRoadmapStage,
} from "./roadmapProgressEvaluator";

const roadmap: ProgressRoadmapStage[] = [
  {
    id: "define",
    guided_steps: [
      {
        step_id: "write-scope",
        action: "Write the project scope.",
        decision_point: "Why is this metric useful?",
      },
    ],
  },
  {
    id: "mvp",
    guided_steps: [
      {
        step_id: "build-workflow",
        action: "Build the first workflow.",
      },
    ],
  },
];

function evaluate(
  overrides: Partial<
    Parameters<typeof evaluateRoadmapProgress>[0]
  > = {},
) {
  return evaluateRoadmapProgress({
    roadmap,
    completedRoadmapNodeIds: [],
    completedGuidedStepIds: [],
    guidedStepProofs: {},
    decisionAnswers: {},
    ...overrides,
  });
}

describe("evaluateRoadmapProgress", () => {
  it("returns the first guided step as the recommended next action", () => {
    const result = evaluate();

    expect(result.status).toBe("not_started");
    expect(result.currentStageId).toBe("define");
    expect(result.currentStepKey).toBe("define:write-scope");
    expect(result.recommendedNextAction).toBe(
      "Write the project scope.",
    );
    expect(result.missingRequirements).toEqual([
      "proof",
      "decision_answer",
    ]);
  });

  it("reports only the missing decision answer after proof is entered", () => {
    const result = evaluate({
      guidedStepProofs: {
        "define:write-scope": "The system receives a query.",
      },
    });

    expect(result.status).toBe("in_progress");
    expect(result.missingRequirements).toEqual([
      "decision_answer",
    ]);
  });

  it("moves to the next step after a valid step is completed", () => {
    const result = evaluate({
      completedGuidedStepIds: ["define:write-scope"],
      guidedStepProofs: {
        "define:write-scope": "The system receives a query.",
      },
      decisionAnswers: {
        "define:write-scope":
          "The metric reflects retrieval usefulness.",
      },
    });

    expect(result.status).toBe("in_progress");
    expect(result.completedStepCount).toBe(1);
    expect(result.completionRatio).toBe(0.5);
    expect(result.currentStageId).toBe("mvp");
    expect(result.currentStepKey).toBe(
      "mvp:build-workflow",
    );
    expect(result.recommendedNextAction).toBe(
      "Build the first workflow.",
    );
  });

  it("blocks stale completion when required proof is missing", () => {
    const result = evaluate({
      completedGuidedStepIds: ["define:write-scope"],
      decisionAnswers: {
        "define:write-scope":
          "The metric reflects retrieval usefulness.",
      },
    });

    expect(result.status).toBe("blocked");
    expect(result.blockedStepKeys).toEqual([
      "define:write-scope",
    ]);
  });

  it("marks the project complete when all steps and missions are complete", () => {
    const result = evaluate({
      completedRoadmapNodeIds: ["define", "mvp"],
      completedGuidedStepIds: [
        "define:write-scope",
        "mvp:build-workflow",
      ],
      guidedStepProofs: {
        "define:write-scope": "Defined input and output.",
        "mvp:build-workflow": "Produced the first result.",
      },
      decisionAnswers: {
        "define:write-scope":
          "The metric measures useful behavior.",
      },
    });

    expect(result.status).toBe("complete");
    expect(result.projectComplete).toBe(true);
    expect(result.completedStepCount).toBe(2);
    expect(result.completedMissionCount).toBe(2);
    expect(result.currentStepKey).toBeNull();
    expect(result.recommendedNextAction).toBeNull();
  });
});
