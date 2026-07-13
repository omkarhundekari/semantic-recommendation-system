// @vitest-environment jsdom

import {
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import {
  afterEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";

import {
  WORKSPACE_STORAGE_KEY,
} from "@/lib/workspacePersistence";

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

afterEach(() => {
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

  it("restores a saved workspace automatically on page load", async () => {
    window.localStorage.setItem(
      WORKSPACE_STORAGE_KEY,
      JSON.stringify({
        schemaVersion: 2,
        goal: "Resume my saved retrieval workspace",
        result: {
          status: "ready",
          directions: [
            {
              id: "saved-retrieval",
              title: "Saved Retrieval Workspace",
              summary:
                "A previously saved project restored at startup.",
              scope:
                "Build and validate one grounded retrieval workflow.",
              estimated_effort: "3 weeks",
              portfolio_tier: "strong",
              difficulty: "intermediate",
              career_signal: "high",
              why_it_fits:
                "Demonstrates retrieval and evaluation skills.",
              mvp_steps: ["Build retrieval"],
              advanced_extensions: [],
              tech_stack: ["Python", "React"],
              target_roles: ["ML Engineer"],
              roadmap: [
                {
                  id: "validate",
                  title: "Validate saved retrieval quality",
                  purpose:
                    "Measure the selected retrieval metric.",
                  tasks: ["Run a repeatable evaluation."],
                  stage_type: "validation",
                  objective: "Save measurable evidence.",
                  why_it_matters:
                    "Validation makes the result credible.",
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
                      title: "Measure saved retrieval",
                      explanation:
                        "Run evaluation and preserve its output.",
                      action:
                        "Run the saved retrieval evaluation.",
                      starter_command: "python evaluate.py",
                      starter_files: ["evaluate.py"],
                      done_when:
                        "The output reports precision@3.",
                      common_confusion:
                        "Use the same fixture for every run.",
                      decision_point:
                        "Which retrieval metric should be prioritized?",
                      proof_type: "command_output",
                      proof_prompt:
                        "Paste the saved evaluation output.",
                      expected_output_patterns: ["precision@3"],
                      interview_takeaway:
                        "Explain why this metric was selected.",
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
        selectedDirectionId: "saved-retrieval",
        activeRoadmapNodeId: "validate",
        completedRoadmapNodeIds: [],
        guidedStepProofs: {
          "validate:measure": "precision@3: 0.81",
        },
        decisionAnswers: {
          "validate:measure":
            "Precision at three reflects the intended demo.",
        },
        completedGuidedStepIds: ["validate:measure"],
        adaptationDecisions: {},
        adaptationEvidence: {},
        savedAt: "2026-07-12T18:00:00.000Z",
      }),
    );

    render(<Home />);

    expect(
      screen.getByDisplayValue(
        "Resume my saved retrieval workspace",
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("heading", {
        name: "Saved Retrieval Workspace",
        level: 2,
      }),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("heading", {
        name: "Validate saved retrieval quality",
        level: 3,
      }),
    ).toBeInTheDocument();

    const restoredSaveTime = new Intl.DateTimeFormat(
      undefined,
      {
        hour: "numeric",
        minute: "2-digit",
      },
    ).format(
      new Date("2026-07-12T18:00:00.000Z"),
    );

    const restoredStatus = screen.getByText(
      `Saved at ${restoredSaveTime}`,
    );

    expect(restoredStatus).toBeInTheDocument();
    expect(restoredStatus).toHaveAttribute(
      "title",
      expect.stringMatching(/^Last saved /),
    );

    expect(
      screen.queryByText(
        "Workspace imported successfully. Its progress and evidence have been restored.",
      ),
    ).not.toBeInTheDocument();

    await waitFor(() => {
      const storedWorkspace = window.localStorage.getItem(
        WORKSPACE_STORAGE_KEY,
      );

      expect(storedWorkspace).not.toBeNull();
      expect(
        JSON.parse(storedWorkspace ?? "{}").selectedDirectionId,
      ).toBe("saved-retrieval");
    });
  });

  it("preserves the current project when workspace replacement is cancelled", async () => {
    window.localStorage.setItem(
      WORKSPACE_STORAGE_KEY,
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

    render(<Home />);

    expect(
      screen.getByDisplayValue("Keep this current workspace"),
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
      screen.getByText("Do not apply this imported workspace"),
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
      screen.getByDisplayValue("Keep this current workspace"),
    ).toBeInTheDocument();

    expect(
      screen.queryByDisplayValue(
        "Do not apply this imported workspace",
      ),
    ).not.toBeInTheDocument();

    expect(
      screen.queryByText(
        "Workspace imported successfully. Its progress and evidence have been restored.",
      ),
    ).not.toBeInTheDocument();
  });

  it("replaces an open project only after explicit confirmation", async () => {
    window.localStorage.setItem(
      WORKSPACE_STORAGE_KEY,
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

    render(<Home />);

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
      screen.getByDisplayValue("Original open workspace"),
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
      screen.queryByDisplayValue("Original open workspace"),
    ).not.toBeInTheDocument();

    expect(
      screen.queryByRole("heading", {
        name: "Replace the current workspace?",
        level: 2,
      }),
    ).not.toBeInTheDocument();

    expect(
      screen.getByText(
        "Workspace imported successfully. Its progress and evidence have been restored.",
      ),
    ).toBeInTheDocument();
  });

  it("preserves the current workspace when reset is cancelled", async () => {
    window.localStorage.setItem(
      WORKSPACE_STORAGE_KEY,
      JSON.stringify({
        schemaVersion: 2,
        goal: "Keep this workspace after reset cancellation",
        result: {
          status: "ready",
          directions: [
            {
              id: "keep-reset-workspace",
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
              mvp_steps: ["Preserve the workspace"],
              advanced_extensions: [],
              tech_stack: ["React", "TypeScript"],
              target_roles: ["Frontend Engineer"],
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
        selectedDirectionId: "keep-reset-workspace",
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

    expect(
      window.localStorage.getItem(
        WORKSPACE_STORAGE_KEY,
      ),
    ).not.toBeNull();
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
});
