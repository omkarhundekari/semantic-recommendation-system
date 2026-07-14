import {
  describe,
  expect,
  it,
  vi,
} from "vitest";

import {
  attachExecutionEvidence,
  detachExecutionEvidence,
  listExecutionEvidenceAttributions,
  type AttributionMutationResponse,
} from "./executionEvidenceAttributionApi";

const API_BASE_URL = "http://127.0.0.1:8000";
const PROJECT_DIRECTION_ID =
  "trusted-project-direction";
const REPOSITORY_KEY = "github:owner/repository";
const EVIDENCE_KEY =
  "github:owner/repository:commit:abc123";

function mutationResponse(): AttributionMutationResponse {
  const attribution = {
    attribution_id: "attribution-one",
    project_direction_id:
      PROJECT_DIRECTION_ID,
    evidence_key: EVIDENCE_KEY,
    roadmap_node_id: "build-mvp",
    source: "manual" as const,
    confidence: 1,
    rationale: "Completes the MVP stage.",
    status: "accepted" as const,
    decided_at:
      "2026-07-13T12:00:00+00:00",
  };

  return {
    created: true,
    attribution,
    stored: {
      schema_version: 2,
      revision: 1,
      saved_at:
        "2026-07-13T12:00:00+00:00",
      attributions: [attribution],
    },
  };
}

describe("execution evidence attribution API", () => {
  it("attaches evidence to a roadmap stage", async () => {
    const payload = mutationResponse();

    const fetcher = vi.fn<
      (
        input: RequestInfo | URL,
        options?: RequestInit,
      ) => Promise<Response>
    >();

    fetcher.mockResolvedValue(
      new Response(JSON.stringify(payload), {
        status: 200,
        headers: {
          "Content-Type": "application/json",
        },
      }),
    );

    const result = await attachExecutionEvidence(
      {
        apiBaseUrl: API_BASE_URL,
        projectDirectionId:
          PROJECT_DIRECTION_ID,
        repositoryKey: REPOSITORY_KEY,
        evidenceKey: EVIDENCE_KEY,
        roadmapNodeId: " build-mvp ",
        rationale: " Completes the MVP stage. ",
        expectedRevision: 0,
      },
      fetcher,
    );

    expect(result).toEqual(payload);

    const [, options] = fetcher.mock.calls[0];

    expect(options?.method).toBe("POST");
    expect(JSON.parse(String(options?.body))).toEqual({
      project_direction_id:
        PROJECT_DIRECTION_ID,
      repository_key: REPOSITORY_KEY,
      evidence_key: EVIDENCE_KEY,
      roadmap_node_id: "build-mvp",
      rationale: "Completes the MVP stage.",
      expected_revision: 0,
    });
  });

  it("requires trusted project identity before attaching", async () => {
    const fetcher = vi.fn();

    await expect(
      attachExecutionEvidence(
        {
          apiBaseUrl: API_BASE_URL,
          projectDirectionId: " ",
          repositoryKey: REPOSITORY_KEY,
          evidenceKey: EVIDENCE_KEY,
          roadmapNodeId: "build-mvp",
        },
        fetcher,
      ),
    ).rejects.toThrow(
      "Trusted project identity is required before attaching evidence.",
    );

    expect(fetcher).not.toHaveBeenCalled();
  });

  it("requires a roadmap stage before attaching", async () => {
    const fetcher = vi.fn();

    await expect(
      attachExecutionEvidence(
        {
          apiBaseUrl: API_BASE_URL,
          projectDirectionId:
            PROJECT_DIRECTION_ID,
          repositoryKey: REPOSITORY_KEY,
          evidenceKey: EVIDENCE_KEY,
          roadmapNodeId: " ",
        },
        fetcher,
      ),
    ).rejects.toThrow(
      "Choose a roadmap stage before attaching evidence.",
    );

    expect(fetcher).not.toHaveBeenCalled();
  });

  it("detaches an evidence attribution", async () => {
    const fetcher = vi.fn<
      (
        input: RequestInfo | URL,
        options?: RequestInit,
      ) => Promise<Response>
    >();

    fetcher.mockResolvedValue(
      new Response(
        JSON.stringify({
          removed: true,
        }),
        {
          status: 200,
          headers: {
            "Content-Type": "application/json",
          },
        },
      ),
    );

    const result = await detachExecutionEvidence(
      {
        apiBaseUrl: API_BASE_URL,
        projectDirectionId:
          PROJECT_DIRECTION_ID,
        repositoryKey: REPOSITORY_KEY,
        evidenceKey: EVIDENCE_KEY,
        roadmapNodeId: "build-mvp",
        expectedRevision: 1,
      },
      fetcher,
    );

    expect(result.removed).toBe(true);

    const [, options] = fetcher.mock.calls[0];

    expect(options?.method).toBe("DELETE");
    expect(JSON.parse(String(options?.body))).toEqual({
      project_direction_id:
        PROJECT_DIRECTION_ID,
      repository_key: REPOSITORY_KEY,
      evidence_key: EVIDENCE_KEY,
      roadmap_node_id: "build-mvp",
      expected_revision: 1,
    });
  });

  it("lists attributions for one roadmap stage", async () => {
    const attribution =
      mutationResponse().attribution;

    const fetcher = vi.fn<
      (
        input: RequestInfo | URL,
        options?: RequestInit,
      ) => Promise<Response>
    >();

    fetcher.mockResolvedValue(
      new Response(
        JSON.stringify([attribution]),
        {
          status: 200,
          headers: {
            "Content-Type": "application/json",
          },
        },
      ),
    );

    const result =
      await listExecutionEvidenceAttributions(
        {
          apiBaseUrl: API_BASE_URL,
          projectDirectionId:
            PROJECT_DIRECTION_ID,
          repositoryKey: REPOSITORY_KEY,
          roadmapNodeId: "build-mvp",
        },
        fetcher,
      );

    expect(result).toEqual([attribution]);

    const [requestUrl] = fetcher.mock.calls[0];

    expect(String(requestUrl)).toContain(
      "repository_key=github%3Aowner%2Frepository",
    );
    expect(String(requestUrl)).toContain(
      "project_direction_id=trusted-project-direction",
    );
    expect(String(requestUrl)).toContain(
      "roadmap_node_id=build-mvp",
    );
  });

  it("surfaces revision conflicts from the API", async () => {
    const fetcher = vi.fn<
      (
        input: RequestInfo | URL,
        options?: RequestInit,
      ) => Promise<Response>
    >();

    fetcher.mockResolvedValue(
      new Response(
        JSON.stringify({
          detail:
            "Repository evidence revision conflict.",
        }),
        {
          status: 409,
          headers: {
            "Content-Type": "application/json",
          },
        },
      ),
    );

    await expect(
      attachExecutionEvidence(
        {
          apiBaseUrl: API_BASE_URL,
          projectDirectionId:
            PROJECT_DIRECTION_ID,
          repositoryKey: REPOSITORY_KEY,
          evidenceKey: EVIDENCE_KEY,
          roadmapNodeId: "build-mvp",
          expectedRevision: 0,
        },
        fetcher,
      ),
    ).rejects.toMatchObject({
      message:
        "Repository evidence revision conflict.",
      status: 409,
    });
  });
});
