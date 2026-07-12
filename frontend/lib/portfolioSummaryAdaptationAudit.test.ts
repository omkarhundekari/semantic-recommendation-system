import { describe, expect, it } from "vitest";

import {
  buildResumeReadyParagraph,
  formatPortfolioSummaryText,
  generatePortfolioSummary,
  type PortfolioWorkspaceLike,
} from "./portfolioSummary";
import { createAdaptationDecision } from "./roadmapAdaptationState";
import type { RoadmapAdaptation } from "./roadmapAdaptationEvaluator";

const validationAdaptation: RoadmapAdaptation = {
  targetStageId: "validate",
  category: "validation",
  title: "Carry precision@3 into validation",
  rationale: "The selected metric should appear in validation.",
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

function buildWorkspace({
  status,
  evidence,
}: {
  status: "accepted" | "deferred" | "rejected";
  evidence?: string;
}): PortfolioWorkspaceLike {
  const decision = createAdaptationDecision({
    adaptation: validationAdaptation,
    status,
    rationale:
      status === "rejected"
        ? "This metric does not match the product goal."
        : "Precision@3 matches the product goal.",
    decidedAt: "2026-07-12T16:00:00.000Z",
  });

  return {
    goal: "Build a grounded retrieval system",
    selectedDirectionId: "retrieval-project",
    completedRoadmapNodeIds: ["define"],
    completedGuidedStepIds: ["define:choose-metric"],
    guidedStepProofs: {
      "define:choose-metric":
        "Saved the evaluation plan.",
    },
    decisionAnswers: {
      "define:choose-metric":
        "I chose precision@3 because the top three results matter most.",
    },
    adaptationDecisions: {
      [decision.adaptationKey]: decision,
    },
    adaptationEvidence: evidence
      ? {
          [decision.adaptationKey]: evidence,
        }
      : {},
    result: {
      resolved_planning_domain: "rag_llm",
      evidence_coverage: {
        label: "Strong direct evidence",
        coverage_state: "strong_direct",
        user_message: "Direct research support is available.",
        warnings: [],
      },
      directions: [
        {
          id: "retrieval-project",
          title: "Grounded Retrieval System",
          summary: "A retrieval-focused project.",
          roadmap: [
            {
              id: "define",
              title: "Define the system",
              purpose: "Choose the project boundary.",
              guided_steps: [
                {
                  step_id: "choose-metric",
                  title: "Choose the primary metric",
                  decision_point:
                    "Which metric should guide validation?",
                },
              ],
            },
            {
              id: "validate",
              title: "Validate the system",
              purpose: "Evaluate retrieval quality.",
              validation_checks: [
                "Confirm evaluation output is reproducible.",
              ],
            },
          ],
          verification: {
            status: "passed",
            issues: [],
          },
        },
      ],
    },
  };
}

describe("portfolio summary adaptation audit", () => {
  it("includes implemented adaptations with evidence", () => {
    const summary = generatePortfolioSummary(
      buildWorkspace({
        status: "accepted",
        evidence:
          "Evaluation report shows precision@3 = 0.81.",
      }),
    );

    expect(summary?.adaptationAudit.implementedCount).toBe(1);
    expect(summary?.adaptationAudit.implemented[0].evidence).toContain(
      "precision@3 = 0.81",
    );
  });

  it("shows accepted adaptations that still lack evidence", () => {
    const summary = generatePortfolioSummary(
      buildWorkspace({
        status: "accepted",
      }),
    );

    expect(
      summary?.adaptationAudit.acceptedMissingEvidenceCount,
    ).toBe(1);
  });

  it("preserves deferred and rejected adaptation decisions", () => {
    const deferred = generatePortfolioSummary(
      buildWorkspace({
        status: "deferred",
      }),
    );
    const rejected = generatePortfolioSummary(
      buildWorkspace({
        status: "rejected",
      }),
    );

    expect(deferred?.adaptationAudit.deferredCount).toBe(1);
    expect(rejected?.adaptationAudit.rejectedCount).toBe(1);
    expect(rejected?.adaptationAudit.rejected[0].rationale).toContain(
      "does not match",
    );
  });

  it("exports the audit in formatted portfolio text", () => {
    const summary = generatePortfolioSummary(
      buildWorkspace({
        status: "accepted",
        evidence:
          "Evaluation report shows precision@3 = 0.81.",
      }),
    );

    if (!summary) {
      throw new Error("Expected portfolio summary.");
    }

    const formatted = formatPortfolioSummaryText(summary);

    expect(formatted).toContain("Roadmap adaptation audit:");
    expect(formatted).toContain("Implemented adaptations:");
    expect(formatted).toContain("precision@3 = 0.81");
  });

  it("mentions implemented decision-driven adjustments in resume text", () => {
    const summary = generatePortfolioSummary(
      buildWorkspace({
        status: "accepted",
        evidence:
          "Evaluation report shows precision@3 = 0.81.",
      }),
    );

    if (!summary) {
      throw new Error("Expected portfolio summary.");
    }

    expect(buildResumeReadyParagraph(summary)).toContain(
      "implemented 1 decision-driven roadmap adjustment",
    );
  });
});
