import { describe, expect, it } from "vitest";

import type {
  DecisionConsequenceEvaluation,
} from "./decisionConsequenceEvaluator";
import {
  evaluateRoadmapAdaptations,
  type AdaptableRoadmapStage,
} from "./roadmapAdaptationEvaluator";

const roadmap: AdaptableRoadmapStage[] = [
  {
    id: "define",
    title: "Define the system",
  },
  {
    id: "mvp",
    title: "Build the MVP",
  },
  {
    id: "validate",
    title: "Validate the system",
  },
  {
    id: "extend",
    title: "Extend the system",
  },
  {
    id: "package",
    title: "Package the project",
  },
];

function consequences(
  overrides: Partial<DecisionConsequenceEvaluation> = {},
): DecisionConsequenceEvaluation {
  return {
    decisionCount: 0,
    consequences: [],
    validationFocus: [],
    deferredItems: [],
    architectureSignals: [],
    priorities: [],
    ...overrides,
  };
}

describe("evaluateRoadmapAdaptations", () => {
  it("returns no adaptations without roadmap stages", () => {
    const result = evaluateRoadmapAdaptations({
      roadmap: [],
      decisionConsequences: consequences({
        validationFocus: ["precision@3"],
      }),
    });

    expect(result).toEqual({
      adaptationCount: 0,
      affectedStageIds: [],
      adaptations: [],
    });
  });

  it("adds the selected metric to the validation mission", () => {
    const result = evaluateRoadmapAdaptations({
      roadmap,
      decisionConsequences: consequences({
        validationFocus: ["precision@3"],
      }),
    });

    const adaptation = result.adaptations.find(
      (item) => item.category === "validation",
    );

    expect(adaptation?.targetStageId).toBe("validate");
    expect(adaptation?.suggestedValidationChecks).toContain(
      "Verify that the evaluation output contains precision@3.",
    );
    expect(adaptation?.suggestedUnlockCondition).toContain(
      "precision@3",
    );
  });

  it("moves deferred scope into the extension mission", () => {
    const result = evaluateRoadmapAdaptations({
      roadmap,
      decisionConsequences: consequences({
        deferredItems: [
          "authentication until the extension phase",
        ],
      }),
    });

    const adaptation = result.adaptations.find(
      (item) => item.category === "scope",
    );

    expect(adaptation?.targetStageId).toBe("extend");
    expect(adaptation?.suggestedTasks[0]).toContain(
      "authentication until the extension phase",
    );
  });

  it("adds architecture persistence and recovery checks", () => {
    const result = evaluateRoadmapAdaptations({
      roadmap,
      decisionConsequences: consequences({
        architectureSignals: ["faiss", "local index"],
      }),
    });

    const adaptation = result.adaptations.find(
      (item) => item.category === "architecture",
    );

    expect(adaptation?.targetStageId).toBe("mvp");
    expect(adaptation?.suggestedValidationChecks[0]).toContain(
      "persistence, reload, and failure behavior",
    );
    expect(adaptation?.suggestedValidationChecks[0]).toContain(
      "faiss, local index",
    );
  });

  it("adds performance, cost, and simplicity adaptations", () => {
    const result = evaluateRoadmapAdaptations({
      roadmap,
      decisionConsequences: consequences({
        priorities: ["performance", "cost", "simplicity"],
      }),
    });

    expect(
      result.adaptations.map((item) => item.category),
    ).toEqual(
      expect.arrayContaining([
        "performance",
        "cost",
        "simplicity",
      ]),
    );
    expect(result.affectedStageIds).toEqual(
      expect.arrayContaining(["mvp", "validate", "package"]),
    );
  });

  it("adds security follow-up when a security consequence exists", () => {
    const result = evaluateRoadmapAdaptations({
      roadmap,
      decisionConsequences: consequences({
        consequences: [
          {
            missionId: "mvp",
            stepId: "choose-auth",
            category: "security",
            summary: "Authentication was deferred.",
            recommendedAdjustment:
              "Add a later security validation step.",
          },
        ],
      }),
    });

    const adaptation = result.adaptations.find(
      (item) => item.category === "security",
    );

    expect(adaptation?.targetStageId).toBe("extend");
    expect(adaptation?.suggestedValidationChecks).toContain(
      "Test one unauthorized or invalid-access scenario.",
    );
  });
});
