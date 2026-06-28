"use client";

import { AnimatePresence, motion } from "framer-motion";
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  CircleDot,
  Clock3,
  Code2,
  FileCheck2,
  GitBranch,
  LoaderCircle,
  ShieldCheck,
  Sparkles,
  Target,
  TriangleAlert,
} from "lucide-react";
import { FormEvent, useMemo, useState } from "react";

type Verification = {
  status: string;
  score: number;
  max_score: number;
  warnings: string[];
};

type RoadmapNode = {
  id: string;
  title: string;
  purpose: string;
  tasks: string[];
};

type Direction = {
  id: string;
  title: string;
  summary: string;
  scope: string;
  estimated_effort: string;
  portfolio_tier: string;
  difficulty: string;
  career_signal: string;
  why_it_fits: string;
  mvp_steps: string[];
  advanced_extensions: string[];
  tech_stack: string[];
  target_roles: string[];
  roadmap: RoadmapNode[];
  risks: string[];
  repairs_applied: string[];
  verification: Verification;
};

type IntelligenceResponse = {
  status: string;
  clarification_required?: boolean;
  clarification_message?: string;
  clarification_options?: string[];
  evidence_route?: string;
  inferred_domain_family?: string | null;
  family_confidence?: number | null;
  inferred_focus?: string | null;
  resolved_planning_domain?: string | null;
  source_counts?: {
    research_papers: number;
    project_patterns: number;
    github_repositories: number;
  };
  research_evidence_assessment?: {
    confidence: {
      level: string;
      reason: string;
    };
    evidence: {
      alignment_summary?: {
        direct: number;
        adjacent: number;
        weak: number;
      };
    };
  };
  directions: Direction[];
};

const examplePrompts = [
  "AI project for an ML engineer role in 3 weeks",
  "React portfolio project for frontend roles",
  "Cloud cost optimization project with Python",
];

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

const guidedPaths = [
  {
    label: "Analyze data and make decisions",
    description: "Models, analytics, risk scoring, and explainability.",
    selectedDirection: "AI / ML",
  },
  {
    label: "Build a product people use",
    description: "Frontend, backend, workflows, and polished user experience.",
    selectedDirection: "Full-stack / Software Engineering",
  },
  {
    label: "Improve cloud systems",
    description: "Automation, observability, cost optimization, and reliability.",
    selectedDirection: "Cloud / Platform",
  },
  {
    label: "Protect systems and manage risk",
    description: "Security analytics, access policies, logs, and threat signals.",
    selectedDirection: "Cybersecurity",
  },
];

const tierVisuals: Record<
  string,
  {
    label: string;
    glow: string;
    accent: string;
    border: string;
    badge: string;
  }
> = {
  Easy: {
    label: "Quick Win",
    glow: "shadow-emerald-500/10",
    accent: "from-emerald-300 via-cyan-200 to-sky-300",
    border: "hover:border-emerald-300/40",
    badge: "bg-emerald-400/10 text-emerald-200",
  },
  Medium: {
    label: "Portfolio Build",
    glow: "shadow-sky-500/10",
    accent: "from-sky-300 via-cyan-200 to-indigo-300",
    border: "hover:border-sky-300/40",
    badge: "bg-sky-400/10 text-sky-200",
  },
  Hard: {
    label: "Flagship Challenge",
    glow: "shadow-violet-500/10",
    accent: "from-violet-300 via-fuchsia-200 to-indigo-300",
    border: "hover:border-violet-300/40",
    badge: "bg-violet-400/10 text-violet-200",
  },
};

function getTierVisual(direction: Direction) {
  return (
    tierVisuals[direction.difficulty] ??
    tierVisuals.Medium
  );
}

function confidenceLabel(value?: number | null) {
  if (value == null) {
    return "Evidence-informed";
  }

  if (value >= 0.75) {
    return "High confidence";
  }

  if (value >= 0.58) {
    return "Grounded confidence";
  }

  return "Emerging signal";
}

