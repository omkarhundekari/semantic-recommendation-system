import { canCompleteGuidedStep } from "./guidedStepCompletion";
import {
  validateProof,
  type ProofValidationStatus,
} from "./proofValidation";

export type RoadmapProgressStatus =
  | "not_started"
  | "in_progress"
  | "blocked"
  | "complete";

export type MissingRequirement =
  | "proof"
  | "proof_expected_pattern"
  | "decision_answer";

export type ProgressGuidedStep = {
  step_id: string;
  action: string;
  decision_point?: string | null;
  expected_output_patterns?: string[];
};

export type ProgressRoadmapStage = {
  id: string;
  guided_steps?: ProgressGuidedStep[];
};

export type RoadmapProgressEvaluation = {
  status: RoadmapProgressStatus;
  completedStepCount: number;
  totalStepCount: number;
  completionRatio: number;
  completedMissionCount: number;
  totalMissionCount: number;
  currentStageId: string | null;
  currentStepKey: string | null;
  recommendedNextAction: string | null;
  missingRequirements: MissingRequirement[];
  currentProofStatus: ProofValidationStatus | null;
  currentProofFeedback: string | null;
  missingProofPatterns: string[];
  blockedStepKeys: string[];
  missionReady: boolean;
  projectComplete: boolean;
};

type EvaluateRoadmapProgressInput = {
  roadmap: ProgressRoadmapStage[];
  completedRoadmapNodeIds: string[];
  completedGuidedStepIds: string[];
  guidedStepProofs: Record<string, string>;
  decisionAnswers: Record<string, string>;
};

type FlattenedStep = {
  stageId: string;
  stepKey: string;
  step: ProgressGuidedStep;
};

function flattenRoadmapSteps(
  roadmap: ProgressRoadmapStage[],
): FlattenedStep[] {
  return roadmap.flatMap((stage) =>
    (stage.guided_steps ?? []).map((step) => ({
      stageId: stage.id,
      stepKey: `${stage.id}:${step.step_id}`,
      step,
    })),
  );
}

function evaluateStep({
  step,
  stepKey,
  guidedStepProofs,
  decisionAnswers,
}: {
  step: ProgressGuidedStep;
  stepKey: string;
  guidedStepProofs: Record<string, string>;
  decisionAnswers: Record<string, string>;
}) {
  const proofValidation = validateProof(
    guidedStepProofs[stepKey] ?? "",
    step.expected_output_patterns ?? [],
  );
  const decisionAnswer = decisionAnswers[stepKey] ?? "";
  const canComplete = canCompleteGuidedStep({
    proofStatus: proofValidation.status,
    decisionPoint: step.decision_point,
    decisionAnswer,
  });

  const missingRequirements: MissingRequirement[] = [];

  if (proofValidation.status === "empty") {
    missingRequirements.push("proof");
  }

  if (proofValidation.status === "missing_expected_pattern") {
    missingRequirements.push("proof_expected_pattern");
  }

  if (
    step.decision_point &&
    decisionAnswer.trim().length === 0
  ) {
    missingRequirements.push("decision_answer");
  }

  return {
    proofValidation,
    missingRequirements,
    canComplete,
  };
}

export function evaluateRoadmapProgress({
  roadmap,
  completedRoadmapNodeIds,
  completedGuidedStepIds,
  guidedStepProofs,
  decisionAnswers,
}: EvaluateRoadmapProgressInput): RoadmapProgressEvaluation {
  const flattenedSteps = flattenRoadmapSteps(roadmap);
  const validStepKeys = new Set(
    flattenedSteps.map(({ stepKey }) => stepKey),
  );
  const completedStepKeys = new Set(
    completedGuidedStepIds.filter((stepKey) =>
      validStepKeys.has(stepKey),
    ),
  );

  const blockedStepKeys = flattenedSteps
    .filter(({ step, stepKey }) => {
      if (!completedStepKeys.has(stepKey)) {
        return false;
      }

      return !evaluateStep({
        step,
        stepKey,
        guidedStepProofs,
        decisionAnswers,
      }).canComplete;
    })
    .map(({ stepKey }) => stepKey);

  const currentStep =
    flattenedSteps.find(
      ({ stepKey }) => !completedStepKeys.has(stepKey),
    ) ?? null;

  const currentStage =
    roadmap.find((stage) => {
      const stageSteps = stage.guided_steps ?? [];

      if (stageSteps.length > 0) {
        return stageSteps.some(
          (step) =>
            !completedStepKeys.has(
              `${stage.id}:${step.step_id}`,
            ),
        );
      }

      return !completedRoadmapNodeIds.includes(stage.id);
    }) ?? null;

  const currentStepEvaluation = currentStep
    ? evaluateStep({
        step: currentStep.step,
        stepKey: currentStep.stepKey,
        guidedStepProofs,
        decisionAnswers,
      })
    : null;

  const currentStageSteps = currentStage?.guided_steps ?? [];
  const missionReady =
    currentStage !== null &&
    currentStageSteps.length > 0 &&
    currentStageSteps.every((step) =>
      completedStepKeys.has(
        `${currentStage.id}:${step.step_id}`,
      ),
    );

  const completedMissionCount = roadmap.filter((stage) =>
    completedRoadmapNodeIds.includes(stage.id),
  ).length;

  const totalStepCount = flattenedSteps.length;
  const completedStepCount = completedStepKeys.size;
  const allGuidedStepsComplete =
    totalStepCount === 0 ||
    completedStepCount === totalStepCount;
  const allMissionsComplete =
    roadmap.length > 0 &&
    completedMissionCount === roadmap.length;
  const projectComplete =
    allGuidedStepsComplete &&
    allMissionsComplete &&
    blockedStepKeys.length === 0;

  let status: RoadmapProgressStatus;

  if (projectComplete) {
    status = "complete";
  } else if (blockedStepKeys.length > 0) {
    status = "blocked";
  } else if (
    completedStepCount === 0 &&
    completedMissionCount === 0 &&
    currentStepEvaluation?.proofValidation.status === "empty"
  ) {
    status = "not_started";
  } else {
    status = "in_progress";
  }

  return {
    status,
    completedStepCount,
    totalStepCount,
    completionRatio:
      totalStepCount > 0
        ? completedStepCount / totalStepCount
        : roadmap.length > 0
          ? completedMissionCount / roadmap.length
          : 0,
    completedMissionCount,
    totalMissionCount: roadmap.length,
    currentStageId:
      currentStep?.stageId ?? currentStage?.id ?? null,
    currentStepKey: currentStep?.stepKey ?? null,
    recommendedNextAction:
      currentStep?.step.action ?? null,
    missingRequirements:
      currentStepEvaluation?.missingRequirements ?? [],
    currentProofStatus:
      currentStepEvaluation?.proofValidation.status ?? null,
    currentProofFeedback:
      currentStepEvaluation?.proofValidation.feedback ?? null,
    missingProofPatterns:
      currentStepEvaluation?.proofValidation.missingPatterns ?? [],
    blockedStepKeys,
    missionReady,
    projectComplete,
  };
}
