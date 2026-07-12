import { describe, expect, it } from "vitest";

import { canCompleteGuidedStep } from "./guidedStepCompletion";

describe("canCompleteGuidedStep", () => {
  it("allows a regular guided step when proof is valid", () => {
    expect(
      canCompleteGuidedStep({
        proofStatus: "accepted",
        decisionPoint: null,
        decisionAnswer: "",
      }),
    ).toBe(true);
  });

  it("blocks a decision-bearing step when its answer is blank", () => {
    expect(
      canCompleteGuidedStep({
        proofStatus: "accepted",
        decisionPoint: "Which retrieval strategy did you choose?",
        decisionAnswer: "   ",
      }),
    ).toBe(false);
  });

  it("allows a decision-bearing step with valid proof and reasoning", () => {
    expect(
      canCompleteGuidedStep({
        proofStatus: "needs_detail",
        decisionPoint: "Which retrieval strategy did you choose?",
        decisionAnswer: "I used hybrid retrieval to improve recall.",
      }),
    ).toBe(true);
  });

  it("blocks completion when proof is invalid", () => {
    expect(
      canCompleteGuidedStep({
        proofStatus: "missing_expected_pattern",
        decisionPoint: "Which retrieval strategy did you choose?",
        decisionAnswer: "I used hybrid retrieval.",
      }),
    ).toBe(false);
  });

  it("blocks a regular step when proof is empty", () => {
    expect(
      canCompleteGuidedStep({
        proofStatus: "empty",
        decisionPoint: null,
        decisionAnswer: "",
      }),
    ).toBe(false);
  });
});
