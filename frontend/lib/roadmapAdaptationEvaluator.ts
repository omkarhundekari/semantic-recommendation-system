import type {
  DecisionConsequenceEvaluation,
} from "./decisionConsequenceEvaluator";

export type AdaptableRoadmapStage = {
  id: string;
  title: string;
  tasks?: string[];
  acceptance_criteria?: string[];
  validation_checks?: string[];
  unlock_condition?: string | null;
};

export type RoadmapAdaptationCategory =
  | "validation"
  | "scope"
  | "architecture"
  | "performance"
  | "security"
  | "cost"
  | "simplicity";

export type RoadmapAdaptation = {
  targetStageId: string;
  category: RoadmapAdaptationCategory;
  title: string;
  rationale: string;
  suggestedTasks: string[];
  suggestedAcceptanceCriteria: string[];
  suggestedValidationChecks: string[];
  suggestedUnlockCondition: string | null;
};

export type RoadmapAdaptationEvaluation = {
  adaptationCount: number;
  affectedStageIds: string[];
  adaptations: RoadmapAdaptation[];
};

type EvaluateRoadmapAdaptationsInput = {
  roadmap: AdaptableRoadmapStage[];
  decisionConsequences: DecisionConsequenceEvaluation;
};

function unique(items: string[]): string[] {
  return [...new Set(items.map((item) => item.trim()).filter(Boolean))];
}

function findStageId(
  roadmap: AdaptableRoadmapStage[],
  preferredIds: string[],
): string | null {
  for (const preferredId of preferredIds) {
    if (roadmap.some((stage) => stage.id === preferredId)) {
      return preferredId;
    }
  }

  return roadmap[0]?.id ?? null;
}

function addAdaptation(
  adaptations: RoadmapAdaptation[],
  adaptation: RoadmapAdaptation,
): void {
  const existing = adaptations.find(
    (item) =>
      item.targetStageId === adaptation.targetStageId &&
      item.category === adaptation.category,
  );

  if (!existing) {
    adaptations.push(adaptation);
    return;
  }

  existing.suggestedTasks = unique([
    ...existing.suggestedTasks,
    ...adaptation.suggestedTasks,
  ]);
  existing.suggestedAcceptanceCriteria = unique([
    ...existing.suggestedAcceptanceCriteria,
    ...adaptation.suggestedAcceptanceCriteria,
  ]);
  existing.suggestedValidationChecks = unique([
    ...existing.suggestedValidationChecks,
    ...adaptation.suggestedValidationChecks,
  ]);

  if (
    !existing.suggestedUnlockCondition &&
    adaptation.suggestedUnlockCondition
  ) {
    existing.suggestedUnlockCondition =
      adaptation.suggestedUnlockCondition;
  }
}

