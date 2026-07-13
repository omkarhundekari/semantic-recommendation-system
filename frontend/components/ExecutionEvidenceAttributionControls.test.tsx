// @vitest-environment jsdom

import {
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import {
  afterEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";

import type {
  EvidenceAttribution,
} from "@/lib/executionEvidenceAttributionApi";
import type {
  ExecutionEvidenceItem,
} from "@/lib/executionEvidenceApi";

import ExecutionEvidenceAttributionControls from "./ExecutionEvidenceAttributionControls";

const EVIDENCE: ExecutionEvidenceItem = {
  provider: "github",
  repository_full_name: "owner/repository",
  evidence_type: "commit",
  external_id: "abc123",
  title: "Implement repository attribution",
  description: "",
  url:
    "https://github.com/owner/repository/commit/abc123",
  occurred_at:
    "2026-07-13T12:00:00+00:00",
  metadata: {},
  first_seen_at:
    "2026-07-13T12:00:00+00:00",
  last_seen_at:
    "2026-07-13T12:00:00+00:00",
};

const ATTRIBUTION: EvidenceAttribution = {
  evidence_key:
    "github:owner/repository:commit:abc123",
  roadmap_node_id: "build-mvp",
  source: "manual",
  confidence: 1,
  rationale: "",
  status: "accepted",
  decided_at:
    "2026-07-13T12:00:00+00:00",
};

const STAGES = [
  {
    id: "build-mvp",
    title: "Build the MVP",
  },
  {
    id: "validate-system",
    title: "Validate the system",
  },
];

afterEach(() => {
  vi.restoreAllMocks();
});

describe("execution evidence attribution controls", () => {
  it("explains that a roadmap is required", () => {
    render(
      <ExecutionEvidenceAttributionControls
        apiBaseUrl="http://127.0.0.1:8000"
        repositoryKey="github:owner/repository"
        revision={0}
        evidence={EVIDENCE}
        roadmapStages={[]}
        attributions={[]}
        onAttributionsChanged={vi.fn()}
      />,
    );

    expect(
      screen.getByText(
        /Generate and select a project direction/,
      ),
    ).toBeInTheDocument();
  });

  it("attaches evidence to the selected stage", async () => {
    const onAttributionsChanged = vi.fn();

    vi.spyOn(
      globalThis,
      "fetch",
    ).mockResolvedValue(
      new Response(
        JSON.stringify({
          created: true,
          attribution: ATTRIBUTION,
          stored: {
            schema_version: 2,
            revision: 1,
            saved_at:
              "2026-07-13T12:00:00+00:00",
            attributions: [ATTRIBUTION],
          },
        }),
        {
          status: 200,
          headers: {
            "Content-Type":
              "application/json",
          },
        },
      ),
    );

    render(
      <ExecutionEvidenceAttributionControls
        apiBaseUrl="http://127.0.0.1:8000"
        repositoryKey="github:owner/repository"
        revision={0}
        evidence={EVIDENCE}
        roadmapStages={STAGES}
        attributions={[]}
        onAttributionsChanged={
          onAttributionsChanged
        }
      />,
    );

    fireEvent.change(
      screen.getByLabelText(
        "Roadmap stage for Implement repository attribution",
      ),
      {
        target: {
          value: "build-mvp",
        },
      },
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: "Attach to stage",
      }),
    );

    expect(
      await screen.findByText("Attaching..."),
    ).toBeInTheDocument();

    await vi.waitFor(() => {
      expect(
        onAttributionsChanged,
      ).toHaveBeenCalledWith({
        attributions: [ATTRIBUTION],
        revision: 1,
      });
    });
  });

  it("shows existing attribution links", () => {
    render(
      <ExecutionEvidenceAttributionControls
        apiBaseUrl="http://127.0.0.1:8000"
        repositoryKey="github:owner/repository"
        revision={1}
        evidence={EVIDENCE}
        roadmapStages={STAGES}
        attributions={[ATTRIBUTION]}
        onAttributionsChanged={vi.fn()}
      />,
    );

    expect(
      screen.getByRole("button", {
        name:
          "Remove Implement repository attribution from Build the MVP",
      }),
    ).toBeInTheDocument();
  });

  it("detaches an existing attribution", async () => {
    const onAttributionsChanged = vi.fn();

    vi.spyOn(
      globalThis,
      "fetch",
    ).mockResolvedValue(
      new Response(
        JSON.stringify({
          removed: true,
        }),
        {
          status: 200,
          headers: {
            "Content-Type":
              "application/json",
          },
        },
      ),
    );

    render(
      <ExecutionEvidenceAttributionControls
        apiBaseUrl="http://127.0.0.1:8000"
        repositoryKey="github:owner/repository"
        revision={1}
        evidence={EVIDENCE}
        roadmapStages={STAGES}
        attributions={[ATTRIBUTION]}
        onAttributionsChanged={
          onAttributionsChanged
        }
      />,
    );

    fireEvent.click(
      screen.getByRole("button", {
        name:
          "Remove Implement repository attribution from Build the MVP",
      }),
    );

    await vi.waitFor(() => {
      expect(
        onAttributionsChanged,
      ).toHaveBeenCalledWith({
        attributions: [],
        revision: 2,
      });
    });
  });

  it("surfaces revision conflicts", async () => {
    vi.spyOn(
      globalThis,
      "fetch",
    ).mockResolvedValue(
      new Response(
        JSON.stringify({
          detail:
            "Repository evidence revision conflict.",
        }),
        {
          status: 409,
          headers: {
            "Content-Type":
              "application/json",
          },
        },
      ),
    );

    render(
      <ExecutionEvidenceAttributionControls
        apiBaseUrl="http://127.0.0.1:8000"
        repositoryKey="github:owner/repository"
        revision={0}
        evidence={EVIDENCE}
        roadmapStages={STAGES}
        attributions={[]}
        onAttributionsChanged={vi.fn()}
      />,
    );

    fireEvent.change(
      screen.getByLabelText(
        "Roadmap stage for Implement repository attribution",
      ),
      {
        target: {
          value: "build-mvp",
        },
      },
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: "Attach to stage",
      }),
    );

    expect(
      await screen.findByRole("alert"),
    ).toHaveTextContent(
      "Repository evidence revision conflict.",
    );
  });
});


