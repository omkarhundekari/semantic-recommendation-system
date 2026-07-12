export type GuidedMissionStepLike = {
  step_id: string;
  title: string;
  explanation?: string;
  action?: string;
  starter_command?: string | null;
  starter_files?: string[];
  done_when?: string;
  common_confusion?: string;
  decision_point?: string | null;
  proof_type?: string;
  proof_prompt?: string;
  expected_output_patterns?: string[];
  interview_takeaway?: string;
};

export type RoadmapNodeLike = {
  id: string;
  title: string;
  purpose: string;
  tasks?: string[];
  stage_type?: string | null;
  objective?: string | null;
  why_it_matters?: string | null;
  commands?: string[];
  expected_outputs?: string[];
  acceptance_criteria?: string[];
  validation_checks?: string[];
  common_errors?: string[];
  portfolio_artifact?: string | null;
  unlock_condition?: string | null;
  guided_steps?: GuidedMissionStepLike[];
};

export type DirectionLike = {
  id: string;
  title: string;
  summary: string;
  difficulty?: string;
  estimated_effort?: string;
  career_signal?: string;
  roadmap: RoadmapNodeLike[];
  evidence_summary?: {
    support_label?: string;
    support_detail?: string;
    source_titles?: string[];
  };
  verification?: {
    status?: string;
    issues?: string[];
  };
};

export type PortfolioWorkspaceLike = {
  goal: string;
  selectedDirectionId: string | null;
  completedRoadmapNodeIds: string[];
  guidedStepProofs?: Record<string, string>;
  completedGuidedStepIds?: string[];
  result: {
    resolved_planning_domain?: string | null;
    evidence_coverage?: {
      label?: string;
      coverage_state?: string;
      user_message?: string;
      warnings?: string[];
    };
    directions: DirectionLike[];
  };
};

export type DecisionEntry = {
  missionId: string;
  missionTitle: string;
  stepId: string;
  stepTitle: string;
  decisionPoint: string;
  proof: string;
};

export type ProofEntry = {
  missionId: string;
  missionTitle: string;
  stepId: string;
  stepTitle: string;
  proofType: string;
  proof: string;
  expectedOutputPatterns: string[];
};

export type PortfolioSummary = {
  projectTitle: string;
  goal: string;
  domain: string | null;
  evidenceConfidenceLabel: string;
  evidenceConfidenceDetail: string;
  missionsCompleted: number;
  totalMissions: number;
  guidedStepsCompleted: number;
  totalGuidedSteps: number;
  proofEntriesSaved: number;
  technicalDecisions: DecisionEntry[];
  proofEntries: ProofEntry[];
  skillsDemonstrated: string[];
  knownLimitations: string[];
  interviewTakeaways: string[];
  portfolioArtifacts: string[];
  completionState: {
    evidenceBacked: boolean;
    fullyExecuted: boolean;
    portfolioReady: boolean;
    interviewPrepped: boolean;
  };
};

export function generatePortfolioSummary(
  workspace: PortfolioWorkspaceLike,
): PortfolioSummary | null {
  const direction = findSelectedDirection(workspace);

  if (!direction) {
    return null;
  }

  const guidedStepKeys = direction.roadmap.flatMap((node) =>
    (node.guided_steps ?? []).map((step) =>
      guidedStepKey(node.id, step.step_id),
    ),
  );

  const guidedStepsCompleted = guidedStepKeys.filter((stepKey) =>
    workspace.completedGuidedStepIds?.includes(stepKey),
  ).length;

  const proofEntries = extractProofEntries(workspace, direction);
  const technicalDecisions = extractDecisionPoints(workspace, direction);
  const skillsDemonstrated = extractSkills(direction, workspace);
  const knownLimitations = extractKnownLimitations(direction, workspace);
  const interviewTakeaways = extractInterviewTakeaways(direction);
  const portfolioArtifacts = extractPortfolioArtifacts(direction);

  const evidenceCoverageState =
    workspace.result.evidence_coverage?.coverage_state ?? "";
  const evidenceBacked = ["strong_direct", "adequate_direct"].includes(
    evidenceCoverageState,
  );

  return {
    projectTitle: direction.title,
    goal: workspace.goal,
    domain: workspace.result.resolved_planning_domain ?? null,
    evidenceConfidenceLabel:
      workspace.result.evidence_coverage?.label ??
      direction.evidence_summary?.support_label ??
      "Evidence reviewed",
    evidenceConfidenceDetail:
      workspace.result.evidence_coverage?.user_message ??
      direction.evidence_summary?.support_detail ??
      "This project direction was generated from the available evidence signals.",
    missionsCompleted: direction.roadmap.filter((node) =>
      workspace.completedRoadmapNodeIds.includes(node.id),
    ).length,
    totalMissions: direction.roadmap.length,
    guidedStepsCompleted,
    totalGuidedSteps: guidedStepKeys.length,
    proofEntriesSaved: proofEntries.length,
    technicalDecisions,
    proofEntries,
    skillsDemonstrated,
    knownLimitations,
    interviewTakeaways,
    portfolioArtifacts,
    completionState: {
      evidenceBacked,
      fullyExecuted:
        direction.roadmap.length > 0 &&
        direction.roadmap.every((node) =>
          workspace.completedRoadmapNodeIds.includes(node.id),
        ),
      portfolioReady: portfolioArtifacts.length > 0 && proofEntries.length > 0,
      interviewPrepped:
        interviewTakeaways.length > 0 && technicalDecisions.length > 0,
    },
  };
}

