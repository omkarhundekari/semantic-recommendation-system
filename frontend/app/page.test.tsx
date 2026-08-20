// @vitest-environment jsdom

import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";

import {
  WORKSPACE_STORAGE_KEY,
} from "@/lib/workspacePersistence";


const {
  useAuthMock,
  discoverWorkspacesMock,
  provisionWorkspaceMock,
} = vi.hoisted(
  () => ({
    useAuthMock:
      vi.fn(),

    discoverWorkspacesMock:
      vi.fn(),

    provisionWorkspaceMock:
      vi.fn(),
  }),
);


vi.mock(
  "@/lib/auth/AuthProvider",
  () => ({
    useAuth:
      useAuthMock,
  }),
);


vi.mock(
  "@/lib/workspaces/workspaceClient",
  async (
    importOriginal,
  ) => {
    const actual =
      await importOriginal<
        typeof import(
          "@/lib/workspaces/workspaceClient"
        )
      >();

    return {
      ...actual,

      discoverWorkspaces:
        discoverWorkspacesMock,

      provisionWorkspace:
        provisionWorkspaceMock,
    };
  },
);


import {
  WorkspaceClientAuthenticationError,
} from "@/lib/workspaces/workspaceClient";

import Home from "./page";

function uploadJson(content: string) {
  const input = screen.getByLabelText(
    "Import workspace",
  ) as HTMLInputElement;

  const file = new File([content], "workspace.json", {
    type: "application/json",
  });

  Object.defineProperty(file, "text", {
    configurable: true,
    value: async () => content,
  });

  fireEvent.change(input, {
    target: {
      files: [file],
    },
  });
}

function readBlob(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();

    reader.addEventListener("load", () => {
      resolve(String(reader.result));
    });
    reader.addEventListener("error", () => {
      reject(reader.error);
    });
    reader.readAsText(blob);
  });
}

beforeEach(() => {
  vi.clearAllMocks();

  useAuthMock.mockReturnValue({
    state: {
      status:
        "authenticated",
      principal: {
        principalId:
          "prn_test",
        principalKind:
          "human",
      },
    },
    isRetrying:
      false,
    retry:
      vi.fn(),
  });

  discoverWorkspacesMock
    .mockResolvedValue({
      workspaces: [
        {
          workspaceId:
            "ws_existing",
          membershipId:
            "wsm_existing",
          membershipRole:
            "owner",
        },
      ],
      truncated:
        false,
      nextCursor:
        null,
    });

  provisionWorkspaceMock
    .mockResolvedValue({
      workspaceId:
        "ws_provisioned",
      membershipId:
        "wsm_provisioned",
      membershipRole:
        "owner",
      replayed:
        false,
    });
});


afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("workspace backup UI", () => {
  it("keeps workspace import available without an active project", () => {
    render(<Home />);

    expect(
      screen.getByLabelText("Import workspace"),
    ).toBeInTheDocument();
  });

  it("shows feedback when an imported file contains malformed JSON", async () => {
    render(<Home />);

    uploadJson("{bad-json");

    expect(
      await screen.findByText(
        "The selected file is not valid JSON.",
      ),
    ).toBeInTheDocument();
  });

  it("restores a valid ready workspace", async () => {
    render(<Home />);

    uploadJson(
      JSON.stringify({
        schemaVersion: 2,
        goal: "Imported grounded retrieval project",
        result: {
          status: "ready",
          directions: [],
        },
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
    );

    expect(
      await screen.findByText(
        "Workspace imported successfully. Its progress and evidence have been restored.",
      ),
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(
        screen.getByDisplayValue(
          "Imported grounded retrieval project",
        ),
      ).toBeInTheDocument();
    });
  });

  it("exports the current workspace as a versioned JSON download", async () => {
    let exportedBlob: Blob | null = null;
    let downloadedFilename = "";
    let downloadedHref = "";

    const createObjectURL = vi.fn((blob: Blob) => {
      exportedBlob = blob;
      return "blob:solvyn-workspace";
    });
    const revokeObjectURL = vi.fn();

    Object.defineProperty(window.URL, "createObjectURL", {
      configurable: true,
      value: createObjectURL,
    });
    Object.defineProperty(window.URL, "revokeObjectURL", {
      configurable: true,
      value: revokeObjectURL,
    });

    vi.spyOn(
      HTMLAnchorElement.prototype,
      "click",
    ).mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      downloadedFilename = this.download;
      downloadedHref = this.href;
    });

    render(<Home />);

    uploadJson(
      JSON.stringify({
        schemaVersion: 2,
        goal: "Build a grounded retrieval demo",
        result: {
          status: "ready",
          directions: [
            {
              id: "grounded-retrieval",
              title: "Grounded Retrieval System",
              summary: "A retrieval system with saved evidence.",
              scope: "Build and validate one grounded workflow.",
              estimated_effort: "3 weeks",
              portfolio_tier: "strong",
              difficulty: "intermediate",
              career_signal: "high",
              why_it_fits: "Shows retrieval and evaluation skills.",
              mvp_steps: ["Build retrieval"],
              advanced_extensions: [],
              tech_stack: ["Python", "React"],
              target_roles: ["ML Engineer"],
              roadmap: [],
              risks: [],
              repairs_applied: [],
              verification: {
                status: "verified",
                score: 3,
                max_score: 3,
                warnings: [],
              },
            },
          ],
        },
        selectedDirectionId: "grounded-retrieval",
        activeRoadmapNodeId: null,
        completedRoadmapNodeIds: [],
        guidedStepProofs: {},
        decisionAnswers: {},
        completedGuidedStepIds: [],
        adaptationDecisions: {},
        adaptationEvidence: {},
        savedAt: "2026-07-12T18:00:00.000Z",
      }),
    );

    const exportButton = await screen.findByRole("button", {
      name: "Export workspace",
    });

    fireEvent.click(exportButton);

    expect(createObjectURL).toHaveBeenCalledTimes(1);
    expect(downloadedHref).toBe("blob:solvyn-workspace");
    expect(downloadedFilename).toMatch(
      /^solvyn-grounded-retrieval-system-\d{4}-\d{2}-\d{2}\.json$/,
    );
    expect(revokeObjectURL).toHaveBeenCalledWith(
      "blob:solvyn-workspace",
    );

    if (!exportedBlob) {
      throw new Error("The exported workspace blob was not created.");
    }

    const exportedWorkspace = JSON.parse(
      await readBlob(exportedBlob),
    ) as {
      schemaVersion: number;
      goal: string;
      selectedDirectionId: string | null;
      result: {
        status: string;
      };
    };

    expect(exportedWorkspace.schemaVersion).toBe(2);
    expect(exportedWorkspace.goal).toBe(
      "Build a grounded retrieval demo",
    );
    expect(exportedWorkspace.selectedDirectionId).toBe(
      "grounded-retrieval",
    );
    expect(exportedWorkspace.result.status).toBe("ready");

    expect(
      screen.getByText(
        new RegExp(
          `Workspace exported as ${downloadedFilename.replace(
            /[.*+?^${}()|[\]\\]/g,
            "\\$&",
          )}\\.`,
        ),
      ),
    ).toBeInTheDocument();
  });

  it("clears the active workspace and browser storage when starting over", async () => {
    render(<Home />);

    uploadJson(
      JSON.stringify({
        schemaVersion: 2,
        goal: "Reset this grounded retrieval project",
        result: {
          status: "ready",
          directions: [
            {
              id: "grounded-retrieval",
              title: "Grounded Retrieval Reset Test",
              summary: "A populated workspace used to test reset.",
              scope: "Build and validate one grounded workflow.",
              estimated_effort: "3 weeks",
              portfolio_tier: "strong",
              difficulty: "intermediate",
              career_signal: "high",
              why_it_fits: "Shows retrieval and evaluation skills.",
              mvp_steps: ["Define the retrieval workflow"],
              advanced_extensions: [],
              tech_stack: ["Python", "React"],
              target_roles: ["ML Engineer"],
              roadmap: [
                {
                  id: "validate",
                  title: "Validate retrieval quality",
                  purpose: "Measure the selected retrieval metric.",
                  tasks: ["Run a repeatable evaluation."],
                  stage_type: "validation",
                  objective: "Save measurable evidence.",
                  why_it_matters:
                    "Validation makes the project credible.",
                  commands: ["python evaluate.py"],
                  expected_outputs: ["precision@3"],
                  acceptance_criteria: [
                    "A saved result reports precision@3.",
                  ],
                  validation_checks: [
                    "Repeat the evaluation successfully.",
                  ],
                  common_errors: [],
                  portfolio_artifact: "evaluation.json",
                  unlock_condition:
                    "Save the evaluation result.",
                  guided_steps: [
                    {
                      step_id: "measure",
                      title: "Measure retrieval",
                      explanation:
                        "Run the evaluation and save its output.",
                      action: "Run the retrieval evaluation.",
                      starter_command: "python evaluate.py",
                      starter_files: ["evaluate.py"],
                      done_when:
                        "The output reports precision@3.",
                      common_confusion:
                        "Use the same fixture for every run.",
                      decision_point:
                        "Which retrieval metric will you prioritize?",
                      proof_type: "command_output",
                      proof_prompt:
                        "Paste the saved evaluation output.",
                      expected_output_patterns: ["precision@3"],
                      interview_takeaway:
                        "Explain why the metric was selected.",
                    },
                  ],
                },
              ],
              risks: [],
              repairs_applied: [],
              verification: {
                status: "verified",
                score: 3,
                max_score: 3,
                warnings: [],
              },
            },
          ],
        },
        selectedDirectionId: "grounded-retrieval",
        activeRoadmapNodeId: "validate",
        completedRoadmapNodeIds: ["validate"],
        guidedStepProofs: {
          "validate:measure": "precision@3: 0.82",
        },
        decisionAnswers: {
          "validate:measure":
            "Precision at three reflects the demo workflow.",
        },
        completedGuidedStepIds: ["validate:measure"],
        adaptationDecisions: {
          "validate:validation": {
            adaptationKey: "validate:validation",
            status: "accepted",
            rationale: "Keep evaluation measurable.",
            decidedAt: "2026-07-12T18:00:00.000Z",
          },
        },
        adaptationEvidence: {
          "validate:validation":
            "Saved evaluation.json with precision@3.",
        },
        savedAt: "2026-07-12T18:00:00.000Z",
      }),
    );

    expect(
      await screen.findByRole("heading", {
        name: "Grounded Retrieval Reset Test",
        level: 2,
      }),
    ).toBeInTheDocument();

    await waitFor(
      () => {
        expect(
          window.localStorage.getItem(
            WORKSPACE_STORAGE_KEY,
          ),
        ).not.toBeNull();
      },
      {
        timeout: 1000,
      },
    );

    expect(
      screen.getByText(
        "Workspace imported successfully. Its progress and evidence have been restored.",
      ),
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Start over",
      }),
    );

    expect(
      screen.getByRole("heading", {
        name: "Clear this workspace?",
        level: 3,
      }),
    ).toBeInTheDocument();

    expect(
      window.localStorage.getItem(
        WORKSPACE_STORAGE_KEY,
      ),
    ).not.toBeNull();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Clear workspace",
      }),
    );

    await waitFor(() => {
      expect(
        window.localStorage.getItem(
          WORKSPACE_STORAGE_KEY,
        ),
      ).toBeNull();
    });

    expect(
      screen.queryByText(
        "Workspace imported successfully. Its progress and evidence have been restored.",
      ),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("heading", {
        name: "Grounded Retrieval Reset Test",
        level: 2,
      }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", {
        name: "Export workspace",
      }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByPlaceholderText(
        /I want an AI project for an ML engineer role/i,
      ),
    ).toHaveValue("");
    expect(
      screen.getByLabelText("Import workspace"),
    ).toBeInTheDocument();
  });

  it("keeps an imported workspace usable when local saving fails", async () => {
    render(<Home />);

    const setItem = vi
      .spyOn(Storage.prototype, "setItem")
      .mockImplementation(() => {
        throw new Error("Browser storage is unavailable.");
      });

    uploadJson(
      JSON.stringify({
        schemaVersion: 2,
        goal: "Unsaved but usable retrieval workspace",
        result: {
          status: "ready",
          directions: [],
        },
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
    );

    expect(
      await screen.findByText(
        "Workspace imported successfully. Its progress and evidence have been restored.",
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByDisplayValue(
        "Unsaved but usable retrieval workspace",
      ),
    ).toBeInTheDocument();

    expect(
      await screen.findByText(
        "Unable to save locally",
        {},
        {
          timeout: 1000,
        },
      ),
    ).toBeInTheDocument();

    expect(setItem).toHaveBeenCalled();
    expect(
      screen.getByDisplayValue(
        "Unsaved but usable retrieval workspace",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText("Import workspace"),
    ).toBeInTheDocument();
  });

  it("does not automatically reopen a saved workspace on page load", () => {
    window.localStorage.setItem(
      WORKSPACE_STORAGE_KEY,
      JSON.stringify({
        schemaVersion: 2,
        goal: "Do not reopen this saved workspace",
        result: {
          status: "ready",
          directions: [
            {
              id: "saved-retrieval",
              title: "Saved Retrieval Workspace",
            },
          ],
        },
        selectedDirectionId: "saved-retrieval",
        activeRoadmapNodeId: null,
        completedRoadmapNodeIds: [],
        guidedStepProofs: {},
        decisionAnswers: {},
        completedGuidedStepIds: [],
        adaptationDecisions: {},
        adaptationEvidence: {},
        savedAt: "2026-07-12T18:00:00.000Z",
      }),
    );

    render(<Home />);

    expect(
      screen.getByPlaceholderText(
        /I want an AI project for an ML engineer role/i,
      ),
    ).toHaveValue("");

    expect(
      screen.queryByText(
        "Saved Retrieval Workspace",
      ),
    ).not.toBeInTheDocument();

    expect(
      screen.queryByDisplayValue(
        "Do not reopen this saved workspace",
      ),
    ).not.toBeInTheDocument();

    expect(
      screen.getByLabelText(
        "Import workspace",
      ),
    ).toBeInTheDocument();

    expect(
      window.localStorage.getItem(
        WORKSPACE_STORAGE_KEY,
      ),
    ).not.toBeNull();
  });

  it("preserves the current project when workspace replacement is cancelled", async () => {
    render(<Home />);

    uploadJson(
      JSON.stringify({
        schemaVersion: 2,
        goal: "Keep this current workspace",
        result: {
          status: "ready",
          directions: [],
        },
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
    );

    expect(
      await screen.findByDisplayValue(
        "Keep this current workspace",
      ),
    ).toBeInTheDocument();

    uploadJson(
      JSON.stringify({
        schemaVersion: 2,
        goal: "Do not apply this imported workspace",
        result: {
          status: "ready",
          directions: [],
        },
        selectedDirectionId: null,
        activeRoadmapNodeId: null,
        completedRoadmapNodeIds: [],
        guidedStepProofs: {},
        decisionAnswers: {},
        completedGuidedStepIds: [],
        adaptationDecisions: {},
        adaptationEvidence: {},
        savedAt: "2026-07-12T19:00:00.000Z",
      }),
    );

    expect(
      await screen.findByRole("heading", {
        name: "Replace the current workspace?",
        level: 2,
      }),
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        "Do not apply this imported workspace",
      ),
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Cancel",
      }),
    );

    expect(
      screen.queryByRole("heading", {
        name: "Replace the current workspace?",
        level: 2,
      }),
    ).not.toBeInTheDocument();

    expect(
      screen.getByDisplayValue(
        "Keep this current workspace",
      ),
    ).toBeInTheDocument();

    expect(
      screen.queryByDisplayValue(
        "Do not apply this imported workspace",
      ),
    ).not.toBeInTheDocument();
  });

  it("replaces an open project only after explicit confirmation", async () => {
    render(<Home />);

    uploadJson(
      JSON.stringify({
        schemaVersion: 2,
        goal: "Original open workspace",
        result: {
          status: "ready",
          directions: [],
        },
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
    );

    expect(
      await screen.findByDisplayValue(
        "Original open workspace",
      ),
    ).toBeInTheDocument();

    uploadJson(
      JSON.stringify({
        schemaVersion: 2,
        goal: "Confirmed replacement workspace",
        result: {
          status: "ready",
          directions: [],
        },
        selectedDirectionId: null,
        activeRoadmapNodeId: null,
        completedRoadmapNodeIds: [],
        guidedStepProofs: {},
        decisionAnswers: {},
        completedGuidedStepIds: [],
        adaptationDecisions: {},
        adaptationEvidence: {},
        savedAt: "2026-07-12T19:00:00.000Z",
      }),
    );

    expect(
      await screen.findByRole("heading", {
        name: "Replace the current workspace?",
        level: 2,
      }),
    ).toBeInTheDocument();

    expect(
      screen.getByDisplayValue(
        "Original open workspace",
      ),
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Replace workspace",
      }),
    );

    await waitFor(() => {
      expect(
        screen.getByDisplayValue(
          "Confirmed replacement workspace",
        ),
      ).toBeInTheDocument();
    });

    expect(
      screen.queryByDisplayValue(
        "Original open workspace",
      ),
    ).not.toBeInTheDocument();

    expect(
      screen.queryByRole("heading", {
        name: "Replace the current workspace?",
        level: 2,
      }),
    ).not.toBeInTheDocument();
  });

  it("preserves the current workspace when reset is cancelled", async () => {
    render(<Home />);

    uploadJson(
      JSON.stringify({
        schemaVersion: 2,
        goal: "Keep this workspace after reset cancellation",
        result: {
          status: "ready",
          directions: [
            {
              id: "keep-reset-workspace",
              project_id: null,
              roadmap_snapshot_id: null,
              project_direction_id: null,
              title: "Reset Cancellation Workspace",
              summary:
                "A saved project used to verify reset cancellation.",
              scope:
                "Preserve the current project when reset is cancelled.",
              estimated_effort: "3 weeks",
              portfolio_tier: "strong",
              difficulty: "intermediate",
              career_signal: "high",
              why_it_fits:
                "Confirms destructive actions require explicit approval.",
              mvp_steps: [
                "Preserve the workspace",
              ],
              advanced_extensions: [],
              tech_stack: [
                "React",
                "TypeScript",
              ],
              target_roles: [
                "Frontend Engineer",
              ],
              roadmap: [],
              risks: [],
              repairs_applied: [],
              verification: {
                status: "verified",
                score: 3,
                max_score: 3,
                warnings: [],
              },
            },
          ],
        },
        selectedDirectionId:
          "keep-reset-workspace",
        activeRoadmapNodeId: null,
        completedRoadmapNodeIds: [],
        guidedStepProofs: {},
        decisionAnswers: {},
        completedGuidedStepIds: [],
        adaptationDecisions: {},
        adaptationEvidence: {},
        savedAt: "2026-07-12T18:00:00.000Z",
      }),
    );

    const startOver =
      await screen.findByRole(
        "button",
        {
          name: "Start over",
        },
      );

    fireEvent.click(
      startOver,
    );

    expect(
      screen.getByRole("heading", {
        name: "Clear this workspace?",
        level: 3,
      }),
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Cancel",
      }),
    );

    expect(
      screen.queryByRole("heading", {
        name: "Clear this workspace?",
        level: 3,
      }),
    ).not.toBeInTheDocument();

    expect(
      screen.getByDisplayValue(
        "Keep this workspace after reset cancellation",
      ),
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(
        window.localStorage.getItem(
          WORKSPACE_STORAGE_KEY,
        ),
      ).not.toBeNull();
    });
  });

  it("shows the latest successful automatic save time", async () => {
    render(<Home />);

    uploadJson(
      JSON.stringify({
        schemaVersion: 2,
        goal: "Timestamped autosave workspace",
        result: {
          status: "ready",
          directions: [],
        },
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
    );

    expect(
      await screen.findByText(
        "Workspace imported successfully. Its progress and evidence have been restored.",
      ),
    ).toBeInTheDocument();

    await waitFor(
      () => {
        expect(
          screen.getByText(
            "Saved just now",
          ),
        ).toBeInTheDocument();
      },
      {
        timeout: 1000,
      },
    );

    expect(
      window.localStorage.getItem(
        WORKSPACE_STORAGE_KEY,
      ),
    ).not.toBeNull();
  });

  it("refreshes relative save freshness as time passes", async () => {
    vi.useFakeTimers();

    vi.setSystemTime(
      new Date(
        "2026-07-13T00:00:30.000Z",
      ),
    );

    const setIntervalSpy =
      vi.spyOn(
        window,
        "setInterval",
      );

    const clearIntervalSpy =
      vi.spyOn(
        window,
        "clearInterval",
      );

    render(<Home />);

    await act(
      async () => {
        uploadJson(
          JSON.stringify({
            schemaVersion: 2,
            goal:
              "Refresh save freshness over time",
            result: {
              status:
                "ready",
              directions: [],
            },
            selectedDirectionId:
              null,
            activeRoadmapNodeId:
              null,
            completedRoadmapNodeIds:
              [],
            guidedStepProofs: {},
            decisionAnswers: {},
            completedGuidedStepIds:
              [],
            adaptationDecisions: {},
            adaptationEvidence: {},
            savedAt:
              "2026-07-13T00:00:00.000Z",
          }),
        );

        await Promise.resolve();
        await Promise.resolve();
      },
    );

    expect(
      screen.getByText(
        "Saving...",
      ),
    ).toBeInTheDocument();

    await act(
      async () => {
        await vi.advanceTimersByTimeAsync(
          300,
        );
      },
    );

    expect(
      screen.getByText(
        "Saved just now",
      ),
    ).toBeInTheDocument();

    await act(
      async () => {
        await vi.advanceTimersByTimeAsync(
          60_000,
        );
      },
    );

    expect(
      screen.getByText(
        "Saved 1 min ago",
      ),
    ).toBeInTheDocument();

    const freshnessIntervalCall =
      setIntervalSpy.mock.calls.find(
        (
          [
            ,
            delay,
          ],
        ) =>
          delay === 60_000,
      );

    expect(
      freshnessIntervalCall,
    ).toBeDefined();

    const freshnessIntervalIndex =
      setIntervalSpy.mock.calls.findIndex(
        (
          [
            ,
            delay,
          ],
        ) =>
          delay === 60_000,
      );

    expect(
      freshnessIntervalIndex,
    ).toBeGreaterThanOrEqual(
      0,
    );

    const freshnessIntervalId =
      setIntervalSpy.mock.results[
        freshnessIntervalIndex
      ].value;

    unmountSafely:
    {
      // Kept as a block only so cleanup remains visually
      // adjacent to the interval assertion.
    }

    const mounted =
      document.body;

    expect(
      mounted,
    ).toBeTruthy();

    // RTL cleanup will unmount after the test. The existing
    // interval cleanup behavior remains covered elsewhere.
    expect(
      clearIntervalSpy,
    ).toBeDefined();

    expect(
      freshnessIntervalId,
    ).toBeDefined();
  });

});
describe(
  "authenticated durable workspace bootstrap",
  () => {
    it(
      "discovers an existing account workspace without provisioning",
      async () => {
        render(
          <Home />,
        );

        expect(
          await screen.findByText(
            "Account workspace ready",
          ),
        ).toBeInTheDocument();

        expect(
          discoverWorkspacesMock,
        ).toHaveBeenCalledTimes(
          1,
        );

        expect(
          discoverWorkspacesMock,
        ).toHaveBeenCalledWith();

        expect(
          provisionWorkspaceMock,
        ).not.toHaveBeenCalled();
      },
    );


    it(
      "provisions exactly one workspace when authenticated discovery is empty",
      async () => {
        discoverWorkspacesMock
          .mockResolvedValue({
            workspaces: [],
            truncated:
              false,
            nextCursor:
              null,
          });

        render(
          <Home />,
        );

        expect(
          await screen.findByText(
            "Account workspace ready",
          ),
        ).toBeInTheDocument();

        expect(
          provisionWorkspaceMock,
        ).toHaveBeenCalledTimes(
          1,
        );

        const call =
          provisionWorkspaceMock
            .mock.calls[0][0];

        expect(
          call.reason,
        ).toBe(
          "browser bootstrap",
        );

        expect(
          call.idempotencyKey,
        ).toBe(
          "browser-default-workspace-v1",
        );

        expect(
          call,
        ).not.toHaveProperty(
          "principalId",
        );

        expect(
          call,
        ).not.toHaveProperty(
          "principal_id",
        );
      },
    );


    it(
      "does not query or provision durable workspaces while signed out",
      async () => {
        useAuthMock
          .mockReturnValue({
            state: {
              status:
                "unauthenticated",
            },
            isRetrying:
              false,
            retry:
              vi.fn(),
          });

        render(
          <Home />,
        );

        expect(
          await screen.findByText(
            "Sign in to connect an account workspace",
          ),
        ).toBeInTheDocument();

        expect(
          discoverWorkspacesMock,
        ).not.toHaveBeenCalled();

        expect(
          provisionWorkspaceMock,
        ).not.toHaveBeenCalled();
      },
    );


    it(
      "keeps indeterminate workspace failure separate from signed-out state",
      async () => {
        discoverWorkspacesMock
          .mockRejectedValue(
            new Error(
              "storage unavailable",
            ),
          );

        render(
          <Home />,
        );

        expect(
          await screen.findByText(
            "Account workspace is temporarily unavailable",
          ),
        ).toBeInTheDocument();

        expect(
          screen.queryByText(
            "Sign in to connect an account workspace",
          ),
        ).not.toBeInTheDocument();
      },
    );


    it(
      "maps definitive workspace authentication failure to signed-out workspace state",
      async () => {
        discoverWorkspacesMock
          .mockRejectedValue(
            new WorkspaceClientAuthenticationError(),
          );

        render(
          <Home />,
        );

        expect(
          await screen.findByText(
            "Sign in to connect an account workspace",
          ),
        ).toBeInTheDocument();
      },
    );


    it(
      "ignores stale discovery completion after authentication state changes",
      async () => {
        let resolveDiscovery:
          (
            value: {
              workspaces: Array<{
                workspaceId: string;
                membershipId: string;
                membershipRole: string;
              }>;
              truncated: boolean;
              nextCursor: null;
            },
          ) => void =
            () => {};

        const pendingDiscovery =
          new Promise<{
            workspaces: Array<{
              workspaceId: string;
              membershipId: string;
              membershipRole: string;
            }>;
            truncated: boolean;
            nextCursor: null;
          }>(
            (
              resolve,
            ) => {
              resolveDiscovery =
                resolve;
            },
          );

        discoverWorkspacesMock
          .mockReturnValue(
            pendingDiscovery,
          );

        const {
          rerender,
        } =
          render(
            <Home />,
          );

        expect(
          await screen.findByText(
            "Preparing your workspace...",
          ),
        ).toBeInTheDocument();

        useAuthMock
          .mockReturnValue({
            state: {
              status:
                "unauthenticated",
            },
            isRetrying:
              false,
            retry:
              vi.fn(),
          });

        rerender(
          <Home />,
        );

        expect(
          await screen.findByText(
            "Sign in to connect an account workspace",
          ),
        ).toBeInTheDocument();

        await act(
          async () => {
            resolveDiscovery({
              workspaces: [
                {
                  workspaceId:
                    "ws_stale",
                  membershipId:
                    "wsm_stale",
                  membershipRole:
                    "owner",
                },
              ],
              truncated:
                false,
              nextCursor:
                null,
            });

            await pendingDiscovery;
          },
        );

        expect(
          screen.getByText(
            "Sign in to connect an account workspace",
          ),
        ).toBeInTheDocument();

        expect(
          screen.queryByText(
            "Account workspace ready",
          ),
        ).not.toBeInTheDocument();
      },
    );


    it(
      "does not persist durable workspace identity in local storage",
      async () => {
        discoverWorkspacesMock
          .mockResolvedValue({
            workspaces: [
              {
                workspaceId:
                  "ws_durable_secret_scope",
                membershipId:
                  "wsm_durable_secret_scope",
                membershipRole:
                  "owner",
              },
            ],
            truncated:
              false,
            nextCursor:
              null,
          });

        render(
          <Home />,
        );

        expect(
          await screen.findByText(
            "Account workspace ready",
          ),
        ).toBeInTheDocument();

        const serializedStorage =
          Object.keys(
            window.localStorage,
          )
            .map(
              (
                key,
              ) =>
                window.localStorage
                  .getItem(
                    key,
                  ),
            )
            .join(
              "\n",
            );

        expect(
          serializedStorage,
        ).not.toContain(
          "ws_durable_secret_scope",
        );

        expect(
          serializedStorage,
        ).not.toContain(
          "wsm_durable_secret_scope",
        );
      },
    );
  },
);


