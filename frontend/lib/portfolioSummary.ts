import {
  evaluateDecisionConsequences,
  type DecisionConsequenceEvaluation,
} from "./decisionConsequenceEvaluator";
import {
  buildAdaptationArtifactAudit,
  formatAdaptationArtifactEntry,
  type AdaptationArtifactAudit,
} from "./adaptationArtifactAudit";
import { evaluateRoadmapAdaptations } from "./roadmapAdaptationEvaluator";
import type { AdaptationDecisionMap } from "./roadmapAdaptationState";

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
  decisionAnswers?: Record<string, string>;
  completedGuidedStepIds?: string[];
  adaptationDecisions?: AdaptationDecisionMap;
  adaptationEvidence?: Record<string, string>;
  result: {
    resolved_planning_domain?: string | null;
    evidence_coverage?: {
      label?: string;
      coverage_state?: string;
      user_message?: string;
      warnings?: string[];
    } | null;
    directions: DirectionLike[];
  };
};

export type DecisionEntry = {
  missionId: string;
  missionTitle: string;
  stepId: string;
  stepTitle: string;
  decisionPoint: string;
  answer: string;
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
  decisionConsequences: DecisionConsequenceEvaluation;
  adaptationAudit: AdaptationArtifactAudit;
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
  const decisionConsequences =
    evaluateDecisionConsequences(technicalDecisions);
  const roadmapAdaptations = evaluateRoadmapAdaptations({
    roadmap: direction.roadmap,
    decisionConsequences,
  });
  const adaptationAudit = buildAdaptationArtifactAudit({
    adaptations: roadmapAdaptations.adaptations,
    decisions: workspace.adaptationDecisions ?? {},
    evidence: workspace.adaptationEvidence ?? {},
  });
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
    decisionConsequences,
    adaptationAudit,
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
  const answers = workspace.decisionAnswers ?? {};

  return direction.roadmap.flatMap((node) =>
    (node.guided_steps ?? [])
      .filter((step) => step.decision_point)
      .map((step) => {
        const answer =
          answers[guidedStepKey(node.id, step.step_id)]?.trim() ?? "";

        if (!answer) {
          return null;
        }

        return {
          missionId: node.id,
          missionTitle: node.title,
          stepId: step.step_id,
          stepTitle: step.title,
          decisionPoint: step.decision_point ?? "",
          answer,
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

export function formatPortfolioSummaryText(summary: PortfolioSummary): string {
  const sections = [
    `Project: ${summary.projectTitle}`,
    `Goal: ${summary.goal}`,
    summary.domain ? `Domain: ${summary.domain}` : "",
    `Evidence: ${summary.evidenceConfidenceLabel}`,
    summary.evidenceConfidenceDetail,
    "",
    "Execution summary:",
    `- Missions completed: ${summary.missionsCompleted}/${summary.totalMissions}`,
    `- Guided steps completed: ${summary.guidedStepsCompleted}/${summary.totalGuidedSteps}`,
    `- Proof entries saved: ${summary.proofEntriesSaved}`,
    "",
    "Skills demonstrated:",
    ...summary.skillsDemonstrated.map((skill) => `- ${skill}`),
    "",
    "Technical decisions:",
    ...formatListOrFallback(
      summary.technicalDecisions.map(
        (decision) => `- ${decision.decisionPoint}\n  Evidence: ${decision.answer}`,
      ),
      "- No technical decisions captured yet.",
    ),
    "",
    "Decision consequences:",
    ...formatListOrFallback(
      summary.decisionConsequences.consequences.map(
        (consequence) =>
          `- [${consequence.category}] ${consequence.recommendedAdjustment}`,
      ),
      "- No decision consequences identified yet.",
    ),
    "",
    "Validation focus:",
    ...formatListOrFallback(
      summary.decisionConsequences.validationFocus.map(
        (metric) => `- ${metric}`,
      ),
      "- No explicit validation metric captured yet.",
    ),
    "",
    "Deferred scope:",
    ...formatListOrFallback(
      summary.decisionConsequences.deferredItems.map(
        (item) => `- ${item}`,
      ),
      "- No deferred scope captured yet.",
    ),
    "",
    "Architecture signals:",
    ...formatListOrFallback(
      summary.decisionConsequences.architectureSignals.map(
        (signal) => `- ${signal}`,
      ),
      "- No explicit architecture signal captured yet.",
    ),
    "",
    "Engineering priorities:",
    ...formatListOrFallback(
      summary.decisionConsequences.priorities.map(
        (priority) => `- ${priority}`,
      ),
      "- No explicit engineering priority captured yet.",
    ),
    "",
    "Roadmap adaptation audit:",
    ...formatListOrFallback(
      summary.adaptationAudit.entries.map(
        (entry) => `- ${formatAdaptationArtifactEntry(entry)}`,
      ),
      "- No roadmap adaptation decisions captured yet.",
    ),
    "",
    "Implemented adaptations:",
    ...formatListOrFallback(
      summary.adaptationAudit.implemented.map(
        (entry) => `- ${entry.title}: ${entry.evidence}`,
      ),
      "- No accepted adaptations have implementation evidence yet.",
    ),
    "",
    "Accepted adaptations missing evidence:",
    ...formatListOrFallback(
      summary.adaptationAudit.acceptedMissingEvidence.map(
        (entry) => `- ${entry.title}`,
      ),
      "- No accepted adaptations are missing evidence.",
    ),
    "",
    "Known limitations:",
    ...formatListOrFallback(
      summary.knownLimitations.map((limitation) => `- ${limitation}`),
      "- No limitations captured yet.",
    ),
    "",
    "Interview takeaways:",
    ...formatListOrFallback(
      summary.interviewTakeaways.map((takeaway) => `- ${takeaway}`),
      "- No interview takeaways captured yet.",
    ),
    "",
    "Portfolio artifacts:",
    ...formatListOrFallback(
      summary.portfolioArtifacts.map((artifact) => `- ${artifact}`),
      "- No portfolio artifacts captured yet.",
    ),
  ];

  return sections.filter((section) => section !== "").join("\n");
}

export function buildResumeReadyParagraph(summary: PortfolioSummary): string {
  const skills = summary.skillsDemonstrated.slice(0, 3).join(", ");
  const proofPhrase =
    summary.proofEntriesSaved > 0
      ? `${summary.proofEntriesSaved} proof-backed execution step${
          summary.proofEntriesSaved === 1 ? "" : "s"
        }`
      : "guided execution evidence";

  const validationPhrase = summary.completionState.fullyExecuted
    ? "completed the full guided roadmap"
    : "completed part of the guided roadmap";

  const adaptationPhrase =
    summary.adaptationAudit.implementedCount > 0
      ? `, implemented ${summary.adaptationAudit.implementedCount} decision-driven roadmap adjustment${
          summary.adaptationAudit.implementedCount === 1 ? "" : "s"
        } with saved evidence`
      : "";

  return `Built ${summary.projectTitle}, a ${summary.domain ?? "technical"} project for ${summary.goal}. The project ${validationPhrase}, captured ${proofPhrase}${adaptationPhrase}, and demonstrated ${skills || "project execution, validation, and technical communication"}.`;
}

function formatListOrFallback(items: string[], fallback: string): string[] {
  return items.length > 0 ? items : [fallback];
}