export function evaluateRoadmapAdaptations({
  roadmap,
  decisionConsequences,
}: EvaluateRoadmapAdaptationsInput): RoadmapAdaptationEvaluation {
  if (roadmap.length === 0) {
    return {
      adaptationCount: 0,
      affectedStageIds: [],
      adaptations: [],
    };
  }

  const adaptations: RoadmapAdaptation[] = [];

  const validationStageId = findStageId(roadmap, [
    "validate",
    "evaluation",
    "test",
    "package",
  ]);

  const extensionStageId = findStageId(roadmap, [
    "extend",
    "extension",
    "advanced",
    "package",
  ]);

  const implementationStageId = findStageId(roadmap, [
    "mvp",
    "build",
    "implement",
    "define",
  ]);

  const packagingStageId = findStageId(roadmap, [
    "package",
    "deploy",
    "extend",
  ]);

  if (
    validationStageId &&
    decisionConsequences.validationFocus.length > 0
  ) {
    const metrics = decisionConsequences.validationFocus;

    addAdaptation(adaptations, {
      targetStageId: validationStageId,
      category: "validation",
      title: "Carry the selected metric into validation",
      rationale:
        "The user explicitly selected a validation signal, so later evaluation should measure and save it.",
      suggestedTasks: [
        `Run evaluation using ${metrics.join(", ")}.`,
        `Save a baseline and final ${metrics.join(", ")} result.`,
      ],
      suggestedAcceptanceCriteria: [
        `A saved evaluation artifact reports ${metrics.join(", ")}.`,
      ],
      suggestedValidationChecks: metrics.map(
        (metric) =>
          `Verify that the evaluation output contains ${metric}.`,
      ),
      suggestedUnlockCondition:
        `Do not complete validation until ${metrics.join(", ")} has been measured and saved.`,
    });
  }

  if (
    extensionStageId &&
    decisionConsequences.deferredItems.length > 0
  ) {
    const deferredItems = decisionConsequences.deferredItems;

    addAdaptation(adaptations, {
      targetStageId: extensionStageId,
      category: "scope",
      title: "Revisit intentionally deferred scope",
      rationale:
        "The user kept these items outside the MVP, so they belong in extension planning rather than blocking the first working version.",
      suggestedTasks: deferredItems.map(
        (item) => `Evaluate whether to add deferred item: ${item}.`,
      ),
      suggestedAcceptanceCriteria: [
        "Each deferred item is either implemented, explicitly rejected, or documented as future work.",
      ],
      suggestedValidationChecks: [],
      suggestedUnlockCondition: null,
    });
  }

  if (
    implementationStageId &&
    decisionConsequences.architectureSignals.length > 0
  ) {
    const signals = decisionConsequences.architectureSignals;

    addAdaptation(adaptations, {
      targetStageId: implementationStageId,
      category: "architecture",
      title: "Align implementation with the chosen architecture",
      rationale:
        "Captured architecture decisions should influence persistence, recovery, and deployment checks.",
      suggestedTasks: [
        `Document how ${signals.join(", ")} fits into the system boundary.`,
      ],
      suggestedAcceptanceCriteria: [
        `The implementation and architecture notes consistently reflect ${signals.join(", ")}.`,
      ],
      suggestedValidationChecks: [
        `Verify startup, persistence, reload, and failure behavior for ${signals.join(", ")}.`,
      ],
      suggestedUnlockCondition: null,
    });
  }

  if (
    validationStageId &&
    decisionConsequences.priorities.includes("performance")
  ) {
    addAdaptation(adaptations, {
      targetStageId: validationStageId,
      category: "performance",
      title: "Add measurable performance validation",
      rationale:
        "Performance was explicitly prioritized, so packaging should not proceed without a measurable result.",
      suggestedTasks: [
        "Measure latency or throughput using a repeatable test input.",
      ],
      suggestedAcceptanceCriteria: [
        "A saved performance result includes the test setup and observed value.",
      ],
      suggestedValidationChecks: [
        "Repeat the performance measurement and confirm the result is reproducible.",
      ],
      suggestedUnlockCondition:
        "Save at least one reproducible performance measurement.",
    });
  }

  if (
    packagingStageId &&
    decisionConsequences.priorities.includes("cost")
  ) {
    addAdaptation(adaptations, {
      targetStageId: packagingStageId,
      category: "cost",
      title: "Document the project cost boundary",
      rationale:
        "Cost was an explicit engineering priority and should be visible in deployment and portfolio documentation.",
      suggestedTasks: [
        "Document free-tier assumptions and any paid dependency threshold.",
      ],
      suggestedAcceptanceCriteria: [
        "The README identifies expected local, hosted, and API costs.",
      ],
      suggestedValidationChecks: [],
      suggestedUnlockCondition: null,
    });
  }

  if (
    implementationStageId &&
    decisionConsequences.priorities.includes("simplicity")
  ) {
    addAdaptation(adaptations, {
      targetStageId: implementationStageId,
      category: "simplicity",
      title: "Protect the simpler MVP design",
      rationale:
        "Simplicity was explicitly prioritized, so additional complexity should require evidence.",
      suggestedTasks: [
        "Document which advanced components were intentionally excluded.",
      ],
      suggestedAcceptanceCriteria: [
        "The MVP completes one end-to-end workflow without unnecessary infrastructure.",
      ],
      suggestedValidationChecks: [],
      suggestedUnlockCondition: null,
    });
  }

  const hasSecurityConsequence =
    decisionConsequences.consequences.some(
      (consequence) => consequence.category === "security",
    );

  if (extensionStageId && hasSecurityConsequence) {
    addAdaptation(adaptations, {
      targetStageId: extensionStageId,
      category: "security",
      title: "Add security follow-up validation",
      rationale:
        "A captured decision introduced a security consequence that should be addressed before production use.",
      suggestedTasks: [
        "Document the trust boundary and add the deferred security control.",
      ],
      suggestedAcceptanceCriteria: [
        "Authentication, authorization, privacy, or encryption behavior is documented and tested where applicable.",
      ],
      suggestedValidationChecks: [
        "Test one unauthorized or invalid-access scenario.",
      ],
      suggestedUnlockCondition: null,
    });
  }

  return {
    adaptationCount: adaptations.length,
    affectedStageIds: unique(
      adaptations.map((adaptation) => adaptation.targetStageId),
    ),
    adaptations,
  };
}
