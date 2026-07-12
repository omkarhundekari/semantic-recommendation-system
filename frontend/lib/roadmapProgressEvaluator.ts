export type RoadmapProgressStatus =
  | "not_started"
  | "in_progress"
  | "blocked"
  | "complete";

export type MissingRequirement = "proof" | "decision_answer";

export type ProgressGuidedStep = {
  step_id: string;
  action: string;
  decision_point?: string | null;
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

function hasText(value: string | undefined): boolean {
  return Boolean(value?.trim());
}

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

function getMissingRequirements({
  step,
  stepKey,
  guidedStepProofs,
  decisionAnswers,
}: {
  step: ProgressGuidedStep;
  stepKey: string;
  guidedStepProofs: Record<string, string>;
  decisionAnswers: Record<string, string>;
}): MissingRequirement[] {
  const missing: MissingRequirement[] = [];

  if (!hasText(guidedStepProofs[stepKey])) {
    missing.push("proof");
  }

  if (
    step.decision_point &&
    !hasText(decisionAnswers[stepKey])
  ) {
    missing.push("decision_answer");
  }

  return missing;
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

      return (
        getMissingRequirements({
          step,
          stepKey,
          guidedStepProofs,
          decisionAnswers,
        }).length > 0
      );
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

  const missingRequirements = currentStep
    ? getMissingRequirements({
        step: currentStep.step,
        stepKey: currentStep.stepKey,
        guidedStepProofs,
        decisionAnswers,
      })
    : [];

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
    !hasText(
      currentStep
        ? guidedStepProofs[currentStep.stepKey]
        : undefined,
    )
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
    missingRequirements,
    blockedStepKeys,
    missionReady,
    projectComplete,
  };
}
