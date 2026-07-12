import type { AdaptationDecisionMap } from "./roadmapAdaptationState";

export const WORKSPACE_STORAGE_KEY = "solvyn:last-workspace";
export const CURRENT_WORKSPACE_SCHEMA_VERSION = 2;

export type PersistedWorkspace<TResult> = {
  schemaVersion: number;
  goal: string;
  result: TResult;
  selectedDirectionId: string | null;
  activeRoadmapNodeId: string | null;
  completedRoadmapNodeIds: string[];
  guidedStepProofs: Record<string, string>;
  decisionAnswers: Record<string, string>;
  completedGuidedStepIds: string[];
  adaptationDecisions: AdaptationDecisionMap;
  adaptationEvidence: Record<string, string>;
  savedAt: string;
};

type UnknownRecord = Record<string, unknown>;

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function stringValue(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function nullableString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function stringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.filter(
    (item): item is string => typeof item === "string",
  );
}

function stringRecord(value: unknown): Record<string, string> {
  if (!isRecord(value)) {
    return {};
  }

  return Object.fromEntries(
    Object.entries(value).filter(
      (entry): entry is [string, string] =>
        typeof entry[1] === "string",
    ),
  );
}

function adaptationDecisionMap(
  value: unknown,
): AdaptationDecisionMap {
  if (!isRecord(value)) {
    return {};
  }

  return Object.fromEntries(
    Object.entries(value).filter(([, decision]) => {
      if (!isRecord(decision)) {
        return false;
      }

      return (
        typeof decision.adaptationKey === "string" &&
        ["accepted", "rejected", "deferred"].includes(
          stringValue(decision.status),
        ) &&
        typeof decision.rationale === "string" &&
        typeof decision.decidedAt === "string"
      );
    }),
  ) as AdaptationDecisionMap;
}

export function migrateWorkspace<TResult>(
  value: unknown,
): PersistedWorkspace<TResult> | null {
  if (!isRecord(value) || !isRecord(value.result)) {
    return null;
  }

  if (value.result.status !== "ready") {
    return null;
  }

  return {
    schemaVersion: CURRENT_WORKSPACE_SCHEMA_VERSION,
    goal: stringValue(value.goal),
    result: value.result as TResult,
    selectedDirectionId: nullableString(
      value.selectedDirectionId,
    ),
    activeRoadmapNodeId: nullableString(
      value.activeRoadmapNodeId,
    ),
    completedRoadmapNodeIds: stringArray(
      value.completedRoadmapNodeIds,
    ),
    guidedStepProofs: stringRecord(value.guidedStepProofs),
    decisionAnswers: stringRecord(value.decisionAnswers),
    completedGuidedStepIds: stringArray(
      value.completedGuidedStepIds,
    ),
    adaptationDecisions: adaptationDecisionMap(
      value.adaptationDecisions,
    ),
    adaptationEvidence: stringRecord(
      value.adaptationEvidence,
    ),
    savedAt:
      stringValue(value.savedAt) || new Date(0).toISOString(),
  };
}

export function parseWorkspace<TResult>(
  rawWorkspace: string | null,
): PersistedWorkspace<TResult> | null {
  if (!rawWorkspace) {
    return null;
  }

  try {
    return migrateWorkspace<TResult>(
      JSON.parse(rawWorkspace) as unknown,
    );
  } catch {
    return null;
  }
}

export function serializeWorkspace<TResult>(
  workspace: Omit<
    PersistedWorkspace<TResult>,
    "schemaVersion"
  >,
): string {
  return JSON.stringify({
    ...workspace,
    schemaVersion: CURRENT_WORKSPACE_SCHEMA_VERSION,
  });
}

export type WorkspaceStorage = Pick<
  Storage,
  "getItem" | "setItem" | "removeItem"
>;

export function readWorkspaceFromStorage<TResult>(
  storage: WorkspaceStorage,
): PersistedWorkspace<TResult> | null {
  try {
    const rawWorkspace = storage.getItem(WORKSPACE_STORAGE_KEY);
    const workspace = parseWorkspace<TResult>(rawWorkspace);

    if (!workspace && rawWorkspace) {
      try {
        storage.removeItem(WORKSPACE_STORAGE_KEY);
      } catch {
        return null;
      }
    }

    return workspace;
  } catch {
    return null;
  }
}

export function writeWorkspaceToStorage<TResult>(
  storage: WorkspaceStorage,
  workspace: Omit<
    PersistedWorkspace<TResult>,
    "schemaVersion"
  >,
): boolean {
  try {
    storage.setItem(
      WORKSPACE_STORAGE_KEY,
      serializeWorkspace(workspace),
    );
    return true;
  } catch {
    return false;
  }
}

export function removeWorkspaceFromStorage(
  storage: WorkspaceStorage,
): boolean {
  try {
    storage.removeItem(WORKSPACE_STORAGE_KEY);
    return true;
  } catch {
    return false;
  }
}

export type WorkspaceImportResult<TResult> =
  | {
      status: "success";
      workspace: PersistedWorkspace<TResult>;
    }
  | {
      status: "error";
      message: string;
    };

export function createWorkspaceBackup<TResult>(
  workspace: Omit<
    PersistedWorkspace<TResult>,
    "schemaVersion"
  >,
): string {
  return JSON.stringify(
    {
      ...workspace,
      schemaVersion: CURRENT_WORKSPACE_SCHEMA_VERSION,
    },
    null,
    2,
  );
}

export function importWorkspaceBackup<TResult>(
  rawBackup: string,
): WorkspaceImportResult<TResult> {
  if (!rawBackup.trim()) {
    return {
      status: "error",
      message: "The selected workspace backup is empty.",
    };
  }

  let parsedBackup: unknown;

  try {
    parsedBackup = JSON.parse(rawBackup) as unknown;
  } catch {
    return {
      status: "error",
      message: "The selected file is not valid JSON.",
    };
  }

  const workspace = migrateWorkspace<TResult>(parsedBackup);

  if (!workspace) {
    return {
      status: "error",
      message:
        "The selected file is not a valid ready Solvyn workspace.",
    };
  }

  return {
    status: "success",
    workspace,
  };
}

export function createWorkspaceBackupFilename(
  projectTitle: string,
  savedAt: string,
): string {
  const normalizedTitle =
    projectTitle
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "") || "project";

  const parsedDate = new Date(savedAt);
  const date =
    Number.isNaN(parsedDate.getTime())
      ? "undated"
      : parsedDate.toISOString().slice(0, 10);

  return `solvyn-${normalizedTitle}-${date}.json`;
}
