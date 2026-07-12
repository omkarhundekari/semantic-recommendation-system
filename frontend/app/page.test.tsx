// @vitest-environment jsdom

import {
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { describe, expect, it } from "vitest";

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
});
