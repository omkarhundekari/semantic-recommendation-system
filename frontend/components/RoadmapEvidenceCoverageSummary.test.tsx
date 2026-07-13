// @vitest-environment jsdom

import {
  render,
  screen,
} from "@testing-library/react";
import {
  describe,
  expect,
  it,
} from "vitest";

import {
  buildRoadmapEvidenceCoverage,
} from "@/lib/roadmapEvidenceCoverage";

import RoadmapEvidenceCoverageSummary from "./RoadmapEvidenceCoverageSummary";

const STAGES = [
  {
    id: "define",
    title: "Define the system",
  },
  {
    id: "build",
    title: "Build the MVP",
  },
];

describe("roadmap evidence coverage summary", () => {
  it("shows uncovered roadmap stages", () => {
    const coverage =
      buildRoadmapEvidenceCoverage({
        roadmapStages: STAGES,
        attributions: [
          {
            evidence_key: "commit:1",
            roadmap_node_id: "build",
            source: "manual",
            confidence: 1,
            rationale: "",
            status: "accepted",
            decided_at:
              "2026-07-13T12:00:00+00:00",
          },
        ],
      });

    render(
      <RoadmapEvidenceCoverageSummary
        coverage={coverage}
      />,
    );

    expect(
      screen.getByText(
        "1/2 roadmap stages covered",
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        "1 stage still need linked execution proof.",
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByText("50%"),
    ).toBeInTheDocument();
  });

  it("shows complete evidence coverage", () => {
    const coverage =
      buildRoadmapEvidenceCoverage({
        roadmapStages: STAGES,
        attributions: [
          {
            evidence_key: "commit:1",
            roadmap_node_id: "define",
            source: "manual",
            confidence: 1,
            rationale: "",
            status: "accepted",
            decided_at:
              "2026-07-13T12:00:00+00:00",
          },
          {
            evidence_key: "commit:2",
            roadmap_node_id: "build",
            source: "manual",
            confidence: 1,
            rationale: "",
            status: "accepted",
            decided_at:
              "2026-07-13T12:00:00+00:00",
          },
        ],
      });

    render(
      <RoadmapEvidenceCoverageSummary
        coverage={coverage}
      />,
    );

    expect(
      screen.getByText(
        "Every roadmap stage has accepted repository evidence.",
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByText("100%"),
    ).toBeInTheDocument();
  });

  it("renders nothing for an empty roadmap", () => {
    const coverage =
      buildRoadmapEvidenceCoverage({
        roadmapStages: [],
        attributions: [],
      });

    const { container } = render(
      <RoadmapEvidenceCoverageSummary
        coverage={coverage}
      />,
    );

    expect(container).toBeEmptyDOMElement();
  });
});
