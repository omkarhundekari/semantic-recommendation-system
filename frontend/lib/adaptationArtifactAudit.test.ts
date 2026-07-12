import { describe, expect, it } from "vitest";

import type { RoadmapAdaptation } from "./roadmapAdaptationEvaluator";
import {
  createAdaptationDecision,
  type AdaptationDecisionMap,
} from "./roadmapAdaptationState";
import {
  buildAdaptationArtifactAudit,
  formatAdaptationArtifactEntry,
} from "./adaptationArtifactAudit";

const validationAdaptation: RoadmapAdaptation = {
  targetStageId: "validate",
  category: "validation",
  title: "Carry precision@3 into validation",
  rationale: "The metric was selected earlier.",
  suggestedTasks: ["Run precision@3 evaluation."],
  suggestedAcceptanceCriteria: [
    "Save a reproducible precision@3 result.",
  ],
  suggestedValidationChecks: [
    "Verify the output includes precision@3.",
  ],
  suggestedUnlockCondition:
    "Do not complete validation until evidence is saved.",
};

const scopeAdaptation: RoadmapAdaptation = {
  targetStageId: "extend",
  category: "scope",
  title: "Revisit deferred authentication",
  rationale: "Authentication was deferred.",
  suggestedTasks: ["Evaluate authentication."],
  suggestedAcceptanceCriteria: [],
  suggestedValidationChecks: [],
  suggestedUnlockCondition: null,
};

const securityAdaptation: RoadmapAdaptation = {
  targetStageId: "extend",
  category: "security",
  title: "Document the trust boundary",
  rationale: "The system handles external input.",
  suggestedTasks: ["Document the trust boundary."],
  suggestedAcceptanceCriteria: [],
  suggestedValidationChecks: [],
  suggestedUnlockCondition: null,
};

function decisions(
  entries: Array<{
    adaptation: RoadmapAdaptation;
    status: "accepted" | "deferred" | "rejected";
    rationale?: string;
  }>,
): AdaptationDecisionMap {
  return Object.fromEntries(
    entries.map(({ adaptation, status, rationale }) => {
      const record = createAdaptationDecision({
        adaptation,
        status,
        rationale,
        decidedAt: "2026-07-12T14:00:00.000Z",
      });

      return [record.adaptationKey, record];
    }),
  );
}

describe("adaptation artifact audit", () => {
  it("marks accepted adaptations with evidence as implemented", () => {
    const audit = buildAdaptationArtifactAudit({
      adaptations: [validationAdaptation],
      decisions: decisions([
        {
          adaptation: validationAdaptation,
          status: "accepted",
          rationale:
            "Precision@3 matches the product goal.",
        },
      ]),
      evidence: {
        "validate:validation":
          "Evaluation report shows precision@3 = 0.81.",
      },
    });

    expect(audit.implementedCount).toBe(1);
    expect(audit.acceptedMissingEvidenceCount).toBe(0);
    expect(audit.implemented[0]).toMatchObject({
      artifactStatus: "implemented",
      evidence:
        "Evaluation report shows precision@3 = 0.81.",
      rationale:
        "Precision@3 matches the product goal.",
    });
  });

  it("distinguishes accepted adaptations without evidence", () => {
    const audit = buildAdaptationArtifactAudit({
      adaptations: [validationAdaptation],
      decisions: decisions([
        {
          adaptation: validationAdaptation,
          status: "accepted",
        },
      ]),
      evidence: {},
    });

    expect(audit.implementedCount).toBe(0);
    expect(audit.acceptedMissingEvidenceCount).toBe(1);
    expect(
      audit.acceptedMissingEvidence[0].artifactStatus,
    ).toBe("accepted_missing_evidence");
  });

  it("keeps deferred and rejected adaptations auditable", () => {
    const audit = buildAdaptationArtifactAudit({
      adaptations: [
        scopeAdaptation,
        securityAdaptation,
      ],
      decisions: decisions([
        {
          adaptation: scopeAdaptation,
          status: "deferred",
          rationale: "Keep the MVP small.",
        },
        {
          adaptation: securityAdaptation,
          status: "rejected",
          rationale:
            "The current prototype uses only local trusted data.",
        },
      ]),
      evidence: {},
    });

    expect(audit.deferredCount).toBe(1);
    expect(audit.rejectedCount).toBe(1);
    expect(audit.deferred[0].rationale).toBe(
      "Keep the MVP small.",
    );
    expect(audit.rejected[0].rationale).toContain(
      "local trusted data",
    );
  });

  it("ignores adaptations without a recorded decision", () => {
    const audit = buildAdaptationArtifactAudit({
      adaptations: [
        validationAdaptation,
        scopeAdaptation,
      ],
      decisions: {},
      evidence: {},
    });

    expect(audit.totalDecided).toBe(0);
    expect(audit.entries).toEqual([]);
  });

  it("preserves implementation requirements", () => {
    const audit = buildAdaptationArtifactAudit({
      adaptations: [validationAdaptation],
      decisions: decisions([
        {
          adaptation: validationAdaptation,
          status: "accepted",
        },
      ]),
      evidence: {
        "validate:validation": "Saved result.",
      },
    });

    expect(
      audit.implemented[0].suggestedTasks,
    ).toEqual(["Run precision@3 evaluation."]);
    expect(
      audit.implemented[0].suggestedValidationChecks,
    ).toEqual([
      "Verify the output includes precision@3.",
    ]);
    expect(
      audit.implemented[0].suggestedUnlockCondition,
    ).toContain("evidence is saved");
  });

  it("formats an entry for text artifacts", () => {
    const audit = buildAdaptationArtifactAudit({
      adaptations: [validationAdaptation],
      decisions: decisions([
        {
          adaptation: validationAdaptation,
          status: "accepted",
          rationale: "Use the product metric.",
        },
      ]),
      evidence: {
        "validate:validation": "precision@3 = 0.81",
      },
    });

    const formatted = formatAdaptationArtifactEntry(
      audit.implemented[0],
    );

    expect(formatted).toContain("[validation]");
    expect(formatted).toContain("Status: implemented");
    expect(formatted).toContain(
      "Rationale: Use the product metric.",
    );
    expect(formatted).toContain(
      "Evidence: precision@3 = 0.81",
    );
  });
});