export default function Home() {
  const [goal, setGoal] = useState("");
  const [showConstraints, setShowConstraints] = useState(false);
  const [skillLevel, setSkillLevel] = useState("intermediate");
  const [timeAvailable, setTimeAvailable] = useState("3 weeks");
  const [targetRole, setTargetRole] = useState("");
  const [preferredStack, setPreferredStack] = useState("");
  const [result, setResult] = useState<IntelligenceResponse | null>(null);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [showHelpChooser, setShowHelpChooser] = useState(false);
  const [selectedDirectionId, setSelectedDirectionId] = useState<string | null>(
    null,
  );
  const [activeRoadmapNodeId, setActiveRoadmapNodeId] = useState<string | null>(
    null,
  );

  const selectedDirection = useMemo(
    () =>
      result?.directions.find(
        (direction) => direction.id === selectedDirectionId,
      ) ?? null,
    [result, selectedDirectionId],
  );

  async function requestDirections(
    nextGoal: string,
    selectedDirection?: string,
  ) {
    if (nextGoal.trim().length < 3) {
      setError("Describe the kind of project you want to build first.");
      return;
    }

    setError("");
    setResult(null);
    setSelectedDirectionId(null);
    setActiveRoadmapNodeId(null);
    setShowHelpChooser(false);
    setIsLoading(true);

    try {
      const response = await fetch(
        `${API_BASE_URL}/v1/project-intelligence`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            goal: nextGoal.trim(),
            selected_direction: selectedDirection ?? null,
            constraints: {
              skill_level: skillLevel,
              time_available: timeAvailable,
              target_roles: targetRole ? [targetRole] : [],
              preferred_stack: preferredStack
                ? preferredStack
                    .split(",")
                    .map((item) => item.trim())
                    .filter(Boolean)
                : [],
            },
          }),
        },
      );

      const payload = (await response.json()) as IntelligenceResponse;

      if (!response.ok) {
        throw new Error("The planning API returned an unexpected response.");
      }

      setResult(payload);

      if (payload.status === "ready" && payload.directions.length > 0) {
        const firstDirection = payload.directions[0];
        setSelectedDirectionId(firstDirection.id);
        setActiveRoadmapNodeId(firstDirection.roadmap[0]?.id ?? null);
      }
    } catch {
      setError(
        "Could not reach the planning API. Confirm FastAPI is running on port 8000.",
      );
    } finally {
      setIsLoading(false);
    }
  }

  async function generateDirections(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await requestDirections(goal);
  }

  function handleClarificationChoice(option: string) {
    if (option.toLowerCase() === "help me choose") {
      setShowHelpChooser(true);
      return;
    }

    void requestDirections(goal, option);
  }

  function chooseGuidedPath(selectedDirection: string) {
    void requestDirections(goal, selectedDirection);
  }

  function chooseDirection(direction: Direction) {
    setSelectedDirectionId(direction.id);
    setActiveRoadmapNodeId(direction.roadmap[0]?.id ?? null);

    window.setTimeout(() => {
      document
        .getElementById("project-roadmap")
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 80);
  }

  return (
    <main className="min-h-screen overflow-hidden bg-[#07111f] text-slate-100">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_50%_10%,rgba(56,189,248,0.16),transparent_34%),radial-gradient(circle_at_88%_78%,rgba(129,140,248,0.12),transparent_28%),radial-gradient(circle_at_8%_86%,rgba(16,185,129,0.08),transparent_25%)]" />

      <section className="relative mx-auto max-w-6xl px-6 py-7 lg:px-10">
        <nav className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-xl border border-sky-300/30 bg-sky-400/10">
              <Sparkles className="h-5 w-5 text-sky-300" />
            </div>

            <div>
              <p className="text-sm font-semibold tracking-wide text-white">
                Research-to-Prototype
              </p>
              <p className="text-xs text-slate-400">Intelligence Engine</p>
            </div>
          </div>

          <span className="hidden rounded-full border border-emerald-300/20 bg-emerald-400/10 px-3 py-1.5 text-xs font-medium text-emerald-200 sm:block">
            Evidence-first planning
          </span>
        </nav>

        <motion.div
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55 }}
          className="mx-auto flex w-full max-w-4xl flex-col justify-center py-16"
        >
          <div className="mb-6 inline-flex w-fit items-center gap-2 rounded-full border border-sky-300/20 bg-slate-950/30 px-3 py-1.5 text-sm text-sky-100 backdrop-blur">
            <span className="h-2 w-2 rounded-full bg-sky-300" />
            Evidence-backed project planning
          </div>

          <h1 className="text-5xl font-semibold tracking-[-0.045em] text-white sm:text-6xl lg:text-7xl">
            What should you{" "}
            <span className="bg-gradient-to-r from-sky-300 via-cyan-200 to-indigo-300 bg-clip-text text-transparent">
              build next?
            </span>
          </h1>

          <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-300">
            Describe your goal. We turn research and implementation signals into
            three practical project directions, then guide you through the one
            you choose.
          </p>

          <form
            onSubmit={generateDirections}
            className="mt-10 rounded-[1.75rem] border border-white/10 bg-slate-950/45 p-3 shadow-2xl shadow-sky-950/30 backdrop-blur-xl"
          >
            <textarea
              value={goal}
              onChange={(event) => setGoal(event.target.value)}
              placeholder="I want an AI project for an ML engineer role. I know Python and basic React, have 3 weeks, and want something impressive but realistic."
              className="min-h-36 w-full resize-none bg-transparent px-4 py-3 text-base leading-7 text-white outline-none placeholder:text-slate-500"
            />

            <div className="border-t border-white/10 px-2 pt-3">
              <button
                type="button"
                onClick={() => setShowConstraints((current) => !current)}
                className="flex w-full items-center justify-between rounded-xl px-2 py-2 text-sm text-slate-400 transition hover:bg-white/[0.03] hover:text-slate-200"
              >
                <span>Refine with role, timeline, and preferred stack</span>

                {showConstraints ? (
                  <ChevronUp className="h-4 w-4" />
                ) : (
                  <ChevronDown className="h-4 w-4" />
                )}
              </button>

              {showConstraints && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  transition={{ duration: 0.2 }}
                  className="grid gap-3 overflow-hidden py-3 sm:grid-cols-2"
                >
                  <label className="text-sm text-slate-400">
                    Skill level
                    <select
                      value={skillLevel}
                      onChange={(event) => setSkillLevel(event.target.value)}
                      className="mt-2 w-full rounded-xl border border-white/10 bg-slate-900 px-3 py-2.5 text-sm text-slate-200 outline-none"
                    >
                      <option value="beginner">Beginner</option>
                      <option value="intermediate">Intermediate</option>
                      <option value="advanced">Advanced</option>
                    </select>
                  </label>

                  <label className="text-sm text-slate-400">
                    Available time
                    <select
                      value={timeAvailable}
                      onChange={(event) => setTimeAvailable(event.target.value)}
                      className="mt-2 w-full rounded-xl border border-white/10 bg-slate-900 px-3 py-2.5 text-sm text-slate-200 outline-none"
                    >
                      <option value="1 week">1 week</option>
                      <option value="2 weeks">2 weeks</option>
                      <option value="3 weeks">3 weeks</option>
                      <option value="1 month">1 month</option>
                    </select>
                  </label>

                  <label className="text-sm text-slate-400">
                    Target role
                    <input
                      value={targetRole}
                      onChange={(event) => setTargetRole(event.target.value)}
                      placeholder="ML Engineer"
                      className="mt-2 w-full rounded-xl border border-white/10 bg-slate-900 px-3 py-2.5 text-sm text-slate-200 outline-none placeholder:text-slate-500"
                    />
                  </label>

                  <label className="text-sm text-slate-400">
                    Preferred stack
                    <input
                      value={preferredStack}
                      onChange={(event) => setPreferredStack(event.target.value)}
                      placeholder="Python, React, FastAPI"
                      className="mt-2 w-full rounded-xl border border-white/10 bg-slate-900 px-3 py-2.5 text-sm text-slate-200 outline-none placeholder:text-slate-500"
                    />
                  </label>
                </motion.div>
              )}
            </div>

            <div className="flex flex-col gap-3 border-t border-white/10 px-2 pt-3 sm:flex-row sm:items-center sm:justify-between">
              <span className="text-sm text-slate-400">
                Grounded in research, implementation references, and realistic scope.
              </span>

              <button
                type="submit"
                disabled={isLoading}
                className="inline-flex items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-sky-400 to-indigo-400 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:scale-[1.02] hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isLoading ? (
                  <>
                    <LoaderCircle className="h-4 w-4 animate-spin" />
                    Building plan
                  </>
                ) : (
                  <>
                    Generate directions
                    <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </button>
            </div>
          </form>

          <div className="mt-5 flex flex-wrap gap-2">
            {examplePrompts.map((prompt) => (
              <button
                key={prompt}
                type="button"
                onClick={() => setGoal(prompt)}
                className="rounded-full border border-white/10 bg-white/[0.035] px-3 py-2 text-sm text-slate-300 transition hover:border-sky-300/30 hover:bg-sky-400/10 hover:text-sky-100"
              >
                {prompt}
              </button>
            ))}
          </div>

          {error && (
            <div className="mt-5 flex items-center gap-2 rounded-2xl border border-rose-300/20 bg-rose-400/10 px-4 py-3 text-sm text-rose-100">
              <AlertCircle className="h-4 w-4" />
              {error}
            </div>
          )}

          <div className="mt-10 flex flex-wrap gap-6 text-sm text-slate-400">
            <span className="inline-flex items-center gap-2">
              <Target className="h-4 w-4 text-sky-300" />
              Role-aware
            </span>

            <span className="inline-flex items-center gap-2">
              <Clock3 className="h-4 w-4 text-sky-300" />
              Timeline-aware
            </span>

            <span>Three distinct directions, not a generic list.</span>
          </div>
        </motion.div>

        {result && result.status !== "ready" && (
          <section className="border-t border-white/10 py-12">
            <motion.div
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              className="rounded-[2rem] border border-amber-300/20 bg-amber-400/10 p-6 shadow-xl shadow-amber-950/10"
            >
              <div className="flex items-start gap-4">
                <div className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-amber-300/10">
                  <CircleDot className="h-5 w-5 text-amber-200" />
                </div>

                <div>
                  <p className="text-sm font-medium text-amber-100">
                    One quick decision first
                  </p>
                  <h2 className="mt-1 text-2xl font-semibold text-white">
                    {result.clarification_message ??
                      "Give the system one more direction."}
                  </h2>
                  <p className="mt-3 max-w-2xl leading-7 text-amber-50/80">
                    We avoid inventing a project when your goal is too broad.
                    Choose a direction and we will build a grounded plan around it.
                  </p>

                  <div className="mt-5 flex flex-wrap gap-2">
                    {(result.clarification_options ?? []).map((option) => (
                      <button
                        key={option}
                        type="button"
                        onClick={() => handleClarificationChoice(option)}
                        className="rounded-full border border-amber-200/20 bg-slate-950/35 px-4 py-2 text-sm text-amber-100 transition hover:border-amber-200/50 hover:bg-amber-100/10"
                      >
                        {option}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </motion.div>
            {showHelpChooser && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-5 rounded-3xl border border-sky-300/20 bg-slate-950/45 p-5"
              >
                <p className="text-sm font-medium text-sky-200">
                  Let’s narrow it by what you enjoy building
                </p>
                <p className="mt-2 text-sm leading-6 text-slate-400">
                  This does not lock you into a project. It simply gives the
                  intelligence engine a trustworthy direction to investigate.
                </p>

                <div className="mt-5 grid gap-3 sm:grid-cols-2">
                  {guidedPaths.map((path) => (
                    <button
                      key={path.label}
                      type="button"
                      onClick={() => chooseGuidedPath(path.selectedDirection)}
                      className="rounded-2xl border border-white/10 bg-white/[0.025] p-4 text-left transition hover:border-sky-300/40 hover:bg-sky-400/10"
                    >
                      <p className="font-medium text-white">{path.label}</p>
                      <p className="mt-2 text-sm leading-6 text-slate-400">
                        {path.description}
                      </p>
                    </button>
                  ))}
                </div>
              </motion.div>
            )}
          </section>
        )}

        {result?.status === "ready" && (
          <>
            <section className="border-t border-white/10 py-12">
              <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
                <div>
                  <p className="text-sm font-medium text-sky-200">
                    Generated project directions
                  </p>
                  <h2 className="mt-2 text-3xl font-semibold text-white">
                    Choose your build path
                  </h2>
                </div>

                <div className="text-sm text-slate-400 sm:text-right">
                  <p>
                    {result.inferred_domain_family?.replaceAll("_", " ") ??
                      "General"}{" "}
                    ·{" "}
                    {(
                      result.resolved_planning_domain ??
                      result.inferred_focus ??
                      "focused"
                    ).replaceAll("_", " ")}
                  </p>
                  <p className="mt-1">
                    {confidenceLabel(result.family_confidence)} ·{" "}
                    {result.source_counts?.research_papers ?? 0} research ·{" "}
                    {result.source_counts?.project_patterns ?? 0} patterns ·{" "}
                    {result.source_counts?.github_repositories ?? 0} repositories
                  </p>
                </div>
              </div>

              {result.research_evidence_assessment && (
                <div className="mt-6 rounded-2xl border border-sky-300/15 bg-sky-300/[0.05] p-5">
                  <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-sky-200">
                        Research evidence
                      </p>
                      <p className="mt-2 text-lg font-semibold capitalize text-white">
                        {result.research_evidence_assessment.confidence.level} support
                      </p>
                      <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">
                        {result.research_evidence_assessment.confidence.reason}
                      </p>
                    </div>

                    <div className="grid grid-cols-3 gap-2 text-center text-xs">
                      <div className="rounded-xl border border-white/10 bg-slate-950/40 px-3 py-2">
                        <p className="font-semibold text-emerald-200">
                          {result.research_evidence_assessment.evidence.alignment_summary?.direct ?? 0}
                        </p>
                        <p className="mt-1 text-slate-400">direct</p>
                      </div>
                      <div className="rounded-xl border border-white/10 bg-slate-950/40 px-3 py-2">
                        <p className="font-semibold text-amber-200">
                          {result.research_evidence_assessment.evidence.alignment_summary?.adjacent ?? 0}
                        </p>
                        <p className="mt-1 text-slate-400">adjacent</p>
                      </div>
                      <div className="rounded-xl border border-white/10 bg-slate-950/40 px-3 py-2">
                        <p className="font-semibold text-slate-200">
                          {result.research_evidence_assessment.evidence.alignment_summary?.weak ?? 0}
                        </p>
                        <p className="mt-1 text-slate-400">weak</p>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              <div className="mt-8 grid gap-5 lg:grid-cols-3">
                {result.directions.map((direction, index) => {
                  const visual = getTierVisual(direction);
                  const isSelected = direction.id === selectedDirectionId;

                  return (
                    <motion.button
                      key={direction.id}
                      type="button"
                      onClick={() => chooseDirection(direction)}
                      initial={{ opacity: 0, y: 18 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.35, delay: index * 0.08 }}
                      whileHover={{ y: -8, scale: 1.015 }}
                      whileTap={{ scale: 0.985 }}
                      className={`group relative overflow-hidden rounded-[1.8rem] border bg-slate-950/50 p-5 text-left backdrop-blur-xl transition ${visual.border} ${
                        isSelected
                          ? "border-white/35 shadow-2xl"
                          : "border-white/10"
                      } ${visual.glow}`}
                    >
                      <div
                        className={`pointer-events-none absolute inset-x-0 top-0 h-1 bg-gradient-to-r ${visual.accent} opacity-60 transition group-hover:opacity-100`}
                      />

                      {isSelected && (
                        <motion.div
                          layoutId="selected-direction-glow"
                          className="pointer-events-none absolute inset-0 bg-gradient-to-br from-white/[0.08] via-transparent to-transparent"
                        />
                      )}

                      <div className="relative">
                        <div className="flex items-start justify-between gap-3">
                          <span
                            className={`rounded-full px-3 py-1 text-xs font-medium ${visual.badge}`}
                          >
                            {direction.portfolio_tier}
                          </span>

                          <span className="text-xs text-slate-400">
                            {direction.estimated_effort}
                          </span>
                        </div>

                        <h3 className="mt-5 text-xl font-semibold text-white">
                          {direction.title}
                        </h3>

                        <p className="mt-3 text-sm leading-6 text-slate-300">
                          {direction.summary}
                        </p>

                        <div className="mt-5 border-t border-white/10 pt-4">
                          <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">
                            Why it fits
                          </p>

                          <p className="mt-2 text-sm leading-6 text-slate-400">
                            {direction.why_it_fits}
                          </p>
                        </div>

                        <div className="mt-5 flex flex-wrap gap-2">
                          {direction.tech_stack.slice(0, 4).map((technology) => (
                            <span
                              key={technology}
                              className="rounded-full border border-white/10 bg-white/[0.035] px-2.5 py-1 text-xs text-slate-300"
                            >
                              {technology}
                            </span>
                          ))}
                        </div>

                        <div className="mt-5 flex items-center justify-between border-t border-white/10 pt-4 text-xs">
                          <span className="inline-flex items-center gap-1.5 text-emerald-200">
                            <ShieldCheck className="h-4 w-4" />
                            Verified {direction.verification.score}/
                            {direction.verification.max_score}
                          </span>

                          <span className="inline-flex items-center gap-1 text-slate-300 transition group-hover:text-white">
                            Explore roadmap
                            <ArrowRight className="h-3.5 w-3.5" />
                          </span>
                        </div>
                      </div>
                    </motion.button>
                  );
                })}
              </div>
            </section>

            <AnimatePresence mode="wait">
              {selectedDirection && (
                <motion.section
                  id="project-roadmap"
                  key={selectedDirection.id}
                  initial={{ opacity: 0, y: 18 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  transition={{ duration: 0.35 }}
                  className="scroll-mt-7 border-t border-white/10 py-14"
                >
                  <div className="rounded-[2rem] border border-white/10 bg-slate-950/45 p-6 shadow-2xl shadow-sky-950/20 backdrop-blur-xl sm:p-8">
                    <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
                      <div className="max-w-3xl">
                        <div className="inline-flex items-center gap-2 rounded-full border border-sky-300/20 bg-sky-400/10 px-3 py-1.5 text-sm text-sky-100">
                          <GitBranch className="h-4 w-4" />
                          Interactive execution roadmap
                        </div>

                        <h2 className="mt-5 text-3xl font-semibold tracking-[-0.03em] text-white sm:text-4xl">
                          {selectedDirection.title}
                        </h2>

                        <p className="mt-4 text-base leading-7 text-slate-300">
                          {selectedDirection.summary}
                        </p>
                      </div>

                      <div className="rounded-2xl border border-white/10 bg-white/[0.025] p-4 text-sm text-slate-300 lg:min-w-64">
                        <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">
                          Build signal
                        </p>
                        <p className="mt-2 font-medium text-white">
                          {selectedDirection.career_signal} career signal
                        </p>
                        <p className="mt-2 text-slate-400">
                          {selectedDirection.estimated_effort} ·{" "}
                          {selectedDirection.difficulty}
                        </p>
                      </div>
                    </div>

                    <div className="mt-10 grid gap-8 lg:grid-cols-[minmax(0,1.15fr)_minmax(300px,0.85fr)]">
                      <div className="relative">
                        <div className="absolute bottom-8 left-[18px] top-8 w-px bg-gradient-to-b from-sky-300/60 via-indigo-300/40 to-violet-300/30 sm:left-1/2" />

                        <div className="space-y-7">
                          {selectedDirection.roadmap.map((node, index) => {
                            const isActive = node.id === activeRoadmapNodeId;
                            const isRight = index % 2 === 1;

                            return (
                              <motion.button
                                key={node.id}
                                type="button"
                                onClick={() => setActiveRoadmapNodeId(node.id)}
                                initial={{ opacity: 0, x: isRight ? 14 : -14 }}
                                animate={{ opacity: 1, x: 0 }}
                                transition={{
                                  duration: 0.3,
                                  delay: index * 0.07,
                                }}
                                whileHover={{ scale: 1.01 }}
                                className={`relative flex w-full items-center gap-4 text-left sm:grid sm:grid-cols-[1fr_40px_1fr] ${
                                  isRight ? "sm:[&>div:first-child]:order-3" : ""
                                }`}
                              >
                                <div
                                  className={`rounded-2xl border p-4 transition sm:col-span-1 ${
                                    isActive
                                      ? "border-sky-200/50 bg-sky-300/10 shadow-xl shadow-sky-500/10"
                                      : "border-white/10 bg-white/[0.025] hover:border-white/25 hover:bg-white/[0.045]"
                                  }`}
                                >
                                  <div className="flex items-center gap-2">
                                    <span className="text-xs font-semibold text-sky-200">
                                      0{index + 1}
                                    </span>
                                    <span className="text-xs uppercase tracking-[0.13em] text-slate-500">
                                      Stage
                                    </span>
                                  </div>

                                  <p className="mt-2 font-semibold text-white">
                                    {node.title}
                                  </p>

                                  <p className="mt-1 text-sm leading-6 text-slate-400">
                                    {node.purpose}
                                  </p>
                                </div>

                                <div className="relative z-10 hidden h-10 w-10 place-items-center sm:grid">
                                  <div
                                    className={`grid h-9 w-9 place-items-center rounded-full border transition ${
                                      isActive
                                        ? "border-sky-200/70 bg-sky-300 text-slate-950 shadow-lg shadow-sky-300/30"
                                        : "border-white/20 bg-slate-950 text-slate-400"
                                    }`}
                                  >
                                    <CheckCircle2 className="h-4 w-4" />
                                  </div>
                                </div>

                                <div className="hidden sm:block" />
                              </motion.button>
                            );
                          })}
                        </div>
                      </div>

                      <RoadmapDetailPanel
                        direction={selectedDirection}
                        activeNodeId={activeRoadmapNodeId}
                      />
                    </div>
                  </div>
                </motion.section>
              )}
            </AnimatePresence>
          </>
        )}
      </section>
    </main>
  );
}

function RoadmapDetailPanel({
  direction,
  activeNodeId,
}: {
  direction: Direction;
  activeNodeId: string | null;
}) {
  const activeNode =
    direction.roadmap.find((node) => node.id === activeNodeId) ??
    direction.roadmap[0];

  if (!activeNode) {
    return null;
  }

  return (
    <AnimatePresence mode="wait">
      <motion.aside
        key={activeNode.id}
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -8 }}
        transition={{ duration: 0.22 }}
        className="sticky top-6 h-fit rounded-[1.6rem] border border-sky-300/15 bg-slate-950/80 p-5 shadow-2xl shadow-sky-950/20"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.14em] text-sky-300">
              Selected stage
            </p>
            <h3 className="mt-2 text-xl font-semibold text-white">
              {activeNode.title}
            </h3>
          </div>

          <Code2 className="h-5 w-5 text-sky-300" />
        </div>

        <p className="mt-3 text-sm leading-6 text-slate-400">
          {activeNode.purpose}
        </p>

        <div className="mt-6">
          <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">
            Build this next
          </p>

          <ul className="mt-3 space-y-3">
            {activeNode.tasks.map((task, index) => (
              <li
                key={task}
                className="flex gap-3 rounded-xl border border-white/[0.06] bg-white/[0.025] p-3 text-sm leading-6 text-slate-300"
              >
                <span className="grid h-6 w-6 shrink-0 place-items-center rounded-lg bg-sky-300/10 text-xs font-semibold text-sky-200">
                  {index + 1}
                </span>
                {task}
              </li>
            ))}
          </ul>
        </div>

        {direction.risks.length > 0 && (
          <div className="mt-6 rounded-2xl border border-amber-300/15 bg-amber-300/[0.06] p-4">
            <p className="inline-flex items-center gap-2 text-sm font-medium text-amber-100">
              <TriangleAlert className="h-4 w-4" />
              Keep the scope honest
            </p>

            <ul className="mt-3 space-y-2">
              {direction.risks.slice(0, 2).map((risk) => (
                <li
                  key={risk}
                  className="text-sm leading-6 text-amber-100/75"
                >
                  {risk}
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="mt-6 border-t border-white/10 pt-4">
          <p className="inline-flex items-center gap-2 text-sm text-slate-300">
            <FileCheck2 className="h-4 w-4 text-emerald-300" />
            {direction.verification.status === "passed"
              ? "Plan verified against role, scope, and evidence."
              : "Plan has review notes before execution."}
          </p>
        </div>
      </motion.aside>
    </AnimatePresence>
  );
}
