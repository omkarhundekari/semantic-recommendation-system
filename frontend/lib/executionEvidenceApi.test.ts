import {
  describe,
  expect,
  it,
  vi,
} from "vitest";

import {
  ExecutionEvidenceApiError,
  getExecutionEvidenceCounts,
  syncExecutionEvidence,
  type ExecutionEvidenceSyncResponse,
} from "./executionEvidenceApi";

function successfulResponse(): ExecutionEvidenceSyncResponse {
  return {
    created: true,
    sync: {
      repository_key: "github:owner/repository",
      status: "succeeded",
      evidence: [],
      synced_counts: {
        commit: 1,
      },
      failed_types: [],
      errors: {},
      sync_state: {
        repository_key: "github:owner/repository",
        status: "succeeded",
        latest_commit_sha: "abc123",
        cursor: null,
        last_attempted_at:
          "2026-07-13T12:00:00+00:00",
        last_succeeded_at:
          "2026-07-13T12:00:00+00:00",
        error_message: null,
      },
      sync_snapshot: {
        repository_key: "github:owner/repository",
        sources: {},
      },
    },
    stored: {
      schema_version: 1,
      revision: 0,
      saved_at: "2026-07-13T12:00:00+00:00",
      repository: {
        provider: "github",
        owner: "owner",
        repository: "repository",
        canonical_url:
          "https://github.com/owner/repository",
      },
      evidence: [
        {
          provider: "github",
          repository_full_name: "owner/repository",
          evidence_type: "commit",
          external_id: "abc123",
          title: "Add evidence sync",
          description: "",
          url:
            "https://github.com/owner/repository/commit/abc123",
          occurred_at:
            "2026-07-13T10:00:00+00:00",
          metadata: {},
          first_seen_at:
            "2026-07-13T12:00:00+00:00",
          last_seen_at:
            "2026-07-13T12:00:00+00:00",
        },
      ],
    },
  };
}

describe("execution evidence API", () => {
  it("posts a normalized repository URL", async () => {
    const payload = successfulResponse();

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

    const result = await syncExecutionEvidence(
      {
        apiBaseUrl: "http://127.0.0.1:8000",
        repositoryUrl:
          "  https://github.com/owner/repository  ",
      },
      fetcher,
    );

    expect(result).toEqual(payload);
    expect(fetcher).toHaveBeenCalledTimes(1);

    const [, options] = fetcher.mock.calls[0];

    expect(options?.method).toBe("POST");
    expect(JSON.parse(String(options?.body))).toEqual({
      repository_url:
        "https://github.com/owner/repository",
      since: null,
    });
  });

  it("rejects an empty repository URL locally", async () => {
    const fetcher = vi.fn();

    await expect(
      syncExecutionEvidence(
        {
          apiBaseUrl: "http://127.0.0.1:8000",
          repositoryUrl: "   ",
        },
        fetcher,
      ),
    ).rejects.toThrow(
      "Enter a public GitHub repository URL.",
    );

    expect(fetcher).not.toHaveBeenCalled();
  });

  it("surfaces the backend validation detail", async () => {
    const fetcher = vi.fn(async () =>
      new Response(
        JSON.stringify({
          detail:
            "Only github.com repositories are supported.",
        }),
        {
          status: 422,
          headers: {
            "Content-Type": "application/json",
          },
        },
      ),
    );

    await expect(
      syncExecutionEvidence(
        {
          apiBaseUrl: "http://127.0.0.1:8000",
          repositoryUrl:
            "https://gitlab.com/owner/repository",
        },
        fetcher,
      ),
    ).rejects.toMatchObject({
      message:
        "Only github.com repositories are supported.",
      status: 422,
    } satisfies Partial<ExecutionEvidenceApiError>);
  });

  it("reports unreachable API failures", async () => {
    const fetcher = vi.fn(async () => {
      throw new Error("Connection refused.");
    });

    await expect(
      syncExecutionEvidence(
        {
          apiBaseUrl: "http://127.0.0.1:8000",
          repositoryUrl:
            "https://github.com/owner/repository",
        },
        fetcher,
      ),
    ).rejects.toThrow(
      "Could not reach the execution-evidence API.",
    );
  });

  it("counts stored evidence by type", () => {
    const payload = successfulResponse();

    payload.stored.evidence.push(
      {
        ...payload.stored.evidence[0],
        external_id: "43",
        evidence_type: "pull_request",
      },
      {
        ...payload.stored.evidence[0],
        external_id: "7001",
        evidence_type: "workflow_run",
      },
    );

    expect(getExecutionEvidenceCounts(payload)).toEqual({
      commit: 1,
      pull_request: 1,
      release: 0,
      workflow_run: 1,
    });
  });
});
