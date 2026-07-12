import { describe, expect, it } from "vitest";

import { buildInterviewStory } from "./interviewStory";
import {
  generatePortfolioSummary,
  type PortfolioWorkspaceLike,
} from "./portfolioSummary";

function buildSummary(decisionAnswer: string) {
  const workspace: PortfolioWorkspaceLike = {
    goal: "Build a grounded retrieval system",
    selectedDirectionId: "retrieval-project",
    completedRoadmapNodeIds: ["define"],
    completedGuidedStepIds: ["define:choose-design"],
    guidedStepProofs: {
      "define:choose-design":
        "The input is a query and the output is a ranked result.",
    },
    decisionAnswers: {
      "define:choose-design": decisionAnswer,
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
          summary: "A retrieval-focused project.",
          difficulty: "Medium",
          estimated_effort: "3 weeks",
          career_signal: "ML systems",
          roadmap: [
            {
              id: "define",
              title: "Define the system",
              purpose: "Choose the system boundary.",
              guided_steps: [
                {
                  step_id: "choose-design",
                  title: "Choose the design",
                  decision_point:
                    "Why is this technical choice appropriate?",
                  expected_output_patterns: ["input", "output"],
                  interview_takeaway:
                    "I connected architecture decisions to constraints.",
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

  const summary = generatePortfolioSummary(workspace);

  if (!summary) {
    throw new Error("Expected a portfolio summary.");
  }

  return summary;
}

describe("interview story decision consequences", () => {
  it("uses architecture consequences in the interview story", () => {
    const story = buildInterviewStory(
      buildSummary(
        "I chose FAISS with a local index to avoid a hosted vector database.",
      ),
    );

    expect(story.implementation).toContain("faiss");
    expect(story.implementation).toContain("local index");
    expect(story.tradeoff).toContain(
      "Align later implementation, persistence, and deployment checks",
    );
  });

  it("uses the selected validation metric", () => {
    const story = buildInterviewStory(
      buildSummary(
        "I chose precision@3 because the first three results matter most.",
      ),
    );

    expect(story.validation).toContain("precision@3");
    expect(story.tradeoff).toContain(
      "Use precision@3 in later validation steps",
    );
  });

  it("turns deferred scope into the next improvement", () => {
    const story = buildInterviewStory(
      buildSummary(
        "I deferred authentication until the extension phase.",
      ),
    );

    expect(story.improvement).toContain(
      "authentication until the extension phase",
    );
    expect(story.tradeoff).toContain("outside the MVP");
  });

  it("preserves the fallback story without decision signals", () => {
    const summary = buildSummary("");
    const story = buildInterviewStory(summary);

    expect(story.tradeoff).toContain(
      "keeping the first version focused",
    );
    expect(story.validation).toContain(
      summary.evidenceConfidenceLabel,
    );
  });
});