export function extractDecisionPoints(
  workspace: PortfolioWorkspaceLike,
  direction: DirectionLike,
): DecisionEntry[] {
  const proofs = workspace.guidedStepProofs ?? {};

  return direction.roadmap.flatMap((node) =>
    (node.guided_steps ?? [])
      .filter((step) => step.decision_point)
      .map((step) => {
        const proof = proofs[guidedStepKey(node.id, step.step_id)]?.trim() ?? "";

        if (!proof) {
          return null;
        }

        return {
          missionId: node.id,
          missionTitle: node.title,
          stepId: step.step_id,
          stepTitle: step.title,
          decisionPoint: step.decision_point ?? "",
          proof,
        };
      })
      .filter((entry): entry is DecisionEntry => entry !== null),
  );
}

export function extractProofEntries(
  workspace: PortfolioWorkspaceLike,
  direction: DirectionLike,
): ProofEntry[] {
  const proofs = workspace.guidedStepProofs ?? {};

  return direction.roadmap.flatMap((node) =>
    (node.guided_steps ?? [])
      .map((step) => {
        const proof = proofs[guidedStepKey(node.id, step.step_id)]?.trim() ?? "";

        if (!proof) {
          return null;
        }

        return {
          missionId: node.id,
          missionTitle: node.title,
          stepId: step.step_id,
          stepTitle: step.title,
          proofType: step.proof_type ?? "proof",
          proof,
          expectedOutputPatterns: step.expected_output_patterns ?? [],
        };
      })
      .filter((entry): entry is ProofEntry => entry !== null),
  );
}

export function extractInterviewTakeaways(
  direction: DirectionLike,
): string[] {
  return uniqueNonEmpty(
    direction.roadmap.flatMap((node) =>
      (node.guided_steps ?? []).map((step) => step.interview_takeaway ?? ""),
    ),
  );
}

export function extractSkills(
  direction: DirectionLike,
  workspace: PortfolioWorkspaceLike,
): string[] {
  const domainSkillMap: Record<string, string[]> = {
    rag_llm: [
      "RAG pipeline implementation",
      "Retrieval evaluation",
      "Evidence-grounded system design",
    ],
    frontend: [
      "Frontend architecture",
      "Stateful user flows",
      "Accessible interface design",
    ],
    education_tech: [
      "Learning flow design",
      "Student progress tracking",
      "Feedback loop design",
    ],
  };

  const domain = workspace.result.resolved_planning_domain ?? "";
  const domainSkills = domainSkillMap[domain] ?? [];

  const roadmapSignals = direction.roadmap.flatMap((node) => [
    node.stage_type ?? "",
    node.objective ?? "",
    node.why_it_matters ?? "",
    ...(node.validation_checks ?? []),
    ...(node.expected_outputs ?? []),
  ]);

  const inferredSkills = roadmapSignals
    .join(" ")
    .toLowerCase()
    .includes("validation")
    ? ["Validation-driven project execution"]
    : [];

  return uniqueNonEmpty([
    ...domainSkills,
    ...inferredSkills,
    direction.career_signal ? `${direction.career_signal} career signal` : "",
  ]);
}

export function extractKnownLimitations(
  direction: DirectionLike,
  workspace: PortfolioWorkspaceLike,
): string[] {
  const coverageWarnings = workspace.result.evidence_coverage?.warnings ?? [];
  const verificationIssues = direction.verification?.issues ?? [];
  const commonErrors = direction.roadmap.flatMap(
    (node) => node.common_errors ?? [],
  );

  return uniqueNonEmpty([
    ...coverageWarnings,
    ...verificationIssues,
    ...commonErrors.slice(0, 3),
  ]);
}

export function extractPortfolioArtifacts(direction: DirectionLike): string[] {
  return uniqueNonEmpty(
    direction.roadmap.map((node) => node.portfolio_artifact ?? ""),
  );
}

function findSelectedDirection(
  workspace: PortfolioWorkspaceLike,
): DirectionLike | null {
  if (workspace.selectedDirectionId) {
    const selected = workspace.result.directions.find(
      (direction) => direction.id === workspace.selectedDirectionId,
    );

    if (selected) {
      return selected;
    }
  }

  return workspace.result.directions[0] ?? null;
}

function guidedStepKey(nodeId: string, stepId: string): string {
  return `${nodeId}:${stepId}`;
}

function uniqueNonEmpty(values: string[]): string[] {
  return Array.from(
    new Set(values.map((value) => value.trim()).filter(Boolean)),
  );
}
