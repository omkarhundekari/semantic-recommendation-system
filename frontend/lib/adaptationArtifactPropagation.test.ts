import { describe, expect, it } from "vitest";

import { buildPassport } from "./buildPassport";
import {
  buildInterviewStory,
  formatInterviewStoryText,
} from "./interviewStory";
import {
  generatePortfolioSummary,
  type PortfolioWorkspaceLike,
} from "./portfolioSummary";
import { buildReadmeOutline } from "./readmeOutline";
import type { RoadmapAdaptation } from "./roadmapAdaptationEvaluator";
import { createAdaptationDecision } from "./roadmapAdaptationState";

const adaptation: RoadmapAdaptation = {
  targetStageId: "validate",
  category: "validation",
  title: "Carry precision@3 into validation",
  rationale: "Use the selected product metric.",
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

function buildSummary({
  status,
  evidence,
}: {
  status: "accepted" | "deferred" | "rejected";
  evidence?: string;
}) {
  const decision = createAdaptationDecision({
    adaptation,
    status,
    rationale:
      status === "rejected"
        ? "The selected metric does not match the product goal."
        : "Precision@3 matches the product goal.",
    decidedAt: "2026-07-12T17:00:00.000Z",
  });

  const workspace: PortfolioWorkspaceLike = {
    goal: "Build a grounded retrieval system",
    selectedDirectionId: "retrieval-project",
    completedRoadmapNodeIds: ["define"],
    completedGuidedStepIds: ["define:choose-metric"],
    guidedStepProofs: {
      "define:choose-metric":
        "Saved the metric selection and evaluation plan.",
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
              purpose: "Choose the system boundary.",
              guided_steps: [
                {
                  step_id: "choose-metric",
                  title: "Choose the metric",
                  decision_point:
                    "Which metric should guide validation?",
                },
              ],
            },
            {
              id: "validate",
              title: "Validate the system",
              purpose: "Evaluate retrieval quality.",
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

  const summary = generatePortfolioSummary(workspace);

  if (!summary) {
    throw new Error("Expected portfolio summary.");
  }

  return summary;
}

describe("adaptation audit artifact propagation", () => {
  it("adds implemented adaptation evidence to the interview story", () => {
    const story = buildInterviewStory(
      buildSummary({
        status: "accepted",
        evidence:
          "Evaluation report shows precision@3 = 0.81.",
      }),
    );

    expect(story.implementation).toContain(
      "decision-driven roadmap adjustment",
    );
    expect(story.implementation).toContain(
      "precision@3 = 0.81",
    );
    expect(story.adaptationHighlights[0]).toContain(
      "Implemented:",
    );
    expect(formatInterviewStoryText(story)).toContain(
      "Roadmap adaptation audit:",
    );
  });

  it("uses missing accepted evidence as the next interview improvement", () => {
    const story = buildInterviewStory(
      buildSummary({
        status: "accepted",
      }),
    );

    expect(story.validation).toContain(
      "still requires implementation evidence",
    );
    expect(story.improvement).toContain(
      "still lack evidence",
    );
  });

  it("adds the audit to the README outline", () => {
    const readme = buildReadmeOutline(
      buildSummary({
        status: "deferred",
      }),
    );

    const auditSection = readme.sections.find(
      (section) =>
        section.title ===
        "Decision-Driven Roadmap Adjustments",
    );

    expect(auditSection?.body).toContain("Deferred:");
    expect(readme.markdown).toContain(
      "## Decision-Driven Roadmap Adjustments",
    );
    expect(readme.markdown).toContain(
      "Revisit deferred adjustment",
    );
  });

  it("adds adaptation status and audit details to the Build Passport", () => {
    const passport = buildPassport(
      buildSummary({
        status: "accepted",
        evidence:
          "Evaluation report shows precision@3 = 0.81.",
      }),
    );

    expect(
      passport.statuses.find(
        (status) =>
          status.label === "Accepted adaptations evidenced",
      )?.passed,
    ).toBe(true);
    expect(passport.adaptationAudit[0]).toContain(
      "Implemented:",
    );
    expect(passport.executionSummary).toContain(
      "1/1 decided roadmap adaptations implemented",
    );
    expect(passport.markdown).toContain(
      "## Roadmap Adaptation Audit",
    );
  });

  it("fails the passport adaptation status when accepted evidence is missing", () => {
    const passport = buildPassport(
      buildSummary({
        status: "accepted",
      }),
    );

    expect(
      passport.statuses.find(
        (status) =>
          status.label === "Accepted adaptations evidenced",
      )?.passed,
    ).toBe(false);
    expect(passport.adaptationAudit[0]).toContain(
      "Accepted but missing evidence",
    );
  });

  it("preserves rejected rationale in generated artifacts", () => {
    const summary = buildSummary({
      status: "rejected",
    });
    const story = buildInterviewStory(summary);
    const readme = buildReadmeOutline(summary);
    const passport = buildPassport(summary);

    expect(story.adaptationHighlights[0]).toContain(
      "does not match the product goal",
    );
    expect(readme.markdown).toContain("Rejected:");
    expect(passport.markdown).toContain(
      "does not match the product goal",
    );
  });
});
