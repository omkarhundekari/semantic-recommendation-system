export type ExecutionEvidenceType =
  | "commit"
  | "pull_request"
  | "release"
  | "workflow_run";

export type ExecutionEvidenceItem = {
  provider: "github";
  repository_full_name: string;
  evidence_type: ExecutionEvidenceType;
  external_id: string;
  title: string;
  description: string;
  url: string;
  occurred_at: string;
  metadata: Record<string, unknown>;
  first_seen_at: string;
  last_seen_at: string;
};

export type SourceSyncStatus =
  | "never_synced"
  | "succeeded"
  | "not_modified"
  | "failed";

export type SourceSyncSnapshot = {
  status: SourceSyncStatus;
  etag: string | null;
  pages_fetched: number;
  last_attempted_at: string | null;
  last_succeeded_at: string | null;
  error_message: string | null;
  rate_limit: {
    remaining: number | null;
    reset_epoch: number | null;
    limit: number | null;
    resource: string | null;
  };
};

export type ExecutionEvidenceSyncResponse = {
  created: boolean;
  sync: {
    repository_key: string;
    status:
      | "succeeded"
      | "partially_succeeded"
      | "failed";
    evidence: ExecutionEvidenceItem[];
    synced_counts: Partial<
      Record<ExecutionEvidenceType, number>
    >;
    failed_types: ExecutionEvidenceType[];
    errors: Partial<
      Record<ExecutionEvidenceType, string>
    >;
    sync_state: {
      repository_key: string;
      status:
        | "never_synced"
        | "syncing"
        | "succeeded"
        | "failed";
      latest_commit_sha: string | null;
      cursor: string | null;
      last_attempted_at: string | null;
      last_succeeded_at: string | null;
      error_message: string | null;
    };
    sync_snapshot: {
      repository_key: string;
      sources: Partial<
        Record<
          ExecutionEvidenceType,
          SourceSyncSnapshot
        >
      >;
    } | null;
  };
  stored: {
    schema_version: number;
    revision: number;
    saved_at: string;
    evidence: ExecutionEvidenceItem[];
    attributions: Array<{
      evidence_key: string;
      roadmap_node_id: string;
      source:
        | "deterministic"
        | "semantic"
        | "manual";
      confidence: number;
      rationale: string;
      status:
        | "suggested"
        | "accepted"
        | "rejected";
      decided_at: string | null;
    }>;
    repository: {
      provider: "github";
      owner: string;
      repository: string;
      canonical_url: string;
    };
  };
};

export type StoredExecutionEvidenceRepository =
  ExecutionEvidenceSyncResponse["stored"] & {
    sync_state?: ExecutionEvidenceSyncResponse["sync"]["sync_state"];
    sync_snapshot?: ExecutionEvidenceSyncResponse["sync"]["sync_snapshot"];
  };

export function buildRestoredExecutionEvidenceResponse(
  stored: StoredExecutionEvidenceRepository,
): ExecutionEvidenceSyncResponse {
  const repositoryKey =
    stored.sync_state?.repository_key ??
    [
      stored.repository.provider,
      `${stored.repository.owner}/${stored.repository.repository}`,
    ].join(":");

  const syncState =
    stored.sync_state ?? {
      repository_key: repositoryKey,
      status: "succeeded" as const,
      latest_commit_sha: null,
      cursor: null,
      last_attempted_at: null,
      last_succeeded_at: stored.saved_at,
      error_message: null,
    };

  return {
    created: false,
    sync: {
      repository_key: repositoryKey,
      status:
        syncState.status === "failed"
          ? "failed"
          : "succeeded",
      evidence: stored.evidence,
      synced_counts: {},
      failed_types: [],
      errors: {},
      sync_state: syncState,
      sync_snapshot:
        stored.sync_snapshot ?? {
          repository_key: repositoryKey,
          sources: {},
        },
    },
    stored,
  };
}

export async function loadExecutionEvidenceRepository(
  {
    apiBaseUrl,
    repositoryKey,
  }: {
    apiBaseUrl: string;
    repositoryKey: string;
  },
  fetcher: typeof fetch = fetch,
): Promise<ExecutionEvidenceSyncResponse> {
  const normalizedRepositoryKey =
    repositoryKey.trim();

  if (!normalizedRepositoryKey) {
    throw new ExecutionEvidenceApiError(
      "A repository key is required to restore execution evidence.",
    );
  }

  const encodedRepositoryKey =
    normalizedRepositoryKey
      .split("/")
      .map((segment) =>
        encodeURIComponent(segment),
      )
      .join("/");

  let response: Response;

  try {
    response = await fetcher(
      `${apiBaseUrl}/v1/execution-evidence/repositories/${encodedRepositoryKey}`,
    );
  } catch {
    throw new ExecutionEvidenceApiError(
      "Could not reach the execution-evidence API.",
    );
  }

  let payload: unknown;

  try {
    payload = await response.json();
  } catch {
    throw new ExecutionEvidenceApiError(
      "The execution-evidence API returned invalid JSON.",
      response.status,
    );
  }

  if (!response.ok) {
    const detail =
      typeof payload === "object" &&
      payload !== null &&
      "detail" in payload &&
      typeof payload.detail === "string"
        ? payload.detail
        : "The stored repository evidence could not be loaded.";

    throw new ExecutionEvidenceApiError(
      detail,
      response.status,
    );
  }

  return buildRestoredExecutionEvidenceResponse(
    payload as StoredExecutionEvidenceRepository,
  );
}


export class ExecutionEvidenceApiError extends Error {
  status: number | null;

  constructor(
    message: string,
    status: number | null = null,
  ) {
    super(message);
    this.name = "ExecutionEvidenceApiError";
    this.status = status;
  }
}

export async function syncExecutionEvidence(
  {
    apiBaseUrl,
    repositoryUrl,
    since,
  }: {
    apiBaseUrl: string;
    repositoryUrl: string;
    since?: string | null;
  },
  fetcher: typeof fetch = fetch,
): Promise<ExecutionEvidenceSyncResponse> {
  const normalizedRepositoryUrl = repositoryUrl.trim();

  if (!normalizedRepositoryUrl) {
    throw new ExecutionEvidenceApiError(
      "Enter a public GitHub repository URL.",
    );
  }

  let response: Response;

  try {
    response = await fetcher(
      `${apiBaseUrl}/v1/execution-evidence/repositories/sync`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          repository_url: normalizedRepositoryUrl,
          since: since?.trim() || null,
        }),
      },
    );
  } catch {
    throw new ExecutionEvidenceApiError(
      "Could not reach the execution-evidence API.",
    );
  }

  let payload: unknown;

  try {
    payload = await response.json();
  } catch {
    throw new ExecutionEvidenceApiError(
      "The execution-evidence API returned invalid JSON.",
      response.status,
    );
  }

  if (!response.ok) {
    const detail =
      typeof payload === "object" &&
      payload !== null &&
      "detail" in payload &&
      typeof payload.detail === "string"
        ? payload.detail
        : "The repository could not be synchronized.";

    throw new ExecutionEvidenceApiError(
      detail,
      response.status,
    );
  }

  return payload as ExecutionEvidenceSyncResponse;
}

export function getExecutionEvidenceCounts(
  response: ExecutionEvidenceSyncResponse,
): Record<ExecutionEvidenceType, number> {
  const counts: Record<ExecutionEvidenceType, number> = {
    commit: 0,
    pull_request: 0,
    release: 0,
    workflow_run: 0,
  };

  for (const item of response.stored.evidence) {
    counts[item.evidence_type] += 1;
  }

  return counts;
}
