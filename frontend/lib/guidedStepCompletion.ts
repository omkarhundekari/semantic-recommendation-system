export type ProofValidationStatus =
  | "empty"
  | "accepted"
  | "needs_detail"
  | "missing_expected_pattern";

export function canCompleteGuidedStep({
  proofStatus,
  decisionPoint,
  decisionAnswer,
}: {
  proofStatus: ProofValidationStatus;
  decisionPoint?: string | null;
  decisionAnswer: string;
}): boolean {
  const hasRequiredDecisionAnswer =
    !decisionPoint || decisionAnswer.trim().length > 0;

  const hasValidProof =
    proofStatus === "accepted" || proofStatus === "needs_detail";

  return hasRequiredDecisionAnswer && hasValidProof;
}
