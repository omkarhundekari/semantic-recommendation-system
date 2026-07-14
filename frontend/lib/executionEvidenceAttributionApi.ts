import {
  ExecutionEvidenceApiError,
  type EvidenceAttribution,
} from "./executionEvidenceApi";

export type {
  EvidenceAttribution,
} from "./executionEvidenceApi";

export type AttributionMutationResponse = {
  created: boolean;
  attribution: EvidenceAttribution;
  stored: {
    schema_version: number;
    revision: number;
    saved_at: string;
    attributions: EvidenceAttribution[];
  };
};

export type AttributionDetachResponse = {
  removed: boolean;
};

type Fetcher = typeof fetch;

async function readApiResponse<T>(
  response: Response,
): Promise<T> {
  let payload: unknown;

  try {
    payload = await response.json();
  } catch {
    throw new ExecutionEvidenceApiError(
      "The attribution API returned invalid JSON.",
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
        : "The evidence attribution request failed.";

    throw new ExecutionEvidenceApiError(
      detail,
      response.status,
    );
  }

  return payload as T;
}

export async function attachExecutionEvidence(
  {
    apiBaseUrl,
    projectDirectionId,
    repositoryKey,
    evidenceKey,
    roadmapNodeId,
    rationale = "",
    expectedRevision,
  }: {
    apiBaseUrl: string;
    projectDirectionId: string;
    repositoryKey: string;
    evidenceKey: string;
    roadmapNodeId: string;
    rationale?: string;
    expectedRevision?: number | null;
  },
  fetcher: Fetcher = fetch,
): Promise<AttributionMutationResponse> {
  if (!projectDirectionId.trim()) {
    throw new ExecutionEvidenceApiError(
      "Trusted project identity is required before attaching evidence.",
    );
  }

  if (!roadmapNodeId.trim()) {
    throw new ExecutionEvidenceApiError(
      "Choose a roadmap stage before attaching evidence.",
    );
  }

  let response: Response;

  try {
    response = await fetcher(
      `${apiBaseUrl}/v1/execution-evidence/attributions`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          project_direction_id:
            projectDirectionId.trim(),
          repository_key: repositoryKey,
          evidence_key: evidenceKey,
          roadmap_node_id: roadmapNodeId.trim(),
          rationale: rationale.trim(),
          expected_revision:
            expectedRevision ?? null,
        }),
      },
    );
  } catch {
    throw new ExecutionEvidenceApiError(
      "Could not reach the evidence attribution API.",
    );
  }

  return readApiResponse<AttributionMutationResponse>(
    response,
  );
}

export async function detachExecutionEvidence(
  {
    apiBaseUrl,
    projectDirectionId,
    repositoryKey,
    evidenceKey,
    roadmapNodeId,
    expectedRevision,
  }: {
    apiBaseUrl: string;
    projectDirectionId: string;
    repositoryKey: string;
    evidenceKey: string;
    roadmapNodeId: string;
    expectedRevision?: number | null;
  },
  fetcher: Fetcher = fetch,
): Promise<AttributionDetachResponse> {
  let response: Response;

  try {
    response = await fetcher(
      `${apiBaseUrl}/v1/execution-evidence/attributions`,
      {
        method: "DELETE",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          project_direction_id:
            projectDirectionId.trim(),
          repository_key: repositoryKey,
          evidence_key: evidenceKey,
          roadmap_node_id: roadmapNodeId,
          expected_revision:
            expectedRevision ?? null,
        }),
      },
    );
  } catch {
    throw new ExecutionEvidenceApiError(
      "Could not reach the evidence attribution API.",
    );
  }

  return readApiResponse<AttributionDetachResponse>(
    response,
  );
}

export async function listExecutionEvidenceAttributions(
  {
    apiBaseUrl,
    projectDirectionId,
    repositoryKey,
    roadmapNodeId,
  }: {
    apiBaseUrl: string;
    projectDirectionId: string;
    repositoryKey: string;
    roadmapNodeId?: string | null;
  },
  fetcher: Fetcher = fetch,
): Promise<EvidenceAttribution[]> {
  const normalizedProjectDirectionId =
    projectDirectionId.trim();

  if (!normalizedProjectDirectionId) {
    throw new ExecutionEvidenceApiError(
      "Trusted project identity is required before listing evidence attributions.",
    );
  }

  const query = new URLSearchParams({
    repository_key: repositoryKey,
    project_direction_id:
      normalizedProjectDirectionId,
  });

  if (roadmapNodeId) {
    query.set(
      "roadmap_node_id",
      roadmapNodeId,
    );
  }

  let response: Response;

  try {
    response = await fetcher(
      `${apiBaseUrl}/v1/execution-evidence/attributions?${query.toString()}`,
    );
  } catch {
    throw new ExecutionEvidenceApiError(
      "Could not reach the evidence attribution API.",
    );
  }

  return readApiResponse<EvidenceAttribution[]>(
    response,
  );
}
