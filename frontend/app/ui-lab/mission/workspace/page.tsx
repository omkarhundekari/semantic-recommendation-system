"use client";

import Link from "next/link";
import {
  useSearchParams,
} from "next/navigation";
import {
  Suspense,
  useState,
} from "react";

import {
  ArrowLeft,
  ArrowRight,
  BookOpenCheck,
  CheckCircle2,
  ChevronRight,
  CircleDot,
  FileCheck2,
  GitBranch,
  Orbit,
  Radar,
  Sparkles,
} from "lucide-react";

import SolvynBackdrop from "@/components/experience/SolvynBackdrop";
import {
  GlassSurface,
  SignalPill,
  SolvynMark,
} from "@/components/experience/SolvynPrimitives";


type WorkspacePanel =
  | "trajectory"
  | "evidence"
  | "decisions"
  | "passport";


const panels: Array<{
  id: WorkspacePanel;
  label: string;
  description: string;
  icon: typeof Orbit;
  dormant?: boolean;
}> = [
  {
    id: "trajectory",
    label: "Trajectory",
    description: "Your current path",
    icon: Orbit,
  },
  {
    id: "evidence",
    label: "Evidence",
    description: "Proof appears as you build",
    icon: Radar,
    dormant: true,
  },
  {
    id: "decisions",
    label: "Decisions",
    description: "Architecture choices live here",
    icon: GitBranch,
    dormant: true,
  },
  {
    id: "passport",
    label: "Build Passport",
    description: "Your verified project story",
    icon: FileCheck2,
    dormant: true,
  },
];


function WorkspaceContent() {
  const searchParams = useSearchParams();
  const requestedGoal = searchParams.get("goal");

  const [activePanel, setActivePanel] =
    useState<WorkspacePanel>("trajectory");

  const goal =
    requestedGoal?.trim() ||
    "Build a project that proves my engineering ability";

  return (
    <main className="solvyn-experience min-h-screen text-slate-100">
      <SolvynBackdrop />

      <div className="relative z-10 mx-auto min-h-screen max-w-[1560px] px-4 pb-8 pt-4 sm:px-6 lg:px-8">
        <nav className="solvyn-nav">
          <div className="flex items-center gap-5">
            <SolvynMark />

            <div className="hidden h-5 w-px bg-white/[0.06] lg:block" />

            <div className="hidden max-w-md lg:block">
              <p className="truncate text-xs font-medium text-slate-300">
                {goal}
              </p>
              <p className="mt-1 text-[11px] text-slate-700">
                Project workspace
              </p>
            </div>
          </div>

          <Link
            href="/ui-lab/mission"
            className="inline-flex items-center gap-2 text-sm text-slate-500 transition hover:text-white"
          >
            <ArrowLeft className="h-4 w-4" />
            New mission
          </Link>
        </nav>

        <div className="grid gap-5 pt-5 lg:grid-cols-[230px_minmax(0,1fr)]">
          <aside className="lg:sticky lg:top-5 lg:h-[calc(100vh-2.5rem)]">
            <GlassSurface className="flex h-full flex-col p-3">
              <div className="px-3 pb-4 pt-3">
                <p className="solvyn-eyebrow">
                  PROJECT
                </p>

                <p className="mt-3 line-clamp-3 text-sm font-medium leading-6 text-white">
                  {goal}
                </p>
              </div>

              <div className="mt-2 grid gap-1">
                {panels.map((panel) => {
                  const Icon = panel.icon;
                  const active =
                    activePanel === panel.id;

                  return (
                    <button
                      key={panel.id}
                      type="button"
                      onClick={() =>
                        setActivePanel(panel.id)
                      }
                      className={`group flex w-full items-center gap-3 rounded-2xl px-3 py-3 text-left transition ${
                        active
                          ? "bg-sky-300/[0.07] text-white"
                          : "text-slate-500 hover:bg-white/[0.025] hover:text-slate-300"
                      }`}
                    >
                      <div
                        className={`grid h-8 w-8 shrink-0 place-items-center rounded-xl border ${
                          active
                            ? "border-sky-300/15 bg-sky-300/[0.06] text-sky-200"
                            : "border-white/[0.045] bg-white/[0.015] text-slate-700"
                        }`}
                      >
                        <Icon className="h-4 w-4" />
                      </div>

                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-medium">
                            {panel.label}
                          </span>

                          {panel.dormant && (
                            <span className="rounded-full border border-white/[0.05] px-1.5 py-0.5 text-[8px] uppercase tracking-[0.12em] text-slate-700">
                              dormant
                            </span>
                          )}
                        </div>

                        <p className="mt-1 truncate text-[10px] text-slate-700">
                          {panel.description}
                        </p>
                      </div>
                    </button>
                  );
                })}
              </div>

              <div className="mt-auto border-t border-white/[0.05] px-3 pt-4">
                <div className="flex items-center gap-2 text-[10px] text-slate-700">
                  <CircleDot className="h-3 w-3 text-emerald-300/60" />
                  Project active
                </div>
              </div>
            </GlassSurface>
          </aside>

          <section className="min-w-0">
            {activePanel === "trajectory" && (
              <TrajectoryView goal={goal} />
            )}

            {activePanel === "evidence" && (
              <DormantFeature
                eyebrow="EVIDENCE"
                title="Your proof will appear here."
                description="Solvyn will surface repository evidence, accepted execution proof, validation signals, and the work that supports each part of your trajectory."
                action="Connect execution evidence"
                icon={Radar}
              />
            )}

            {activePanel === "decisions" && (
              <DormantFeature
                eyebrow="DECISIONS"
                title="Important choices become visible."
                description="When your project reaches meaningful technical forks, Solvyn records the question, your decision, the evidence behind it, and the consequences that followed."
                action="No decisions yet"
                icon={GitBranch}
              />
            )}

            {activePanel === "passport" && (
              <DormantFeature
                eyebrow="BUILD PASSPORT"
                title="Your project story grows as you build."
                description="Verified milestones, technical decisions, execution evidence, adaptation history, and project outcomes will eventually become a portable proof of your engineering work."
                action="Passport is still forming"
                icon={BookOpenCheck}
              />
            )}
          </section>
        </div>
      </div>
    </main>
  );
}


