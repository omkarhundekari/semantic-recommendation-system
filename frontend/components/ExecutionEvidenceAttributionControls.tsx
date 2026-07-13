"use client";

import {
  useMemo,
  useState,
} from "react";

import {
  attachExecutionEvidence,
  detachExecutionEvidence,
  type EvidenceAttribution,
} from "@/lib/executionEvidenceAttributionApi";
import {
  ExecutionEvidenceApiError,
  type ExecutionEvidenceItem,
} from "@/lib/executionEvidenceApi";

type RoadmapStageOption = {
  id: string;
  title: string;
};

type Props = {
  apiBaseUrl: string;
  repositoryKey: string;
  revision: number;
  evidence: ExecutionEvidenceItem;
  roadmapStages: RoadmapStageOption[];
  attributions: EvidenceAttribution[];
  onAttributionsChanged: ({
    attributions,
    revision,
  }: {
    attributions: EvidenceAttribution[];
    revision: number;
  }) => void;
};

function evidenceKey(
  evidence: ExecutionEvidenceItem,
): string {
  return [
    evidence.provider,
    evidence.repository_full_name.toLowerCase(),
    evidence.evidence_type,
    evidence.external_id,
  ].join(":");
}

export default function ExecutionEvidenceAttributionControls({
  apiBaseUrl,
  repositoryKey,
  revision,
  evidence,
  roadmapStages,
  attributions,
  onAttributionsChanged,
}: Props) {
  const currentEvidenceKey = evidenceKey(evidence);
  const linkedAttributions = useMemo(
    () =>
      attributions.filter(
        (attribution) =>
          attribution.evidence_key ===
          currentEvidenceKey,
      ),
    [
      attributions,
      currentEvidenceKey,
    ],
  );

  const linkedStageIds = useMemo(
    () =>
      new Set(
        linkedAttributions.map(
          (attribution) =>
            attribution.roadmap_node_id,
        ),
      ),
    [linkedAttributions],
  );

  const availableRoadmapStages =
    useMemo(
      () =>
        roadmapStages.filter(
          (stage) =>
            !linkedStageIds.has(
              stage.id,
            ),
        ),
      [
        roadmapStages,
        linkedStageIds,
      ],
    );

  const [selectedStageId, setSelectedStageId] =
    useState("");
  const [error, setError] = useState("");
  const [pendingStageId, setPendingStageId] =
    useState<string | null>(null);

  async function attachSelectedStage() {
    if (!selectedStageId) {
      setError(
        "Choose a roadmap stage before attaching evidence.",
      );
      return;
    }

    setError("");
    setPendingStageId(selectedStageId);

    try {
      const response = await attachExecutionEvidence({
        apiBaseUrl,
        repositoryKey,
        evidenceKey: currentEvidenceKey,
        roadmapNodeId: selectedStageId,
        expectedRevision: revision,
      });

      onAttributionsChanged({
        attributions:
          response.stored.attributions,
        revision: response.stored.revision,
      });
      setSelectedStageId("");
    } catch (caughtError) {
      setError(
        caughtError instanceof ExecutionEvidenceApiError
          ? caughtError.message
          : "The evidence could not be attached.",
      );
    } finally {
      setPendingStageId(null);
    }
  }

  async function detachStage(
    roadmapNodeId: string,
  ) {
    setError("");
    setPendingStageId(roadmapNodeId);

    try {
      const response = await detachExecutionEvidence({
        apiBaseUrl,
        repositoryKey,
        evidenceKey: currentEvidenceKey,
        roadmapNodeId,
        expectedRevision: revision,
      });

      if (response.removed) {
        onAttributionsChanged({
          attributions: attributions.filter(
            (attribution) =>
              !(
                attribution.evidence_key ===
                  currentEvidenceKey &&
                attribution.roadmap_node_id ===
                  roadmapNodeId
              ),
          ),
          revision: revision + 1,
        });
      }
    } catch (caughtError) {
      setError(
        caughtError instanceof ExecutionEvidenceApiError
          ? caughtError.message
          : "The evidence attribution could not be removed.",
      );
    } finally {
      setPendingStageId(null);
    }
  }

  if (roadmapStages.length === 0) {
    return (
      <p className="mt-3 text-xs leading-5 text-slate-500">
        Generate and select a project direction before
        attaching this evidence to a roadmap stage.
      </p>
    );
  }

  return (
    <div className="mt-3 border-t border-white/10 pt-3">
      {availableRoadmapStages.length > 0 ? (
        <div className="flex flex-col gap-2 sm:flex-row">
          <label className="flex-1">
            <span className="sr-only">
              Roadmap stage for {evidence.title}
            </span>

            <select
              value={selectedStageId}
              onChange={(event) =>
                setSelectedStageId(
                  event.target.value,
                )
              }
              aria-label={`Roadmap stage for ${evidence.title}`}
              className="w-full rounded-xl border border-white/10 bg-slate-900 px-3 py-2 text-xs text-slate-200 outline-none"
            >
              <option value="">
                Choose roadmap stage
              </option>

              {availableRoadmapStages.map(
                (stage) => (
                  <option
                    key={stage.id}
                    value={stage.id}
                  >
                    {stage.title}
                  </option>
                ),
              )}
            </select>
          </label>

          <button
            type="button"
            onClick={() => {
              void attachSelectedStage();
            }}
            disabled={
              pendingStageId !== null
            }
            className="rounded-xl border border-emerald-300/20 bg-emerald-400/10 px-3 py-2 text-xs font-semibold text-emerald-100 transition hover:bg-emerald-400/20 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {pendingStageId ===
              selectedStageId &&
            selectedStageId
              ? "Attaching..."
              : "Attach to stage"}
          </button>
        </div>
      ) : (
        <p className="text-xs leading-5 text-emerald-200">
          This evidence is linked to every roadmap stage.
        </p>
      )}

      {linkedAttributions.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {linkedAttributions.map(
            (attribution) => {
              const stage =
                roadmapStages.find(
                  (candidate) =>
                    candidate.id ===
                    attribution.roadmap_node_id,
                );

              return (
                <span
                  key={`${attribution.evidence_key}:${attribution.roadmap_node_id}`}
                  className="inline-flex items-center gap-2 rounded-full border border-sky-300/20 bg-sky-400/10 px-3 py-1.5 text-xs text-sky-100"
                >
                  {stage?.title ??
                    attribution.roadmap_node_id}

                  <button
                    type="button"
                    onClick={() => {
                      void detachStage(
                        attribution.roadmap_node_id,
                      );
                    }}
                    disabled={
                      pendingStageId ===
                      attribution.roadmap_node_id
                    }
                    aria-label={`Remove ${evidence.title} from ${
                      stage?.title ??
                      attribution.roadmap_node_id
                    }`}
                    className="font-semibold text-sky-300 transition hover:text-white disabled:opacity-50"
                  >
                    ×
                  </button>
                </span>
              );
            },
          )}
        </div>
      )}

      {error && (
        <p
          role="alert"
          className="mt-3 text-xs leading-5 text-rose-200"
        >
          {error}
        </p>
      )}
    </div>
  );
}
