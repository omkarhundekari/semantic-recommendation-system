import type {
  EvidenceAttribution,
} from "./executionEvidenceApi";

export function selectProjectEvidenceAttributions({
  attributions,
  projectDirectionId,
}: {
  attributions: EvidenceAttribution[];
  projectDirectionId: string | null;
}): EvidenceAttribution[] {
  const normalizedProjectDirectionId =
    projectDirectionId?.trim() ?? "";

  if (!normalizedProjectDirectionId) {
    return [];
  }

  return attributions.filter(
    (attribution) =>
      attribution.project_direction_id ===
      normalizedProjectDirectionId,
  );
}
