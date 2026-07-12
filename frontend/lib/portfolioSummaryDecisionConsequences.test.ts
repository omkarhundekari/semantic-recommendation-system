import { describe, expect, it } from "vitest";

import {
  formatPortfolioSummaryText,
  generatePortfolioSummary,
  type PortfolioWorkspaceLike,
} from "./portfolioSummary";

function buildWorkspace(
  decisionAnswer: string,
): PortfolioWorkspaceLike {
  return {
    goal: "Build a grounded retrieval system",
    selectedDirectionId: "retrieval-project",
    completedRoadmapNodeIds: ["define"],
    completedGuidedStepIds: ["define:choose-architecture"],
    guidedStepProofs: {
      "define:choose-architecture":
        "Created an input query and output ranking workflow.",
    },
    decisionAnswers: {
      "define:choose-architecture": decisionAnswer,
    },
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
          summary: "A retrieval-focused engineering project.",
          difficulty: "Medium",
          estimated_effort: "3 weeks",
          career_signal: "ML systems",
          roadmap: [
            {
              id: "define",
              title: "Define the architecture",
              purpose: "Choose the first system boundary.",
              portfolio_artifact: "Architecture decision record",
              guided_steps: [
                {
                  step_id: "choose-architecture",
                  title: "Choose the architecture",
                  decision_point:
                    "Why is this architecture appropriate?",
                  expected_output_patterns: ["input", "output"],
                  interview_takeaway:
                    "I chose an architecture based on project constraints.",
                },
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

describe("portfolio summary decision consequences", () => {
  it("includes architecture consequences from captured decisions", () => {
    const summary = generatePortfolioSummary(
      buildWorkspace(
        "I chose FAISS with a local index to avoid a hosted vector database.",
      ),
    );

    expect(summary).not.toBeNull();
    expect(summary?.decisionConsequences.decisionCount).toBe(1);
    expect(
      summary?.decisionConsequences.architectureSignals,
    ).toEqual([
      "faiss",
      "local index",
      "vector database",
    ]);
    expect(
      summary?.decisionConsequences.consequences[0].category,
    ).toBe("architecture");
  });

  it("includes validation metrics and deferred scope", () => {
    const validationSummary = generatePortfolioSummary(
      buildWorkspace(
        "I chose precision@3 because the top three results matter most.",
      ),
    );
    const scopeSummary = generatePortfolioSummary(
      buildWorkspace(
        "I deferred authentication until the extension phase.",
      ),
    );

    expect(
      validationSummary?.decisionConsequences.validationFocus,
    ).toContain("precision@3");
    expect(
      scopeSummary?.decisionConsequences.deferredItems,
    ).toEqual(["authentication until the extension phase"]);
  });

  it("exports decision consequences in formatted portfolio text", () => {
    const summary = generatePortfolioSummary(
      buildWorkspace(
        "I kept the design simple and used the free tier to reduce cost.",
      ),
    );

    expect(summary).not.toBeNull();

    const formatted = formatPortfolioSummaryText(summary!);

    expect(formatted).toContain("Decision consequences:");
    expect(formatted).toContain("Engineering priorities:");
    expect(formatted).toContain("- simplicity");
    expect(formatted).toContain("- cost");
  });

  it("returns an empty consequence evaluation without answers", () => {
    const workspace = buildWorkspace("");
    workspace.decisionAnswers = {};

    const summary = generatePortfolioSummary(workspace);

    expect(summary?.technicalDecisions).toEqual([]);
    expect(summary?.decisionConsequences).toEqual({
      decisionCount: 0,
      consequences: [],
      validationFocus: [],
      deferredItems: [],
      architectureSignals: [],
      priorities: [],
    });
  });
});
