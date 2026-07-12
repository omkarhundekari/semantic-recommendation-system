import { describe, expect, it } from "vitest";

import type { RoadmapAdaptation } from "./roadmapAdaptationEvaluator";
import {
  adaptationKey,
  createAdaptationDecision,
  type AdaptationDecisionMap,
} from "./roadmapAdaptationState";
import {
  acceptedAdaptationsForStage,
  canCompleteMissionWithAdaptations,
  evaluateAcceptedAdaptationReadiness,
} from "./acceptedAdaptationReadiness";

const validationAdaptation: RoadmapAdaptation = {
  targetStageId: "validate",
  category: "validation",
  title: "Carry precision@3 into validation",
  rationale: "Precision@3 was selected as the primary metric.",
  suggestedTasks: [
    "Run the evaluation using precision@3.",
  ],
  suggestedAcceptanceCriteria: [
    "Save a reproducible precision@3 result.",
  ],
  suggestedValidationChecks: [
    "Verify the output includes precision@3.",
  ],
  suggestedUnlockCondition:
    "Do not complete validation until precision@3 evidence is saved.",
};

const performanceAdaptation: RoadmapAdaptation = {
  targetStageId: "validate",
  category: "performance",
  title: "Measure runtime performance",
  rationale: "The implementation includes a latency constraint.",
  suggestedTasks: [
    "Measure request latency.",
    "Run the evaluation using precision@3.",
  ],
  suggestedAcceptanceCriteria: [
    "Record representative latency results.",
  ],
  suggestedValidationChecks: [
    "Verify latency stays within the selected threshold.",
  ],
  suggestedUnlockCondition: null,
};

const scopeAdaptation: RoadmapAdaptation = {
  targetStageId: "extend",
  category: "scope",
  title: "Revisit deferred authentication",
  rationale: "Authentication was excluded from the MVP.",
  suggestedTasks: [
    "Evaluate whether authentication should be added.",
  ],
  suggestedAcceptanceCriteria: [],
  suggestedValidationChecks: [],
  suggestedUnlockCondition: null,
};

function decisionMap(
  entries: Array<{
    adaptation: RoadmapAdaptation;
    status: "accepted" | "rejected" | "deferred";
  }>,
): AdaptationDecisionMap {
  return Object.fromEntries(
    entries.map(({ adaptation, status }) => {
      const record = createAdaptationDecision({
        adaptation,
        status,
        decidedAt: "2026-07-12T12:00:00.000Z",
      });

      return [record.adaptationKey, record];
    }),
  );
}

describe("accepted adaptation readiness", () => {
  it("returns only accepted adaptations for the selected stage", () => {
    const decisions = decisionMap([
      {
        adaptation: validationAdaptation,
        status: "accepted",
      },
      {
        adaptation: performanceAdaptation,
        status: "deferred",
      },
      {
        adaptation: scopeAdaptation,
        status: "accepted",
      },
    ]);

    const result = acceptedAdaptationsForStage({
      stageId: "validate",
      adaptations: [
        validationAdaptation,
        performanceAdaptation,
        scopeAdaptation,
      ],
      decisions,
    });

    expect(result).toEqual([validationAdaptation]);
  });

  it("returns not applicable when the stage has no accepted adaptations", () => {
    const result = evaluateAcceptedAdaptationReadiness({
      stageId: "validate",
      adaptations: [validationAdaptation],
      decisions: decisionMap([
        {
          adaptation: validationAdaptation,
          status: "deferred",
        },
      ]),
      evidence: {},
    });

    expect(result).toEqual({
      status: "not_applicable",
      stageId: "validate",
      acceptedCount: 0,
      completedCount: 0,
      blockingAdaptationKeys: [],
      requiredTasks: [],
      requiredAcceptanceCriteria: [],
      requiredValidationChecks: [],
      requiredUnlockConditions: [],
      missingEvidence: [],
    });
  });

  it("blocks an accepted adaptation without saved evidence", () => {
    const key = adaptationKey(validationAdaptation);

    const result = evaluateAcceptedAdaptationReadiness({
      stageId: "validate",
      adaptations: [validationAdaptation],
      decisions: decisionMap([
        {
          adaptation: validationAdaptation,
          status: "accepted",
        },
      ]),
      evidence: {},
    });

    expect(result.status).toBe("blocked");
    expect(result.acceptedCount).toBe(1);
    expect(result.completedCount).toBe(0);
    expect(result.blockingAdaptationKeys).toEqual([key]);
    expect(result.missingEvidence).toEqual([
      "Save evidence for: Carry precision@3 into validation",
    ]);
  });

  it("becomes ready when every accepted adaptation has evidence", () => {
    const key = adaptationKey(validationAdaptation);

    const result = evaluateAcceptedAdaptationReadiness({
      stageId: "validate",
      adaptations: [validationAdaptation],
      decisions: decisionMap([
        {
          adaptation: validationAdaptation,
          status: "accepted",
        },
      ]),
      evidence: {
        [key]:
          "Evaluation report shows precision@3 = 0.81.",
      },
    });

    expect(result.status).toBe("ready");
    expect(result.completedCount).toBe(1);
    expect(result.blockingAdaptationKeys).toEqual([]);
  });

  it("keeps rejected and deferred adaptations non-blocking", () => {
    const result = evaluateAcceptedAdaptationReadiness({
      stageId: "validate",
      adaptations: [
        validationAdaptation,
        performanceAdaptation,
      ],
      decisions: decisionMap([
        {
          adaptation: validationAdaptation,
          status: "rejected",
        },
        {
          adaptation: performanceAdaptation,
          status: "deferred",
        },
      ]),
      evidence: {},
    });

    expect(result.status).toBe("not_applicable");
    expect(canCompleteMissionWithAdaptations(result)).toBe(
      true,
    );
  });

  it("deduplicates requirements across accepted adaptations", () => {
    const result = evaluateAcceptedAdaptationReadiness({
      stageId: "validate",
      adaptations: [
        validationAdaptation,
        performanceAdaptation,
      ],
      decisions: decisionMap([
        {
          adaptation: validationAdaptation,
          status: "accepted",
        },
        {
          adaptation: performanceAdaptation,
          status: "accepted",
        },
      ]),
      evidence: {},
    });

    expect(result.requiredTasks).toEqual([
      "Run the evaluation using precision@3.",
      "Measure request latency.",
    ]);
    expect(result.requiredAcceptanceCriteria).toHaveLength(2);
    expect(result.requiredValidationChecks).toHaveLength(2);
    expect(result.requiredUnlockConditions).toEqual([
      "Do not complete validation until precision@3 evidence is saved.",
    ]);
  });

  it("allows mission completion only when readiness is not blocked", () => {
    const blocked = evaluateAcceptedAdaptationReadiness({
      stageId: "validate",
      adaptations: [validationAdaptation],
      decisions: decisionMap([
        {
          adaptation: validationAdaptation,
          status: "accepted",
        },
      ]),
      evidence: {},
    });

    const ready = evaluateAcceptedAdaptationReadiness({
      stageId: "validate",
      adaptations: [validationAdaptation],
      decisions: decisionMap([
        {
          adaptation: validationAdaptation,
          status: "accepted",
        },
      ]),
      evidence: {
        [adaptationKey(validationAdaptation)]:
          "Saved evaluation output.",
      },
    });

    expect(canCompleteMissionWithAdaptations(blocked)).toBe(
      false,
    );
    expect(canCompleteMissionWithAdaptations(ready)).toBe(
      true,
    );
  });
});