describe("execution evidence attribution stage availability", () => {
  it("removes already-linked stages from the selector", () => {
    render(
      <ExecutionEvidenceAttributionControls
        apiBaseUrl="http://127.0.0.1:8000"
        repositoryKey="github:owner/repository"
        revision={1}
        evidence={EVIDENCE}
        roadmapStages={STAGES}
        attributions={[ATTRIBUTION]}
        onAttributionsChanged={vi.fn()}
      />,
    );

    const selector =
      screen.getByLabelText(
        "Roadmap stage for Implement repository attribution",
      );

    expect(selector).not.toHaveTextContent(
      "Build the MVP",
    );
    expect(selector).toHaveTextContent(
      "Validate the system",
    );
  });

  it("shows complete-link feedback when every stage is linked", () => {
    const validateAttribution: EvidenceAttribution =
      {
        ...ATTRIBUTION,
        roadmap_node_id:
          "validate-system",
      };

    render(
      <ExecutionEvidenceAttributionControls
        apiBaseUrl="http://127.0.0.1:8000"
        repositoryKey="github:owner/repository"
        revision={2}
        evidence={EVIDENCE}
        roadmapStages={STAGES}
        attributions={[
          ATTRIBUTION,
          validateAttribution,
        ]}
        onAttributionsChanged={vi.fn()}
      />,
    );

    expect(
      screen.getByText(
        "This evidence is linked to every roadmap stage.",
      ),
    ).toBeInTheDocument();

    expect(
      screen.queryByRole("button", {
        name: "Attach to stage",
      }),
    ).not.toBeInTheDocument();
  });
});
