import type { DecisionEntry } from "./portfolioSummary";

export type DecisionConsequenceCategory =
  | "scope"
  | "validation"
  | "architecture"
  | "performance"
  | "security"
  | "cost"
  | "simplicity"
  | "general";

export type DecisionConsequence = {
  missionId: string;
  stepId: string;
  category: DecisionConsequenceCategory;
  summary: string;
  recommendedAdjustment: string;
};

export type DecisionConsequenceEvaluation = {
  decisionCount: number;
  consequences: DecisionConsequence[];
  validationFocus: string[];
  deferredItems: string[];
  architectureSignals: string[];
  priorities: string[];
};

const VALIDATION_METRICS = [
  "precision@1",
  "precision@3",
  "precision@5",
  "recall@1",
  "recall@3",
  "recall@5",
  "mrr",
  "ndcg",
  "latency",
  "accuracy",
  "f1",
  "precision",
  "recall",
  "throughput",
  "response time",
];

const ARCHITECTURE_SIGNALS = [
  "faiss",
  "postgres",
  "postgresql",
  "redis",
  "sqlite",
  "mysql",
  "mongodb",
  "pinecone",
  "weaviate",
  "qdrant",
  "chroma",
  "local index",
  "hosted database",
  "vector database",
  "serverless",
  "docker",
  "kubernetes",
  "microservice",
  "monolith",
];

const DEFERRED_ITEM_PATTERNS = [
  /(?:defer|deferred|postpone|postponed|later|leave out|left out|exclude|excluded|skip|skipped)\s+(?:the\s+)?([^.,;]+)/gi,
  /(?:not include|not implementing|not implement)\s+(?:the\s+)?([^.,;]+)/gi,
];

function normalize(value: string): string {
  return value.toLowerCase().trim();
}

function unique(items: string[]): string[] {
  return [...new Set(items.map((item) => item.trim()).filter(Boolean))];
}

function includesAny(text: string, terms: string[]): boolean {
  return terms.some((term) => text.includes(term));
}

function extractMatchingTerms(text: string, terms: string[]): string[] {
  const matches = terms.filter((term) => text.includes(term));

  return matches.filter(
    (term) =>
      !matches.some(
        (moreSpecificTerm) =>
          moreSpecificTerm !== term &&
          moreSpecificTerm.length > term.length &&
          moreSpecificTerm.includes(term),
      ),
  );
}

function extractDeferredItems(answer: string): string[] {
  const items: string[] = [];

  for (const pattern of DEFERRED_ITEM_PATTERNS) {
    pattern.lastIndex = 0;

    let match = pattern.exec(answer);

    while (match) {
      const item = match[1]?.trim();

      if (item) {
        items.push(item);
      }

      match = pattern.exec(answer);
    }
  }

  return unique(items);
}

function classifyDecision(
  decision: DecisionEntry,
): DecisionConsequenceCategory {
  const text = normalize(
    `${decision.decisionPoint} ${decision.answer}`,
  );

  if (
    includesAny(text, [
      "metric",
      "measure",
      "validation",
      "precision",
      "recall",
      "accuracy",
      "latency",
      "mrr",
      "ndcg",
      "f1",
    ])
  ) {
    return "validation";
  }

  if (
    includesAny(text, [
      "defer",
      "postpone",
      "leave out",
      "left out",
      "exclude",
      "skip",
      "mvp",
      "scope",
    ])
  ) {
    return "scope";
  }

  if (
    includesAny(text, [
      "architecture",
      "database",
      "faiss",
      "redis",
      "postgres",
      "sqlite",
      "vector",
      "serverless",
      "docker",
      "kubernetes",
      "monolith",
      "microservice",
    ])
  ) {
    return "architecture";
  }

  if (
    includesAny(text, [
      "performance",
      "latency",
      "speed",
      "throughput",
      "fast",
      "scalability",
      "scale",
    ])
  ) {
    return "performance";
  }

  if (
    includesAny(text, [
      "security",
      "authentication",
      "authorization",
      "privacy",
      "encrypt",
    ])
  ) {
    return "security";
  }

  if (
    includesAny(text, [
      "cost",
      "cheap",
      "budget",
      "free tier",
      "api credits",
    ])
  ) {
    return "cost";
  }

  if (
    includesAny(text, [
      "simple",
      "simplicity",
      "minimal",
      "easy to debug",
      "maintainable",
    ])
  ) {
    return "simplicity";
  }

  return "general";
}

