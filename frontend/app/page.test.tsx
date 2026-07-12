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
});
