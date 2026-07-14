import { describe, expect, it } from "vitest";

import {
  CURRENT_WORKSPACE_SCHEMA_VERSION,
  createWorkspaceBackup,
  createWorkspaceBackupFilename,
  importWorkspaceBackup,
  migrateWorkspace,
  parseWorkspace,
  readWorkspaceFromStorage,
  removeWorkspaceFromStorage,
  serializeWorkspace,
  writeWorkspaceToStorage,
  type WorkspaceStorage,
} from "./workspacePersistence";

type ReadyResult = {
  status: "ready";
  response_schema_version?: number;
  persistence?: {
    roadmap_registry: {
      status: string;
      remediation: string | null;
    };
  };
  directions: Array<{
    id: string;
    project_direction_id?: string | null;
  }>;
};

const readyResult: ReadyResult = {
  status: "ready",
  directions: [],
};

describe("workspace persistence", () => {
  it("migrates an unversioned workspace with safe defaults", () => {
    const result = migrateWorkspace<ReadyResult>({
      goal: "Build a retrieval project",
      result: {
        status: "ready",
        response_schema_version: 1,
        persistence: {
          roadmap_registry: {
            status: "unavailable_error",
            remediation:
              "This workspace predates trusted " +
              "roadmap persistence.",
          },
        },
        directions: [],
      },
      selectedDirectionId: "retrieval",
      activeRoadmapNodeId: "define",
      completedRoadmapNodeIds: ["define"],
      savedAt: "2026-07-12T18:00:00.000Z",
    });

    expect(result).toEqual({
      schemaVersion: CURRENT_WORKSPACE_SCHEMA_VERSION,
      goal: "Build a retrieval project",
      result: {
        status: "ready",
        response_schema_version: 1,
        persistence: {
          roadmap_registry: {
            status: "unavailable_error",
            remediation:
              "This workspace predates trusted " +
              "roadmap persistence.",
          },
        },
        directions: [],
      },
      selectedDirectionId: "retrieval",
      activeRoadmapNodeId: "define",
      completedRoadmapNodeIds: ["define"],
      guidedStepProofs: {},
      decisionAnswers: {},
      completedGuidedStepIds: [],
      adaptationDecisions: {},
      adaptationEvidence: {},
      savedAt: "2026-07-12T18:00:00.000Z",
    });
  });

  it("preserves trusted roadmap identities", () => {
    const result = migrateWorkspace<ReadyResult>({
      schemaVersion: 2,
      goal: "Build a retrieval project",
      result: {
        status: "ready",
        response_schema_version: 2,
        persistence: {
          roadmap_registry: {
            status: "ready",
            remediation: null,
          },
        },
        directions: [
          {
            id: "direction-1",
            project_direction_id:
              "trusted-project-direction",
          },
        ],
      },
      savedAt: "2026-07-12T18:00:00.000Z",
    });

    expect(
      result?.result.response_schema_version,
    ).toBe(2);
    expect(
      result?.result.persistence
        ?.roadmap_registry.status,
    ).toBe("ready");
    expect(
      result?.result.directions[0]
        .project_direction_id,
    ).toBe("trusted-project-direction");
  });

  it("normalizes missing direction identities to null", () => {
    const result = migrateWorkspace<ReadyResult>({
      goal: "Legacy retrieval project",
      result: {
        status: "ready",
        directions: [
          {
            id: "direction-1",
          },
        ],
      },
      savedAt: "2026-07-12T18:00:00.000Z",
    });

    expect(
      result?.result.directions[0]
        .project_direction_id,
    ).toBeNull();
    expect(
      result?.result.persistence
        ?.roadmap_registry.status,
    ).toBe("unavailable_error");
  });

  it("preserves current adaptation state", () => {
    const result = migrateWorkspace<ReadyResult>({
      schemaVersion: 2,
      goal: "Build a retrieval project",
      result: readyResult,
      selectedDirectionId: "retrieval",
      activeRoadmapNodeId: "validate",
      completedRoadmapNodeIds: ["define"],
      guidedStepProofs: {
        "define:scope": "Saved scope.",
      },
      decisionAnswers: {
        "define:scope": "Use precision@3.",
      },
      completedGuidedStepIds: ["define:scope"],
      adaptationDecisions: {
        "validate:validation": {
          adaptationKey: "validate:validation",
          status: "accepted",
          rationale: "Use the selected metric.",
          decidedAt: "2026-07-12T18:00:00.000Z",
        },
      },
      adaptationEvidence: {
        "validate:validation": "precision@3 = 0.81",
      },
      savedAt: "2026-07-12T18:00:00.000Z",
    });

    expect(
      result?.adaptationDecisions["validate:validation"]
        .status,
    ).toBe("accepted");
    expect(
      result?.adaptationEvidence["validate:validation"],
    ).toBe("precision@3 = 0.81");
  });

  it("filters malformed collection values", () => {
    const result = migrateWorkspace<ReadyResult>({
      goal: 123,
      result: readyResult,
      completedRoadmapNodeIds: ["define", 4, null],
      guidedStepProofs: {
        valid: "proof",
        invalid: 9,
      },
      completedGuidedStepIds: "not-an-array",
      adaptationEvidence: {
        valid: "evidence",
        invalid: false,
      },
    });

    expect(result?.goal).toBe("");
    expect(result?.completedRoadmapNodeIds).toEqual([
      "define",
    ]);
    expect(result?.guidedStepProofs).toEqual({
      valid: "proof",
    });
    expect(result?.completedGuidedStepIds).toEqual([]);
    expect(result?.adaptationEvidence).toEqual({
      valid: "evidence",
    });
  });

  it("rejects missing or non-ready results", () => {
    expect(migrateWorkspace({ goal: "Missing result" })).toBeNull();

    expect(
      migrateWorkspace({
        goal: "Clarification",
        result: {
          status: "clarification_required",
        },
      }),
    ).toBeNull();
  });

  it("returns null for malformed JSON", () => {
    expect(parseWorkspace("{bad-json")).toBeNull();
    expect(parseWorkspace(null)).toBeNull();
  });

  it("serializes using the current schema version", () => {
    const raw = serializeWorkspace({
      goal: "Build a retrieval project",
      result: readyResult,
      selectedDirectionId: null,
      activeRoadmapNodeId: null,
      completedRoadmapNodeIds: [],
      guidedStepProofs: {},
      decisionAnswers: {},
      completedGuidedStepIds: [],
      adaptationDecisions: {},
      adaptationEvidence: {},
      savedAt: "2026-07-12T18:00:00.000Z",
    });

    expect(JSON.parse(raw)).toMatchObject({
      schemaVersion: CURRENT_WORKSPACE_SCHEMA_VERSION,
      goal: "Build a retrieval project",
    });
  });

  it("reads a valid workspace from storage", () => {
    const raw = serializeWorkspace({
      goal: "Build a retrieval project",
      result: readyResult,
      selectedDirectionId: null,
      activeRoadmapNodeId: null,
      completedRoadmapNodeIds: [],
      guidedStepProofs: {},
      decisionAnswers: {},
      completedGuidedStepIds: [],
      adaptationDecisions: {},
      adaptationEvidence: {},
      savedAt: "2026-07-12T18:00:00.000Z",
    });

    const storage: WorkspaceStorage = {
      getItem: () => raw,
      setItem: () => undefined,
      removeItem: () => undefined,
    };

    expect(
      readWorkspaceFromStorage<ReadyResult>(storage)?.goal,
    ).toBe("Build a retrieval project");
  });

  it("removes malformed stored workspace data", () => {
    let removedKey: string | null = null;

    const storage: WorkspaceStorage = {
      getItem: () => "{bad-json",
      setItem: () => undefined,
      removeItem: (key) => {
        removedKey = key;
      },
    };

    expect(
      readWorkspaceFromStorage<ReadyResult>(storage),
    ).toBeNull();
    expect(removedKey).toBe("solvyn:last-workspace");
  });

  it("fails safely when storage reads are blocked", () => {
    const storage: WorkspaceStorage = {
      getItem: () => {
        throw new Error("Storage blocked");
      },
      setItem: () => undefined,
      removeItem: () => undefined,
    };

    expect(
      readWorkspaceFromStorage<ReadyResult>(storage),
    ).toBeNull();
  });

  it("returns false when a workspace write fails", () => {
    const storage: WorkspaceStorage = {
      getItem: () => null,
      setItem: () => {
        throw new Error("Quota exceeded");
      },
      removeItem: () => undefined,
    };

    expect(
      writeWorkspaceToStorage(storage, {
        goal: "Build a retrieval project",
        result: readyResult,
        selectedDirectionId: null,
        activeRoadmapNodeId: null,
        completedRoadmapNodeIds: [],
        guidedStepProofs: {},
        decisionAnswers: {},
        completedGuidedStepIds: [],
        adaptationDecisions: {},
        adaptationEvidence: {},
        savedAt: "2026-07-12T18:00:00.000Z",
      }),
    ).toBe(false);
  });

  it("returns false when workspace removal fails", () => {
    const storage: WorkspaceStorage = {
      getItem: () => null,
      setItem: () => undefined,
      removeItem: () => {
        throw new Error("Storage blocked");
      },
    };

    expect(removeWorkspaceFromStorage(storage)).toBe(false);
  });

  it("creates a readable versioned workspace backup", () => {
    const backup = createWorkspaceBackup({
      goal: "Build a retrieval project",
      result: readyResult,
      selectedDirectionId: "retrieval",
      activeRoadmapNodeId: "validate",
      completedRoadmapNodeIds: ["define"],
      guidedStepProofs: {
        "define:scope": "Saved scope.",
      },
      decisionAnswers: {
        "define:scope": "Use precision@3.",
      },
      completedGuidedStepIds: ["define:scope"],
      adaptationDecisions: {},
      adaptationEvidence: {},
      savedAt: "2026-07-12T18:00:00.000Z",
    });

    expect(backup).toContain('"schemaVersion": 2');
    expect(backup).toContain('"goal": "Build a retrieval project"');
    expect(backup.split("\n").length).toBeGreaterThan(1);
  });

  it("imports and migrates a valid workspace backup", () => {
    const result = importWorkspaceBackup<ReadyResult>(
      JSON.stringify({
        goal: "Imported retrieval project",
        result: readyResult,
        selectedDirectionId: "retrieval",
        activeRoadmapNodeId: null,
        completedRoadmapNodeIds: [],
        savedAt: "2026-07-12T18:00:00.000Z",
      }),
    );

    expect(result.status).toBe("success");

    if (result.status === "success") {
      expect(result.workspace.schemaVersion).toBe(
        CURRENT_WORKSPACE_SCHEMA_VERSION,
      );
      expect(result.workspace.goal).toBe(
        "Imported retrieval project",
      );
      expect(result.workspace.guidedStepProofs).toEqual({});
      expect(result.workspace.adaptationDecisions).toEqual({});
    }
  });

  it("rejects empty workspace backup content", () => {
    expect(importWorkspaceBackup<ReadyResult>("   ")).toEqual({
      status: "error",
      message: "The selected workspace backup is empty.",
    });
  });

  it("rejects malformed workspace backup JSON", () => {
    expect(
      importWorkspaceBackup<ReadyResult>("{bad-json"),
    ).toEqual({
      status: "error",
      message: "The selected file is not valid JSON.",
    });
  });

  it("rejects a non-ready workspace backup", () => {
    expect(
      importWorkspaceBackup<ReadyResult>(
        JSON.stringify({
          goal: "Invalid backup",
          result: {
            status: "clarification_required",
          },
        }),
      ),
    ).toEqual({
      status: "error",
      message:
        "The selected file is not a valid ready Solvyn workspace.",
    });
  });

  it("creates a stable backup filename", () => {
    expect(
      createWorkspaceBackupFilename(
        "Grounded Retrieval System",
        "2026-07-12T18:00:00.000Z",
      ),
    ).toBe(
      "solvyn-grounded-retrieval-system-2026-07-12.json",
    );
  });

  it("sanitizes unusual titles and invalid dates", () => {
    expect(
      createWorkspaceBackupFilename(
        "  RAG + Search / Demo!  ",
        "not-a-date",
      ),
    ).toBe("solvyn-rag-search-demo-undated.json");
  });
});