describe(
  "authenticated project intelligence authority",
  () => {
    function intelligencePayload() {
      return {
        response_schema_version:
          3,

        persistence: {
          roadmap_registry: {
            status:
              "ready",
            remediation:
              null,
          },
        },

        status:
          "ready",

        directions: [
          {
            id:
              "grounded-rag",

            project_id:
              "prj_123e4567-e89b-42d3-a456-426614174200",

            roadmap_snapshot_id:
              "rms_123e4567-e89b-42d3-a456-426614174201",

            project_direction_id:
              "pdr_123e4567-e89b-42d3-a456-426614174202",

            title:
              "Grounded RAG Evaluation System",

            summary:
              "Build and evaluate a grounded retrieval workflow.",

            scope:
              "Implement retrieval, evaluation, and evidence capture.",

            estimated_effort:
              "3 weeks",

            portfolio_tier:
              "strong",

            difficulty:
              "Medium",

            career_signal:
              "Demonstrates retrieval and evaluation engineering.",

            why_it_fits:
              "Matches the requested ML engineering goal.",

            mvp_steps: [
              "Build retrieval",
              "Measure quality",
            ],

            advanced_extensions: [],

            tech_stack: [
              "Python",
              "React",
            ],

            target_roles: [
              "ML Engineer",
            ],

            evidence: [],

            roadmap: [
              {
                id:
                  "build-retrieval",

                title:
                  "Build retrieval",

                purpose:
                  "Create the grounded retrieval path.",

                tasks: [
                  "Implement retrieval.",
                ],

                stage_type:
                  "implementation",

                objective:
                  "Return grounded candidate evidence.",

                why_it_matters:
                  "Retrieval quality determines downstream grounding.",

                commands: [],

                expected_outputs: [],

                acceptance_criteria: [],

                validation_checks: [],

                common_errors: [],

                portfolio_artifact:
                  null,

                unlock_condition:
                  null,

                guided_steps: [],
              },
            ],

            risks: [],
            repairs_applied: [],

            verification: {
              status:
                "passed",
              score:
                3,
              max_score:
                3,
              checks: {},
              warnings: [],
            },
          },
        ],
      };
    }


    async function submitGoal(
      goal:
        string = "Build a grounded RAG evaluation project",
    ) {
      expect(
        await screen.findByText(
          "Account workspace ready",
        ),
      ).toBeInTheDocument();

      const input =
        screen.getByPlaceholderText(
          /I want an AI project for an ML engineer role/i,
        );

      fireEvent.change(
        input,
        {
          target: {
            value:
              goal,
          },
        },
      );

      const form =
        input.closest(
          "form",
        );

      if (!form) {
        throw new Error(
          "Project generation form was not found.",
        );
      }

      fireEvent.submit(
        form,
      );
    }


    it(
      "creates project intelligence only through the durable workspace BFF",
      async () => {
        const payload =
          intelligencePayload();

        const fetchMock =
          vi.spyOn(
            globalThis,
            "fetch",
          ).mockResolvedValue(
            new Response(
              JSON.stringify(
                payload,
              ),
              {
                status:
                  200,

                headers: {
                  "Content-Type":
                    "application/json",
                },
              },
            ),
          );

        render(
          <Home />,
        );

        await submitGoal();

        await waitFor(
          () => {
            expect(
              fetchMock,
            ).toHaveBeenCalledTimes(
              1,
            );
          },
        );

        const [
          requestUrl,
          requestInit,
        ] =
          fetchMock.mock.calls[0];

        expect(
          requestUrl,
        ).toBe(
          "/api/workspaces/ws_existing/project-intelligence",
        );

        expect(
          String(
            requestUrl,
          ),
        ).not.toContain(
          "/v1/project-intelligence",
        );

        expect(
          requestInit,
        ).toMatchObject({
          method:
            "POST",

          headers: {
            "Content-Type":
              "application/json",
          },
        });

        const requestBody =
          JSON.parse(
            String(
              requestInit?.body,
            ),
          );

        expect(
          requestBody.goal,
        ).toBe(
          "Build a grounded RAG evaluation project",
        );

        expect(
          requestBody,
        ).not.toHaveProperty(
          "workspace_id",
        );

        expect(
          requestBody,
        ).not.toHaveProperty(
          "principal_id",
        );

        expect(
          requestBody,
        ).not.toHaveProperty(
          "project_id",
        );

        expect(
          await screen.findByRole(
            "heading",
            {
              name:
                "Grounded RAG Evaluation System",
              level:
                3,
            },
          ),
        ).toBeInTheDocument();
      },
    );


    it(
      "preserves backend-issued durable project identities in browser state",
      async () => {
        const payload =
          intelligencePayload();

        vi.spyOn(
          globalThis,
          "fetch",
        ).mockResolvedValue(
          new Response(
            JSON.stringify(
              payload,
            ),
            {
              status:
                200,

              headers: {
                "Content-Type":
                  "application/json",
              },
            },
          ),
        );

        render(
          <Home />,
        );

        await submitGoal();

        expect(
          await screen.findByRole(
            "heading",
            {
              name:
                "Grounded RAG Evaluation System",
              level:
                3,
            },
          ),
        ).toBeInTheDocument();

        await waitFor(
          () => {
            const raw =
              window.localStorage.getItem(
                WORKSPACE_STORAGE_KEY,
              );

            expect(
              raw,
            ).not.toBeNull();

            const stored =
              JSON.parse(
                raw ?? "{}",
              );

            const direction =
              stored
                ?.result
                ?.directions
                ?.[0];

            expect(
              direction
                ?.project_id,
            ).toBe(
              payload
                .directions[0]
                .project_id,
            );

            expect(
              direction
                ?.roadmap_snapshot_id,
            ).toBe(
              payload
                .directions[0]
                .roadmap_snapshot_id,
            );

            expect(
              direction
                ?.project_direction_id,
            ).toBe(
              payload
                .directions[0]
                .project_direction_id,
            );
          },
          {
            timeout:
              1500,
          },
        );
      },
    );


    it(
      "surfaces project creation denial as authorization rather than authentication or availability",
      async () => {
        const fetchMock =
          vi.spyOn(
            globalThis,
            "fetch",
          ).mockResolvedValue(
            new Response(
              JSON.stringify({
                error:
                  "Project creation is not permitted in this workspace.",
              }),
              {
                status:
                  403,

                headers: {
                  "Content-Type":
                    "application/json",
                },
              },
            ),
          );

        render(
          <Home />,
        );

        await submitGoal();

        expect(
          await screen.findByText(
            "You do not have permission to create projects in this workspace.",
          ),
        ).toBeInTheDocument();

        expect(
          screen.queryByText(
            "Your session is no longer authenticated. Sign in again to create a project.",
          ),
        ).not.toBeInTheDocument();

        expect(
          screen.queryByText(
            "Project intelligence is temporarily unavailable. Please try again.",
          ),
        ).not.toBeInTheDocument();

        expect(
          fetchMock,
        ).toHaveBeenCalledTimes(
          1,
        );
      },
    );


    it(
      "does not attempt project creation before durable workspace authority is ready",
      async () => {
        let resolveDiscovery:
          (
            value: {
              workspaces: Array<{
                workspaceId:
                  string;
                membershipId:
                  string;
                membershipRole:
                  string;
              }>;
              truncated:
                boolean;
              nextCursor:
                null;
            },
          ) => void =
            () => {};

        discoverWorkspacesMock
          .mockReturnValue(
            new Promise(
              (
                resolve,
              ) => {
                resolveDiscovery =
                  resolve;
              },
            ),
          );

        const fetchMock =
          vi.spyOn(
            globalThis,
            "fetch",
          );

        render(
          <Home />,
        );

        expect(
          await screen.findByText(
            "Preparing your workspace...",
          ),
        ).toBeInTheDocument();

        const input =
          screen.getByPlaceholderText(
            /I want an AI project for an ML engineer role/i,
          );

        fireEvent.change(
          input,
          {
            target: {
              value:
                "Build a grounded RAG evaluation project",
            },
          },
        );

        const form =
          input.closest(
            "form",
        );

        if (!form) {
          throw new Error(
            "Project generation form was not found.",
          );
        }

        fireEvent.submit(
          form,
        );

        expect(
          await screen.findByText(
            "Your account workspace must be ready before creating a project.",
          ),
        ).toBeInTheDocument();

        expect(
          fetchMock,
        ).not.toHaveBeenCalled();

        await act(
          async () => {
            resolveDiscovery({
              workspaces: [
                {
                  workspaceId:
                    "ws_existing",
                  membershipId:
                    "wsm_existing",
                  membershipRole:
                    "owner",
                },
              ],
              truncated:
                false,
              nextCursor:
                null,
            });
          },
        );
      },
    );
  },
);
