import { describe, expect, it } from "vitest";

import type { RoadmapAdaptation } from "./roadmapAdaptationEvaluator";
import {
  acceptedAdaptations,
  adaptationKey,
  clearAdaptationDecision,
  createAdaptationDecision,
  removeStaleAdaptationDecisions,
  setAdaptationDecision,
  summarizeAdaptationDecisions,
  type AdaptationDecisionMap,
} from "./roadmapAdaptationState";

const validationAdaptation: RoadmapAdaptation = {
  targetStageId: "validate",
  category: "validation",
  title: "Carry the selected metric into validation",
  rationale: "The user selected precision@3.",
  suggestedTasks: ["Run precision@3 evaluation."],
  suggestedAcceptanceCriteria: [
    "Save a precision@3 result.",
  ],
  suggestedValidationChecks: [
    "Verify the output contains precision@3.",
  ],
  suggestedUnlockCondition:
    "Do not complete validation until precision@3 is saved.",
};

const scopeAdaptation: RoadmapAdaptation = {
  targetStageId: "extend",
  category: "scope",
  title: "Revisit deferred scope",
  rationale: "Authentication was deferred.",
  suggestedTasks: ["Evaluate authentication."],
  suggestedAcceptanceCriteria: [],
  suggestedValidationChecks: [],
  suggestedUnlockCondition: null,
};

describe("roadmap adaptation state", () => {
  it("builds a stable adaptation key", () => {
    expect(adaptationKey(validationAdaptation)).toBe(
      "validate:validation",
    );
  });

  it("creates a normalized decision record", () => {
    const record = createAdaptationDecision({
      adaptation: validationAdaptation,
      status: "accepted",
      rationale: "  This metric matches the project goal.  ",
      decidedAt: "2026-07-12T10:00:00.000Z",
    });

    expect(record).toEqual({
      adaptationKey: "validate:validation",
      status: "accepted",
      rationale: "This metric matches the project goal.",
      decidedAt: "2026-07-12T10:00:00.000Z",
    });
  });

  it("adds and replaces decisions immutably", () => {
    const first = createAdaptationDecision({
      adaptation: validationAdaptation,
      status: "deferred",
      decidedAt: "2026-07-12T10:00:00.000Z",
    });
    const second = createAdaptationDecision({
      adaptation: validationAdaptation,
      status: "accepted",
      decidedAt: "2026-07-12T11:00:00.000Z",
    });

    const deferred = setAdaptationDecision({}, first);
    const accepted = setAdaptationDecision(deferred, second);

    expect(deferred["validate:validation"].status).toBe(
      "deferred",
    );
    expect(accepted["validate:validation"].status).toBe(
      "accepted",
    );
  });

  it("clears one saved decision", () => {
    const decisions: AdaptationDecisionMap = {
      "validate:validation": createAdaptationDecision({
        adaptation: validationAdaptation,
        status: "accepted",
      }),
      "extend:scope": createAdaptationDecision({
        adaptation: scopeAdaptation,
        status: "deferred",
      }),
    };

    const result = clearAdaptationDecision(
      decisions,
      "validate:validation",
    );

    expect(result["validate:validation"]).toBeUndefined();
    expect(result["extend:scope"]).toBeDefined();
  });

  it("removes decisions for adaptations that no longer exist", () => {
    const decisions: AdaptationDecisionMap = {
      "validate:validation": createAdaptationDecision({
        adaptation: validationAdaptation,
        status: "accepted",
      }),
      "extend:scope": createAdaptationDecision({
        adaptation: scopeAdaptation,
        status: "rejected",
      }),
    };

    const result = removeStaleAdaptationDecisions({
      adaptations: [validationAdaptation],
      decisions,
    });

    expect(Object.keys(result)).toEqual([
      "validate:validation",
    ]);
  });

  it("summarizes pending and decided adaptations", () => {
    const decisions: AdaptationDecisionMap = {
      "validate:validation": createAdaptationDecision({
        adaptation: validationAdaptation,
        status: "accepted",
      }),
    };

    const result = summarizeAdaptationDecisions({
      adaptations: [
        validationAdaptation,
        scopeAdaptation,
      ],
      decisions,
    });

    expect(result).toEqual({
      totalAdaptations: 2,
      pendingCount: 1,
      acceptedCount: 1,
      rejectedCount: 0,
      deferredCount: 0,
      acceptedAdaptationKeys: [
        "validate:validation",
      ],
      pendingAdaptationKeys: ["extend:scope"],
    });
  });

  it("returns only accepted roadmap adaptations", () => {
    const decisions: AdaptationDecisionMap = {
      "validate:validation": createAdaptationDecision({
        adaptation: validationAdaptation,
        status: "accepted",
      }),
      "extend:scope": createAdaptationDecision({
        adaptation: scopeAdaptation,
        status: "rejected",
      }),
    };

    const result = acceptedAdaptations({
      adaptations: [
        validationAdaptation,
        scopeAdaptation,
      ],
      decisions,
    });

    expect(result).toEqual([validationAdaptation]);
  });
});
