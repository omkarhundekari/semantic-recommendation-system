import type {
  PersistedWorkspace,
} from "./workspacePersistence";
import type {
  AdaptationDecisionMap,
} from "./roadmapAdaptationState";

type SanitizableGuidedStep = {
  step_id: string;
};

type SanitizableRoadmapStage = {
  id: string;
  guided_steps?: SanitizableGuidedStep[];
};

type SanitizableDirection = {
  id: string;
  roadmap: SanitizableRoadmapStage[];
};

export type SanitizableWorkspaceResult = {
  directions: SanitizableDirection[];
};

const VALID_ADAPTATION_CATEGORIES = new Set([
  "validation",
  "scope",
  "architecture",
  "performance",
  "security",
  "cost",
  "simplicity",
]);

function filterStringRecord(
  values: Record<string, string>,
  validKeys: Set<string>,
): Record<string, string> {
  return Object.fromEntries(
    Object.entries(values).filter(([key]) =>
      validKeys.has(key),
    ),
  );
}

function filterAdaptationDecisions(
  decisions: AdaptationDecisionMap,
  validStageIds: Set<string>,
): AdaptationDecisionMap {
  return Object.fromEntries(
    Object.entries(decisions).filter(([key, decision]) => {
      const separatorIndex = key.lastIndexOf(":");

      if (separatorIndex <= 0) {
        return false;
      }

      const stageId = key.slice(0, separatorIndex);
      const category = key.slice(separatorIndex + 1);

      return (
        decision.adaptationKey === key &&
        validStageIds.has(stageId) &&
        VALID_ADAPTATION_CATEGORIES.has(category)
      );
    }),
  );
}

export function sanitizeWorkspaceReferences<
  TResult extends SanitizableWorkspaceResult,
>(
  workspace: PersistedWorkspace<TResult>,
): PersistedWorkspace<TResult> {
  const selectedDirection =
    workspace.result.directions.find(
      (direction) =>
        direction.id === workspace.selectedDirectionId,
    ) ?? null;

  if (!selectedDirection) {
    return {
      ...workspace,
      selectedDirectionId: null,
      activeRoadmapNodeId: null,
      completedRoadmapNodeIds: [],
      guidedStepProofs: {},
      decisionAnswers: {},
      completedGuidedStepIds: [],
      adaptationDecisions: {},
      adaptationEvidence: {},
    };
  }

  const validStageIds = new Set(
    selectedDirection.roadmap.map((stage) => stage.id),
  );

  const validStepKeys = new Set(
    selectedDirection.roadmap.flatMap((stage) =>
      (stage.guided_steps ?? []).map(
        (step) => `${stage.id}:${step.step_id}`,
      ),
    ),
  );

  const adaptationDecisions = filterAdaptationDecisions(
    workspace.adaptationDecisions,
    validStageIds,
  );

  const validAdaptationKeys = new Set(
    Object.keys(adaptationDecisions),
  );

  return {
    ...workspace,
    activeRoadmapNodeId:
      workspace.activeRoadmapNodeId &&
      validStageIds.has(workspace.activeRoadmapNodeId)
        ? workspace.activeRoadmapNodeId
        : null,
    completedRoadmapNodeIds:
      workspace.completedRoadmapNodeIds.filter((stageId) =>
        validStageIds.has(stageId),
      ),
    guidedStepProofs: filterStringRecord(
      workspace.guidedStepProofs,
      validStepKeys,
    ),
    decisionAnswers: filterStringRecord(
      workspace.decisionAnswers,
      validStepKeys,
    ),
    completedGuidedStepIds:
      workspace.completedGuidedStepIds.filter((stepKey) =>
        validStepKeys.has(stepKey),
      ),
    adaptationDecisions,
    adaptationEvidence: filterStringRecord(
      workspace.adaptationEvidence,
      validAdaptationKeys,
    ),
  };
}
