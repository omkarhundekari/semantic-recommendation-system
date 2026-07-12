export type ProofValidationStatus =
  | "empty"
  | "accepted"
  | "needs_detail"
  | "missing_expected_pattern";

export type ProofValidationResult = {
  status: ProofValidationStatus;
  missingPatterns: string[];
  feedback: string;
};

export function validateProof(
  proof: string,
  expectedPatterns: string[],
): ProofValidationResult {
  const normalizedProof = proof.toLowerCase().trim();
  const normalizedPatterns = expectedPatterns
    .map((pattern) => pattern.trim())
    .filter(Boolean);

  if (!normalizedProof) {
    return {
      status: "empty",
      missingPatterns: normalizedPatterns,
      feedback: "Paste proof for this guided step.",
    };
  }

  if (normalizedPatterns.length === 0) {
    return {
      status: "needs_detail",
      missingPatterns: [],
      feedback:
        "Proof saved. Add enough detail so future-you can understand what was completed.",
    };
  }

  const missingPatterns = normalizedPatterns.filter(
    (pattern) => !normalizedProof.includes(pattern.toLowerCase()),
  );

  if (missingPatterns.length === 0) {
    return {
      status: "accepted",
      missingPatterns: [],
      feedback: "Proof looks complete.",
    };
  }

  return {
    status: "missing_expected_pattern",
    missingPatterns,
    feedback: `Expected to see: ${missingPatterns.join(", ")}.`,
  };
}
