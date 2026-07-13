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
    repository: {
      provider: "github";
      owner: string;
      repository: string;
      canonical_url: string;
    };
  };
};

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
