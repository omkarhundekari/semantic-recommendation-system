import {
  ShieldCheck,
  Target,
} from "lucide-react";

import type {
  RoadmapEvidenceCoverage,
} from "@/lib/roadmapEvidenceCoverage";

export default function RoadmapEvidenceCoverageSummary({
  coverage,
}: {
  coverage: RoadmapEvidenceCoverage;
}) {
  if (coverage.totalStageCount === 0) {
    return null;
  }

  const complete =
    coverage.coveredStageCount ===
    coverage.totalStageCount;

  return (
    <div
      aria-label="Roadmap execution evidence coverage"
      className={`rounded-2xl border p-4 ${
        complete
          ? "border-emerald-300/20 bg-emerald-400/[0.06]"
          : "border-amber-300/20 bg-amber-400/[0.06]"
      }`}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div
            className={`grid h-9 w-9 shrink-0 place-items-center rounded-xl ${
              complete
                ? "bg-emerald-300/10"
                : "bg-amber-300/10"
            }`}
          >
            {complete ? (
              <ShieldCheck className="h-4 w-4 text-emerald-200" />
            ) : (
              <Target className="h-4 w-4 text-amber-200" />
            )}
          </div>

          <div>
            <p
              className={`text-xs font-semibold uppercase tracking-[0.14em] ${
                complete
                  ? "text-emerald-200"
                  : "text-amber-200"
              }`}
            >
              Execution evidence coverage
            </p>

            <p className="mt-1 text-sm font-semibold text-white">
              {coverage.coveredStageCount}/
              {coverage.totalStageCount} roadmap stages
              covered
            </p>

            <p className="mt-1 text-xs leading-5 text-slate-400">
              {complete
                ? "Every roadmap stage has accepted repository evidence."
                : `${coverage.uncoveredStageIds.length} stage${
                    coverage.uncoveredStageIds.length === 1
                      ? ""
                      : "s"
                  } still need linked execution proof.`}
            </p>
          </div>
        </div>

        <p
          className={`text-xl font-semibold ${
            complete
              ? "text-emerald-100"
              : "text-amber-100"
          }`}
        >
          {coverage.coveragePercent}%
        </p>
      </div>

      <div className="mt-4 h-2 overflow-hidden rounded-full bg-white/[0.07]">
        <div
          className={`h-full rounded-full transition-all ${
            complete
              ? "bg-emerald-300"
              : "bg-amber-300"
          }`}
          style={{
            width: `${coverage.coveragePercent}%`,
          }}
        />
      </div>

      <p className="mt-3 text-xs text-slate-500">
        {coverage.acceptedAttributionCount} accepted proof
        link
        {coverage.acceptedAttributionCount === 1
          ? ""
          : "s"}
      </p>
    </div>
  );
}
