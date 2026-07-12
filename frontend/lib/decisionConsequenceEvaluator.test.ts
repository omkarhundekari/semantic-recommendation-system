import { describe, expect, it } from "vitest";

import type { DecisionEntry } from "./portfolioSummary";
import { evaluateDecisionConsequences } from "./decisionConsequenceEvaluator";

function decision(
  overrides: Partial<DecisionEntry>,
): DecisionEntry {
  return {
    missionId: "mvp",
    missionTitle: "Build the MVP",
    stepId: "build-first-workflow",
    stepTitle: "Build the first workflow",
    decisionPoint: "What did you intentionally leave out?",
    answer: "I deferred authentication until the extension phase.",
    ...overrides,
  };
}

describe("evaluateDecisionConsequences", () => {
  it("returns an empty evaluation when no decisions exist", () => {
    const result = evaluateDecisionConsequences([]);

    expect(result.decisionCount).toBe(0);
    expect(result.consequences).toEqual([]);
    expect(result.validationFocus).toEqual([]);
  });

  it("detects deferred MVP scope", () => {
    const result = evaluateDecisionConsequences([
      decision({}),
    ]);

    expect(result.deferredItems).toEqual([
      "authentication until the extension phase",
    ]);
    expect(result.consequences[0].category).toBe("scope");
    expect(
      result.consequences[0].recommendedAdjustment,
    ).toContain("outside the MVP");
  });

  it("detects explicit validation metrics", () => {
    const result = evaluateDecisionConsequences([
      decision({
        missionId: "validate",
        missionTitle: "Validate the system",
        stepId: "run-validation",
        decisionPoint: "Why did you choose this metric?",
        answer:
          "I chose precision@3 because the first three results matter most.",
      }),
    ]);

    expect(result.validationFocus).toContain("precision@3");
    expect(result.consequences[0].category).toBe("validation");
    expect(
      result.consequences[0].recommendedAdjustment,
    ).toContain("precision@3");
  });

  it("detects architecture choices", () => {
    const result = evaluateDecisionConsequences([
      decision({
        decisionPoint:
          "Why is this architecture useful?",
        answer:
          "I chose FAISS with a local index to avoid a hosted vector database.",
      }),
    ]);

    expect(result.architectureSignals).toEqual([
      "faiss",
      "local index",
      "vector database",
    ]);
    expect(result.consequences[0].category).toBe(
      "architecture",
    );
  });

  it("detects user priorities", () => {
    const result = evaluateDecisionConsequences([
      decision({
        answer:
          "I kept the design simple and used the free tier to reduce cost.",
      }),
    ]);

    expect(result.priorities).toEqual([
      "simplicity",
      "cost",
    ]);
  });

  it("preserves one consequence per captured decision", () => {
    const result = evaluateDecisionConsequences([
      decision({}),
      decision({
        missionId: "validate",
        missionTitle: "Validate the system",
        stepId: "run-validation",
        decisionPoint: "Why this metric?",
        answer: "I selected latency as the main measure.",
      }),
    ]);

    expect(result.decisionCount).toBe(2);
    expect(result.consequences).toHaveLength(2);
  });
});
