import {
  ExecutionEvidenceApiError,
} from "./executionEvidenceApi";

export type EvidenceAttribution = {
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
};

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
    repositoryKey,
    evidenceKey,
    roadmapNodeId,
    expectedRevision,
  }: {
    apiBaseUrl: string;
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
    repositoryKey,
    roadmapNodeId,
  }: {
    apiBaseUrl: string;
    repositoryKey: string;
    roadmapNodeId?: string | null;
  },
  fetcher: Fetcher = fetch,
): Promise<EvidenceAttribution[]> {
  const query = new URLSearchParams({
    repository_key: repositoryKey,
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