function TrajectoryView({
  goal,
}: {
  goal: string;
}) {
  return (
    <div className="grid gap-5">
      <GlassSurface className="overflow-hidden p-6 sm:p-8">
        <div className="flex flex-col gap-8 xl:flex-row xl:items-start xl:justify-between">
          <div className="max-w-3xl">
            <SignalPill tone="emerald">
              Trajectory forming
            </SignalPill>

            <h1 className="mt-6 text-3xl font-semibold tracking-[-0.05em] text-white sm:text-5xl">
              Your path starts simple.
            </h1>

            <p className="mt-5 max-w-2xl text-sm leading-7 text-slate-500 sm:text-base">
              Solvyn progressively introduces detail as the project
              becomes real. You only see what matters at the current
              stage.
            </p>
          </div>

          <div className="min-w-[220px] rounded-2xl border border-white/[0.055] bg-black/10 p-4">
            <p className="text-[10px] uppercase tracking-[0.16em] text-slate-700">
              Current intent
            </p>

            <p className="mt-3 text-sm leading-6 text-slate-300">
              {goal}
            </p>
          </div>
        </div>

        <div className="relative mt-12 overflow-hidden rounded-[2rem] border border-white/[0.045] bg-slate-950/25 px-4 py-12 sm:px-8">
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(56,189,248,0.06),transparent_38%)]" />

          <div className="relative mx-auto max-w-4xl">
            <div className="absolute left-[8%] right-[8%] top-6 h-px bg-gradient-to-r from-emerald-300/40 via-sky-300/25 to-white/[0.04]" />

            <div className="relative grid grid-cols-4 gap-3">
              {[
                {
                  label: "Define",
                  state: "active",
                },
                {
                  label: "Build",
                  state: "future",
                },
                {
                  label: "Validate",
                  state: "future",
                },
                {
                  label: "Package",
                  state: "future",
                },
              ].map((node, index) => (
                <div
                  key={node.label}
                  className="text-center"
                >
                  <div
                    className={`relative mx-auto grid h-12 w-12 place-items-center rounded-full border ${
                      node.state === "active"
                        ? "border-emerald-300/30 bg-emerald-300/[0.08] shadow-[0_0_34px_rgba(110,231,183,0.12)]"
                        : "border-white/[0.055] bg-slate-950/70"
                    }`}
                  >
                    {node.state === "active" ? (
                      <Sparkles className="h-4 w-4 text-emerald-200" />
                    ) : (
                      <span className="font-mono text-[10px] text-slate-700">
                        0{index + 1}
                      </span>
                    )}
                  </div>

                  <p
                    className={`mt-4 text-xs font-medium ${
                      node.state === "active"
                        ? "text-emerald-100"
                        : "text-slate-600"
                    }`}
                  >
                    {node.label}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </GlassSurface>

      <div className="grid gap-5 xl:grid-cols-[1.15fr_0.85fr]">
        <GlassSurface className="p-6">
          <p className="solvyn-eyebrow">
            CURRENT STEP
          </p>

          <div className="mt-5 flex items-start gap-4">
            <div className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl border border-emerald-300/15 bg-emerald-300/[0.06]">
              <CheckCircle2 className="h-5 w-5 text-emerald-200" />
            </div>

            <div>
              <h2 className="text-xl font-semibold tracking-[-0.03em] text-white">
                Clarify what success means
              </h2>

              <p className="mt-2 max-w-2xl text-sm leading-7 text-slate-500">
                Before architecture, frameworks, or implementation,
                define the result that would make this project worth
                building.
              </p>

              <button
                type="button"
                className="mt-6 inline-flex items-center gap-2 text-sm font-medium text-sky-200 transition hover:text-white"
              >
                Continue
                <ArrowRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        </GlassSurface>

        <GlassSurface className="p-6">
          <p className="solvyn-eyebrow">
            WHAT COMES NEXT
          </p>

          <div className="mt-5 space-y-3">
            {[
              "A focused project direction",
              "A roadmap shaped around your constraints",
              "Evidence only when execution begins",
            ].map((item) => (
              <div
                key={item}
                className="flex items-center gap-3 rounded-2xl border border-white/[0.045] bg-white/[0.015] px-4 py-3"
              >
                <ChevronRight className="h-3.5 w-3.5 text-slate-700" />
                <span className="text-xs text-slate-500">
                  {item}
                </span>
              </div>
            ))}
          </div>
        </GlassSurface>
      </div>
    </div>
  );
}


function DormantFeature({
  eyebrow,
  title,
  description,
  action,
  icon: Icon,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action: string;
  icon: typeof Radar;
}) {
  return (
    <GlassSurface className="grid min-h-[72vh] place-items-center p-8">
      <div className="max-w-lg text-center">
        <div className="mx-auto grid h-16 w-16 place-items-center rounded-[1.35rem] border border-white/[0.06] bg-white/[0.02]">
          <Icon className="h-6 w-6 text-slate-600" />
        </div>

        <p className="solvyn-eyebrow mt-7">
          {eyebrow}
        </p>

        <h1 className="mt-4 text-3xl font-semibold tracking-[-0.045em] text-white">
          {title}
        </h1>

        <p className="mt-4 text-sm leading-7 text-slate-500">
          {description}
        </p>

        <div className="mt-8 inline-flex items-center gap-2 rounded-full border border-white/[0.05] bg-white/[0.015] px-4 py-2 text-xs text-slate-600">
          <CircleDot className="h-3 w-3" />
          {action}
        </div>
      </div>
    </GlassSurface>
  );
}


export default function MissionWorkspacePage() {
  return (
    <Suspense>
      <WorkspaceContent />
    </Suspense>
  );
}
