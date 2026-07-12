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
        expected_output_patterns: ["input", "output"],
      },
    ],
  },
  {
    id: "mvp",
    guided_steps: [
      {
        step_id: "build-workflow",
        action: "Build the first workflow.",
        expected_output_patterns: [],
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
  it("reports missing proof and decision reasoning", () => {
    const result = evaluate();

    expect(result.status).toBe("not_started");
    expect(result.currentStepKey).toBe("define:write-scope");
    expect(result.missingRequirements).toEqual([
      "proof",
      "decision_answer",
    ]);
    expect(result.currentProofStatus).toBe("empty");
  });

  it("reports proof that misses expected evidence", () => {
    const result = evaluate({
      guidedStepProofs: {
        "define:write-scope": "I described the project.",
      },
      decisionAnswers: {
        "define:write-scope": "The metric is useful.",
      },
    });

    expect(result.status).toBe("in_progress");
    expect(result.currentProofStatus).toBe(
      "missing_expected_pattern",
    );
    expect(result.missingRequirements).toEqual([
      "proof_expected_pattern",
    ]);
    expect(result.missingProofPatterns).toEqual([
      "input",
      "output",
    ]);
  });

  it("reports only a missing decision after valid proof", () => {
    const result = evaluate({
      guidedStepProofs: {
        "define:write-scope":
          "The input is a query and the output is a ranked result.",
      },
    });

    expect(result.currentProofStatus).toBe("accepted");
    expect(result.missingRequirements).toEqual([
      "decision_answer",
    ]);
  });

  it("moves to the next step after valid completion", () => {
    const result = evaluate({
      completedGuidedStepIds: ["define:write-scope"],
      guidedStepProofs: {
        "define:write-scope":
          "The input is a query and the output is a ranked result.",
      },
      decisionAnswers: {
        "define:write-scope":
          "The metric reflects retrieval usefulness.",
      },
    });

    expect(result.completedStepCount).toBe(1);
    expect(result.currentStepKey).toBe(
      "mvp:build-workflow",
    );
    expect(result.currentProofStatus).toBe("empty");
  });

  it("accepts detailed proof when no patterns are configured", () => {
    const result = evaluate({
      completedGuidedStepIds: ["define:write-scope"],
      guidedStepProofs: {
        "define:write-scope":
          "The input is a query and the output is a ranked result.",
        "mvp:build-workflow":
          "The workflow produced the first saved result.",
      },
      decisionAnswers: {
        "define:write-scope":
          "The metric reflects retrieval usefulness.",
      },
    });

    expect(result.currentStepKey).toBe(
      "mvp:build-workflow",
    );
    expect(result.currentProofStatus).toBe("needs_detail");
    expect(result.missingRequirements).toEqual([]);
  });

  it("blocks stale completion when proof quality is invalid", () => {
    const result = evaluate({
      completedGuidedStepIds: ["define:write-scope"],
      guidedStepProofs: {
        "define:write-scope": "Finished it.",
      },
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

  it("marks the complete project only when all saved proof remains valid", () => {
    const result = evaluate({
      completedRoadmapNodeIds: ["define", "mvp"],
      completedGuidedStepIds: [
        "define:write-scope",
        "mvp:build-workflow",
      ],
      guidedStepProofs: {
        "define:write-scope":
          "The input is a query and the output is a ranked result.",
        "mvp:build-workflow":
          "The workflow produced the first saved result.",
      },
      decisionAnswers: {
        "define:write-scope":
          "The metric measures useful retrieval behavior.",
      },
    });

    expect(result.status).toBe("complete");
    expect(result.projectComplete).toBe(true);
    expect(result.blockedStepKeys).toEqual([]);
  });
});