function buildAdjustment(
  category: DecisionConsequenceCategory,
  decision: DecisionEntry,
  metrics: string[],
  deferredItems: string[],
  architectureSignals: string[],
): string {
  if (category === "validation") {
    return metrics.length > 0
      ? `Use ${metrics.join(", ")} in later validation steps and saved evaluation outputs.`
      : "Carry this validation choice into later tests and saved evaluation outputs.";
  }

  if (category === "scope") {
    return deferredItems.length > 0
      ? `Keep ${deferredItems.join(", ")} outside the MVP and revisit it during extension planning.`
      : "Keep the MVP boundary explicit and move excluded work into later extensions.";
  }

  if (category === "architecture") {
    return architectureSignals.length > 0
      ? `Align later implementation, persistence, and deployment checks with ${architectureSignals.join(", ")}.`
      : "Carry this architecture choice into persistence, deployment, and failure-recovery checks.";
  }

  if (category === "performance") {
    return "Add measurable performance checks before packaging the project.";
  }

  if (category === "security") {
    return "Add a later security validation step covering the chosen trust boundary.";
  }

  if (category === "cost") {
    return "Prefer low-cost defaults and document when a paid dependency becomes necessary.";
  }

  if (category === "simplicity") {
    return "Preserve the simpler design until evidence shows additional complexity is necessary.";
  }

  return `Carry this decision from ${decision.missionTitle} into later implementation and interview explanations.`;
}

export function evaluateDecisionConsequences(
  decisions: DecisionEntry[],
): DecisionConsequenceEvaluation {
  const consequences: DecisionConsequence[] = [];
  const validationFocus: string[] = [];
  const deferredItems: string[] = [];
  const architectureSignals: string[] = [];
  const priorities: string[] = [];

  for (const decision of decisions) {
    const normalizedAnswer = normalize(decision.answer);
    const normalizedText = normalize(
      `${decision.decisionPoint} ${decision.answer}`,
    );
    const category = classifyDecision(decision);
    const decisionMetrics = extractMatchingTerms(
      normalizedText,
      VALIDATION_METRICS,
    );
    const decisionDeferredItems = extractDeferredItems(
      decision.answer,
    );
    const decisionArchitectureSignals = extractMatchingTerms(
      normalizedText,
      ARCHITECTURE_SIGNALS,
    );

    validationFocus.push(...decisionMetrics);
    deferredItems.push(...decisionDeferredItems);
    architectureSignals.push(...decisionArchitectureSignals);

    if (
      includesAny(normalizedAnswer, [
        "performance",
        "latency",
        "speed",
        "throughput",
        "fast",
      ])
    ) {
      priorities.push("performance");
    }

    if (
      includesAny(normalizedAnswer, [
        "simple",
        "simplicity",
        "minimal",
        "maintainable",
      ])
    ) {
      priorities.push("simplicity");
    }

    if (
      includesAny(normalizedAnswer, [
        "cost",
        "budget",
        "cheap",
        "free tier",
      ])
    ) {
      priorities.push("cost");
    }

    consequences.push({
      missionId: decision.missionId,
      stepId: decision.stepId,
      category,
      summary: decision.answer,
      recommendedAdjustment: buildAdjustment(
        category,
        decision,
        decisionMetrics,
        decisionDeferredItems,
        decisionArchitectureSignals,
      ),
    });
  }

  return {
    decisionCount: decisions.length,
    consequences,
    validationFocus: unique(validationFocus),
    deferredItems: unique(deferredItems),
    architectureSignals: unique(architectureSignals),
    priorities: unique(priorities),
  };
}
