"use client";

import {
  buildResumeReadyParagraph,
  formatPortfolioSummaryText,
  generatePortfolioSummary,
  type PortfolioSummary,
  type PortfolioWorkspaceLike,
} from "@/lib/portfolioSummary";
import { validateProof } from "@/lib/proofValidation";

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
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

type Verification = {
  status: string;
  score: number;
  max_score: number;
  warnings: string[];
};

type DecisionTraceInspiration = {
  title: string;
  source_type: string;
  url?: string | null;
};

type DecisionTrace = {
  research_support_scope:
    | "idea_specific"
    | "mixed"
    | "planning_domain";
  idea_specific_rationale: string;
  primary_inspiration?: DecisionTraceInspiration | null;
  supporting_papers?: Array<{
    document_id: string;
    title: string;
  }>;
  implementation_references?: Array<{
    title: string;
    source_type: string;
  }>;
};

type GuidedMissionStep = {
  step_id: string;
  title: string;
  explanation: string;
  action: string;
  starter_command?: string | null;
  starter_files: string[];
  done_when: string;
  common_confusion: string;
  decision_point?: string | null;
  proof_type: string;
  proof_prompt: string;
  expected_output_patterns: string[];
  interview_takeaway: string;
};

type RoadmapNode = {
  id: string;
  title: string;
  purpose: string;
  tasks: string[];
  stage_type?: string | null;
  objective?: string | null;
  why_it_matters?: string | null;
  commands?: string[];
  expected_outputs?: string[];
  acceptance_criteria?: string[];
  validation_checks?: string[];
  common_errors?: string[];
  portfolio_artifact?: string | null;
  unlock_condition?: string | null;
  guided_steps?: GuidedMissionStep[];
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
  decision_trace?: DecisionTrace | null;
};

type PresentationProjectDirection = {
  title: string;
  level: string;
  estimated_time: string;
  what_you_will_build: string;
  why_it_matters: string;
  skills_shown: string[];
  interview_talking_point: string;
  evidence_badge: string;
  confidence_explanation: string;
  open_questions: string[];
  evidence_summary: string;
};

type FrontendProjectDirection = {
  id: string;
  title: string;
  tier: string;
  level: string;
  estimated_time: string;
  summary: string;
  evidence_badge: string;
  confidence_explanation: string;
  evidence_summary: string;
  skills_shown: string[];
  why_it_matters: string;
  interview_talking_point: string;
  open_questions: string[];
};

type SynthesisStatus = {
  presentation_project_directions?: PresentationProjectDirection[];
  frontend_project_directions?: FrontendProjectDirection[];
};

type EvidenceCoverage = {
  coverage_state: string;
  label: string;
  user_message: string;
  can_generate_directions: boolean;
  should_ask_clarification?: boolean;
  should_offer_exploratory_mode?: boolean;
  warnings?: string[];
  direct_count?: number;
  adjacent_count?: number;
  weak_count?: number;
  unique_source_count?: number;
};

type IntelligenceResponse = {
  status: string;
  clarification_required?: boolean;
  clarification_message?: string;
  clarification_options?: string[];
  evidence_route?: string;
  evidence_coverage?: EvidenceCoverage | null;
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
  synthesis_status?: SynthesisStatus;
  directions: Direction[];
};

type SavedWorkspace = {
  goal: string;
  result: IntelligenceResponse;
  selectedDirectionId: string | null;
  activeRoadmapNodeId: string | null;
  completedRoadmapNodeIds: string[];
  guidedStepProofs?: Record<string, string>;
  completedGuidedStepIds?: string[];
  savedAt: string;
};

const SAVED_WORKSPACE_KEY = "solvyn:last-workspace";

function readSavedWorkspace(): SavedWorkspace | null {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    const rawWorkspace = window.localStorage.getItem(SAVED_WORKSPACE_KEY);

    if (!rawWorkspace) {
      return null;
    }

    const workspace = JSON.parse(rawWorkspace) as SavedWorkspace;

    if (!workspace.result || workspace.result.status !== "ready") {
      return null;
    }

    return workspace;
  } catch {
    window.localStorage.removeItem(SAVED_WORKSPACE_KEY);
    return null;
  }
}

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
  return tierVisuals[direction.difficulty] ?? tierVisuals.Medium;
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

function coverageBadgeClass(state?: string) {
  if (state === "strong_direct") {
    return "border-emerald-300/20 bg-emerald-400/10 text-emerald-100";
  }

  if (state === "adequate_direct") {
    return "border-sky-300/20 bg-sky-400/10 text-sky-100";
  }

  if (state === "adjacent_only") {
    return "border-amber-300/20 bg-amber-400/10 text-amber-100";
  }

  if (
    state === "exploratory" ||
    state === "out_of_domain" ||
    state === "query_too_broad"
  ) {
    return "border-rose-300/20 bg-rose-400/10 text-rose-100";
  }

  return "border-white/10 bg-white/[0.04] text-slate-200";
}

function formatSourceType(sourceType: string) {
  const labels: Record<string, string> = {
    github_repository: "GitHub repository",
    project_pattern: "Project pattern",
    research_paper: "Research paper",
  };

  return labels[sourceType] ?? sourceType.replaceAll("_", " ");
}

function getDecisionTracePresentation(
  trace?: DecisionTrace | null,
) {
  if (!trace) {
    return {
      label: "Evidence-informed",
      detail: "This direction is informed by the broader research session.",
      badgeClass: "bg-slate-400/10 text-slate-200",
    };
  }

  if (trace.research_support_scope === "idea_specific") {
    const paperCount = trace.supporting_papers?.length ?? 0;

    return {
      label: "Direct research support",
      detail:
        paperCount > 0
          ? `${paperCount} matching research paper${
              paperCount === 1 ? "" : "s"
            } linked to this direction.`
          : "This direction is linked to a selected research paper.",
      badgeClass: "bg-emerald-400/10 text-emerald-200",
    };
  }

  if (trace.research_support_scope === "mixed") {
    const implementationCount =
      trace.implementation_references?.length ?? 0;

    return {
      label: "Mixed support",
      detail:
        implementationCount > 0
          ? `${implementationCount} implementation reference${
              implementationCount === 1 ? "" : "s"
            } plus broader research-session support.`
          : "A project pattern or implementation signal plus broader research-session support.",
      badgeClass: "bg-sky-400/10 text-sky-200",
    };
  }

  return {
    label: "Planning-domain support",
    detail:
      "This direction is informed by the broader research session, not one specific source.",
    badgeClass: "bg-amber-400/10 text-amber-200",
  };
}

export default function Home() {
  const [savedWorkspace] = useState<SavedWorkspace | null>(() =>
    readSavedWorkspace(),
  );

  const [goal, setGoal] = useState(savedWorkspace?.goal ?? "");
  const [showConstraints, setShowConstraints] = useState(false);
  const [skillLevel, setSkillLevel] = useState("intermediate");
  const [timeAvailable, setTimeAvailable] = useState("3 weeks");
  const [targetRole, setTargetRole] = useState("");
  const [preferredStack, setPreferredStack] = useState("");
  const [result, setResult] = useState<IntelligenceResponse | null>(
    savedWorkspace?.result ?? null,
  );
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [showHelpChooser, setShowHelpChooser] = useState(false);
  const [portfolioSummary, setPortfolioSummary] =
    useState<PortfolioSummary | null>(null);

  const [selectedDirectionId, setSelectedDirectionId] = useState<string | null>(
    savedWorkspace?.selectedDirectionId ?? null,
  );

  const [activeRoadmapNodeId, setActiveRoadmapNodeId] = useState<string | null>(
    savedWorkspace?.activeRoadmapNodeId ?? null,
  );

  const [completedRoadmapNodeIds, setCompletedRoadmapNodeIds] = useState<
    string[]
  >(savedWorkspace?.completedRoadmapNodeIds ?? []);

  const [guidedStepProofs, setGuidedStepProofs] = useState<
    Record<string, string>
  >(savedWorkspace?.guidedStepProofs ?? {});
  const [completedGuidedStepIds, setCompletedGuidedStepIds] = useState<
    string[]
  >(savedWorkspace?.completedGuidedStepIds ?? []);

  const [expandedWhyDirectionId, setExpandedWhyDirectionId] = useState<
    string | null
  >(null);

  const [shouldScrollToClarification, setShouldScrollToClarification] =
    useState(false);

  const [shouldScrollToDirections, setShouldScrollToDirections] =
    useState(false);

  const [shouldScrollToHelpChooser, setShouldScrollToHelpChooser] =
    useState(false);

  useEffect(() => {
    if (!result || result.status !== "ready") {
      return;
    }

    const workspace: SavedWorkspace = {
      goal,
      result,
      selectedDirectionId,
      activeRoadmapNodeId,
      completedRoadmapNodeIds,
      guidedStepProofs,
      completedGuidedStepIds,
      savedAt: new Date().toISOString(),
    };

    window.localStorage.setItem(SAVED_WORKSPACE_KEY, JSON.stringify(workspace));
  }, [
    goal,
    result,
    selectedDirectionId,
    activeRoadmapNodeId,
    completedRoadmapNodeIds,
    guidedStepProofs,
    completedGuidedStepIds,
  ]);

  const clarificationSectionRef = useCallback(
    (node: HTMLElement | null) => {
      if (!node || !shouldScrollToClarification) {
        return;
      }

      window.requestAnimationFrame(() => {
        const targetTop =
          node.getBoundingClientRect().top + window.scrollY - 24;

        window.scrollTo({
          top: targetTop,
          behavior: "smooth",
        });

        window.setTimeout(() => {
          node
            .querySelector<HTMLButtonElement>("button")
            ?.focus({ preventScroll: true });

          setShouldScrollToClarification(false);
        }, 350);
      });
    },
    [shouldScrollToClarification],
  );

  const directionsSectionRef = useCallback(
    (node: HTMLElement | null) => {
      if (!node || !shouldScrollToDirections) {
        return;
      }

      window.requestAnimationFrame(() => {
        const targetTop =
          node.getBoundingClientRect().top + window.scrollY - 24;

        window.scrollTo({
          top: targetTop,
          behavior: "smooth",
        });

        window.setTimeout(() => {
          node
            .querySelector<HTMLButtonElement>("button")
            ?.focus({ preventScroll: true });

          setShouldScrollToDirections(false);
        }, 350);
      });
    },
    [shouldScrollToDirections],
  );

  const helpChooserRef = useCallback(
    (node: HTMLDivElement | null) => {
      if (!node || !shouldScrollToHelpChooser) {
        return;
      }

      window.requestAnimationFrame(() => {
        const targetTop =
          node.getBoundingClientRect().top + window.scrollY - 24;

        window.scrollTo({
          top: targetTop,
          behavior: "smooth",
        });

        window.setTimeout(() => {
          node
            .querySelector<HTMLButtonElement>("button")
            ?.focus({ preventScroll: true });

          setShouldScrollToHelpChooser(false);
        }, 350);
      });
    },
    [shouldScrollToHelpChooser],
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
    setCompletedRoadmapNodeIds([]);
    setGuidedStepProofs({});
    setCompletedGuidedStepIds([]);
    setExpandedWhyDirectionId(null);
    setShouldScrollToClarification(false);
    setShouldScrollToDirections(false);
    setShouldScrollToHelpChooser(false);
    setShowHelpChooser(false);
    setPortfolioSummary(null);
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

      if (payload.status !== "ready") {
        setShouldScrollToClarification(true);
      }

      if (payload.status === "ready" && payload.directions.length > 0) {
        setShouldScrollToDirections(true);
      }

      setResult(payload);
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
      setShouldScrollToHelpChooser(true);
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
    setCompletedRoadmapNodeIds([]);
    setGuidedStepProofs({});
    setCompletedGuidedStepIds([]);
    setPortfolioSummary(null);

    window.setTimeout(() => {
      document
        .getElementById("project-roadmap")
        ?.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
    }, 80);
  }

  const selectedDirectionGuidedSteps =
    selectedDirection?.roadmap.flatMap((node) => node.guided_steps ?? []) ?? [];
  const selectedDirectionGuidedStepKeys =
    selectedDirection?.roadmap.flatMap((node) =>
      (node.guided_steps ?? []).map((step) => `${node.id}:${step.step_id}`),
    ) ?? [];
  const completedSelectedDirectionGuidedStepCount =
    selectedDirectionGuidedStepKeys.filter((stepKey) =>
      completedGuidedStepIds.includes(stepKey),
    ).length;
  const savedProofCount = selectedDirectionGuidedStepKeys.filter(
    (stepKey) => guidedStepProofs[stepKey]?.trim(),
  ).length;
  const isSelectedProjectComplete =
    selectedDirection !== null &&
    selectedDirection.roadmap.length > 0 &&
    selectedDirection.roadmap.every((node) =>
      completedRoadmapNodeIds.includes(node.id),
    );

  function createPortfolioSummary() {
    if (!result || result.status !== "ready" || !selectedDirectionId) {
      return;
    }

    const summary = generatePortfolioSummary({
      goal,
      selectedDirectionId,
      completedRoadmapNodeIds,
      guidedStepProofs,
      completedGuidedStepIds,
      result,
    } satisfies PortfolioWorkspaceLike);

    setPortfolioSummary(summary);
  }

  function completeActiveMission() {
    if (!selectedDirection || !activeRoadmapNodeId) {
      return;
    }

    setCompletedRoadmapNodeIds((current) => {
      if (current.includes(activeRoadmapNodeId)) {
        return current;
      }

      return [...current, activeRoadmapNodeId];
    });

    const activeIndex = selectedDirection.roadmap.findIndex(
      (node) => node.id === activeRoadmapNodeId,
    );
    const nextNode = selectedDirection.roadmap[activeIndex + 1];

    if (nextNode) {
      setActiveRoadmapNodeId(nextNode.id);
    }
  }

  function clearSavedWorkspace() {
    window.localStorage.removeItem(SAVED_WORKSPACE_KEY);
    setGoal("");
    setResult(null);
    setSelectedDirectionId(null);
    setActiveRoadmapNodeId(null);
    setCompletedRoadmapNodeIds([]);
    setGuidedStepProofs({});
    setCompletedGuidedStepIds([]);
    setPortfolioSummary(null);
    setError("");
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
                Solvyn
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
                      onChange={(event) =>
                        setPreferredStack(event.target.value)
                      }
                      placeholder="Python, React, FastAPI"
                      className="mt-2 w-full rounded-xl border border-white/10 bg-slate-900 px-3 py-2.5 text-sm text-slate-200 outline-none placeholder:text-slate-500"
                    />
                  </label>
                </motion.div>
              )}
            </div>

            <div className="flex flex-col gap-3 border-t border-white/10 px-2 pt-3 sm:flex-row sm:items-center sm:justify-between">
              <span className="text-sm text-slate-400">
                Grounded in research, implementation references, and realistic
                scope.
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
          <section
            ref={clarificationSectionRef}
            id="clarification-section"
            tabIndex={-1}
            className="scroll-mt-6 border-t border-white/10 py-12 outline-none"
          >
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
                    Choose a direction and we will build a grounded plan around
                    it.
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
                ref={helpChooserRef}
                id="help-chooser"
                tabIndex={-1}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-5 scroll-mt-6 rounded-3xl border border-sky-300/20 bg-slate-950/45 p-5 outline-none"
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
            <section
              ref={directionsSectionRef}
              id="generated-directions"
              tabIndex={-1}
              className="scroll-mt-6 border-t border-white/10 py-12 outline-none"
            >
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
                    {result.source_counts?.github_repositories ?? 0}{" "}
                    repositories
                  </p>
                </div>
              </div>

              {result.evidence_coverage && (
                <div
                  className={`mt-6 rounded-2xl border p-5 ${coverageBadgeClass(
                    result.evidence_coverage.coverage_state,
                  )}`}
                >
                  <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] opacity-75">
                        Evidence coverage
                      </p>

                      <p className="mt-2 text-lg font-semibold">
                        {result.evidence_coverage.label}
                      </p>

                      <p className="mt-2 max-w-3xl text-sm leading-6 opacity-80">
                        {result.evidence_coverage.user_message}
                      </p>
                    </div>

                    <div className="grid grid-cols-3 gap-2 text-center text-xs">
                      <div className="rounded-xl border border-white/10 bg-slate-950/35 px-3 py-2">
                        <p className="font-semibold">
                          {result.evidence_coverage.direct_count ?? 0}
                        </p>
                        <p className="mt-1 opacity-70">direct</p>
                      </div>

                      <div className="rounded-xl border border-white/10 bg-slate-950/35 px-3 py-2">
                        <p className="font-semibold">
                          {result.evidence_coverage.adjacent_count ?? 0}
                        </p>
                        <p className="mt-1 opacity-70">adjacent</p>
                      </div>

                      <div className="rounded-xl border border-white/10 bg-slate-950/35 px-3 py-2">
                        <p className="font-semibold">
                          {result.evidence_coverage.unique_source_count ?? 0}
                        </p>
                        <p className="mt-1 opacity-70">sources</p>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {result.research_evidence_assessment && (
                <div className="mt-6 rounded-2xl border border-sky-300/15 bg-sky-300/[0.05] p-5">
                  <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-sky-200">
                        Research evidence
                      </p>

                      <p className="mt-2 text-lg font-semibold capitalize text-white">
                        {result.research_evidence_assessment.confidence.level}{" "}
                        support
                      </p>

                      <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">
                        {result.research_evidence_assessment.confidence.reason}
                      </p>
                    </div>

                    <div className="grid grid-cols-3 gap-2 text-center text-xs">
                      <div className="rounded-xl border border-white/10 bg-slate-950/40 px-3 py-2">
                        <p className="font-semibold text-emerald-200">
                          {result.research_evidence_assessment.evidence
                            .alignment_summary?.direct ?? 0}
                        </p>
                        <p className="mt-1 text-slate-400">direct</p>
                      </div>

                      <div className="rounded-xl border border-white/10 bg-slate-950/40 px-3 py-2">
                        <p className="font-semibold text-amber-200">
                          {result.research_evidence_assessment.evidence
                            .alignment_summary?.adjacent ?? 0}
                        </p>
                        <p className="mt-1 text-slate-400">adjacent</p>
                      </div>

                      <div className="rounded-xl border border-white/10 bg-slate-950/40 px-3 py-2">
                        <p className="font-semibold text-slate-200">
                          {result.research_evidence_assessment.evidence
                            .alignment_summary?.weak ?? 0}
                        </p>
                        <p className="mt-1 text-slate-400">weak</p>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              <div className="mt-8 grid gap-5 lg:grid-cols-3">
                {result.directions.map((direction, index) => {
                  const frontendDirection =
                    result.synthesis_status?.frontend_project_directions?.find(
                      (item) => item.id === direction.id,
                    ) ??
                    result.synthesis_status?.frontend_project_directions?.[
                      index
                    ];
                  const visual = getTierVisual(direction);
                  const isSelected = direction.id === selectedDirectionId;
                  const isWhyExpanded =
                    direction.id === expandedWhyDirectionId;
                  const tracePresentation = getDecisionTracePresentation(
                    direction.decision_trace,
                  );

                  return (
                    <motion.div
                      key={direction.id}
                      initial={{ opacity: 0, y: 18 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.35, delay: index * 0.08 }}
                      whileHover={{ y: -8, scale: 1.015 }}
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
                            {frontendDirection?.tier ?? direction.portfolio_tier}
                          </span>

                          <span className="text-xs text-slate-400">
                            {frontendDirection?.estimated_time ?? direction.estimated_effort}
                          </span>
                        </div>

                        <h3 className="mt-5 text-xl font-semibold text-white">
                          {frontendDirection?.title ?? direction.title}
                        </h3>

                        <p className="mt-3 text-sm leading-6 text-slate-300">
                          {frontendDirection?.summary ?? direction.summary}
                        </p>

                        {frontendDirection && (
                          <div className="mt-4 rounded-2xl border border-emerald-300/15 bg-emerald-400/[0.045] p-3">
                            <p className="text-xs font-medium text-emerald-200">
                              {frontendDirection.evidence_badge}
                            </p>

                            <p className="mt-2 text-sm leading-6 text-slate-300">
                              {frontendDirection.confidence_explanation}
                            </p>

                            <div className="mt-3 flex flex-wrap gap-2">
                              {frontendDirection.skills_shown
                                .slice(0, 3)
                                .map((skill) => (
                                  <span
                                    key={skill}
                                    className="rounded-full border border-white/10 bg-white/[0.035] px-2.5 py-1 text-xs text-slate-300"
                                  >
                                    {skill}
                                  </span>
                                ))}
                            </div>
                          </div>
                        )}

                        <div className="mt-5 border-t border-white/10 pt-4">
                          <button
                            type="button"
                            onClick={() =>
                              setExpandedWhyDirectionId((currentId) =>
                                currentId === direction.id
                                  ? null
                                  : direction.id,
                              )
                            }
                            className="flex w-full items-center justify-between rounded-lg px-1 py-1 text-left transition hover:bg-white/[0.04]"
                            aria-expanded={isWhyExpanded}
                          >
                            <span className="text-xs font-medium uppercase tracking-[0.14em] text-slate-400">
                              Why this project?
                            </span>

                            {isWhyExpanded ? (
                              <ChevronUp className="h-4 w-4 text-slate-400" />
                            ) : (
                              <ChevronDown className="h-4 w-4 text-slate-400" />
                            )}
                          </button>

                          <AnimatePresence initial={false}>
                            {isWhyExpanded && (
                              <motion.div
                                initial={{ opacity: 0, height: 0 }}
                                animate={{ opacity: 1, height: "auto" }}
                                exit={{ opacity: 0, height: 0 }}
                                transition={{ duration: 0.22 }}
                                className="overflow-hidden"
                              >
                                <div className="mt-3 rounded-2xl border border-sky-300/15 bg-sky-400/[0.05] p-4">
                                  <p className="text-sm leading-6 text-slate-300">
                                    {frontendDirection?.why_it_matters ?? direction.why_it_fits}
                                  </p>

                                  {frontendDirection?.interview_talking_point && (
                                    <div className="mt-4 rounded-2xl border border-cyan-300/15 bg-cyan-400/[0.045] p-4">
                                      <p className="text-xs font-medium uppercase tracking-[0.12em] text-cyan-200">
                                        Interview angle
                                      </p>

                                      <p className="mt-2 text-sm leading-6 text-slate-300">
                                        {frontendDirection.interview_talking_point}
                                      </p>
                                    </div>
                                  )}

                                  <div className="mt-4 rounded-2xl border border-white/10 bg-slate-950/35 p-4">
                                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                                      <div>
                                        <p className="text-xs font-medium uppercase tracking-[0.12em] text-slate-500">
                                          Research support
                                        </p>

                                        <span
                                          className={`mt-2 inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${tracePresentation.badgeClass}`}
                                        >
                                          {tracePresentation.label}
                                        </span>
                                      </div>

                                      <p className="max-w-xs text-xs leading-5 text-slate-400 sm:text-right">
                                        {tracePresentation.detail}
                                      </p>
                                    </div>

                                    {direction.decision_trace?.primary_inspiration && (
                                      <div className="mt-4 border-t border-white/10 pt-4">
                                        <p className="text-xs font-medium uppercase tracking-[0.12em] text-slate-500">
                                          Primary inspiration
                                        </p>

                                        {direction.decision_trace.primary_inspiration.url ? (
                                          <a
                                            href={
                                              direction.decision_trace
                                                .primary_inspiration.url
                                            }
                                            target="_blank"
                                            rel="noreferrer"
                                            className="mt-2 block text-sm font-medium leading-6 text-sky-200 transition hover:text-sky-100 hover:underline"
                                          >
                                            {
                                              direction.decision_trace
                                                .primary_inspiration.title
                                            }
                                          </a>
                                        ) : (
                                          <p className="mt-2 text-sm font-medium leading-6 text-slate-200">
                                            {
                                              direction.decision_trace
                                                .primary_inspiration.title
                                            }
                                          </p>
                                        )}

                                        <p className="mt-1 text-xs capitalize text-slate-500">
                                          {formatSourceType(
                                            direction.decision_trace
                                              .primary_inspiration.source_type,
                                          )}
                                        </p>
                                      </div>
                                    )}

                                  </div>

                                  <div className="mt-4 border-t border-white/10 pt-4 text-xs">
                                    <p className="font-medium uppercase tracking-[0.12em] text-slate-500">
                                      Scope
                                    </p>

                                    <p className="mt-1 leading-5 text-slate-300">
                                      {direction.scope}
                                    </p>
                                  </div>

                                  {direction.decision_trace?.research_support_scope !==
                                    "idea_specific" &&
                                    result.research_evidence_assessment && (
                                      <p className="mt-3 text-xs leading-5 text-slate-400">
                                        This direction uses broader session-level
                                        research support rather than claiming direct
                                        support from one paper.
                                      </p>
                                    )}
                                </div>
                              </motion.div>
                            )}
                          </AnimatePresence>
                        </div>

                        <div className="mt-5 flex flex-wrap gap-2">
                          {direction.tech_stack
                            .slice(0, 4)
                            .map((technology) => (
                              <span
                                key={technology}
                                className="rounded-full border border-white/10 bg-white/[0.035] px-2.5 py-1 text-xs text-slate-300"
                              >
                                {technology}
                              </span>
                            ))}
                        </div>

                        <div className="mt-5 border-t border-white/10 pt-4">
                          <span className="inline-flex items-center gap-1.5 text-xs text-emerald-200">
                            <ShieldCheck className="h-4 w-4" />
                            Verified {direction.verification.score}/
                            {direction.verification.max_score}
                          </span>

                          <button
                            type="button"
                            onClick={() => chooseDirection(direction)}
                            className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-xl border border-sky-300/25 bg-sky-400/10 px-4 py-3 text-sm font-semibold text-sky-100 transition hover:border-sky-200/50 hover:bg-sky-300/20 hover:text-white"
                          >
                            Open roadmap
                            <ArrowRight className="h-4 w-4" />
                          </button>
                        </div>
                      </div>
                    </motion.div>
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

                        <button
                          type="button"
                          onClick={clearSavedWorkspace}
                          className="mt-4 w-full rounded-xl border border-white/10 px-3 py-2 text-xs font-medium text-slate-300 transition hover:border-rose-300/30 hover:bg-rose-400/10 hover:text-rose-100"
                        >
                          Start over
                        </button>
                      </div>
                    </div>

                    {isSelectedProjectComplete && (
                      <div className="mt-8 rounded-2xl border border-emerald-300/20 bg-emerald-400/[0.06] p-5">
                        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                          <div>
                            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-emerald-200">
                              Project execution complete
                            </p>
                            <h3 className="mt-2 text-xl font-semibold text-white">
                              Your guided build is ready to package.
                            </h3>
                            <p className="mt-2 text-sm leading-6 text-emerald-50/80">
                              Every roadmap mission is complete. Next, Solvyn can turn this
                              into a portfolio summary, interview story, and eventually a
                              shareable Build Passport.
                            </p>
                          </div>

                          <div className="grid min-w-56 gap-2 text-sm text-emerald-50/90">
                            <p>
                              <span className="font-semibold text-white">
                                {completedRoadmapNodeIds.length}
                              </span>{" "}
                              missions completed
                            </p>
                            <p>
                              <span className="font-semibold text-white">
                                {completedSelectedDirectionGuidedStepCount}
                              </span>
                              /{selectedDirectionGuidedSteps.length} guided steps completed
                            </p>
                            <p>
                              <span className="font-semibold text-white">
                                {savedProofCount}
                              </span>{" "}
                              proof entries saved
                            </p>
                          </div>
                        </div>

                        <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                          <button
                            type="button"
                            onClick={createPortfolioSummary}
                            className="rounded-xl border border-emerald-300/15 bg-slate-950/30 px-3 py-3 text-left text-sm font-medium text-emerald-50 transition hover:border-emerald-200/35 hover:bg-emerald-300/10"
                          >
                            Create portfolio summary
                          </button>

                          {[
                            "Generate interview story",
                            "Prepare README outline",
                            "Preview Build Passport",
                          ].map((action) => (
                            <button
                              key={action}
                              type="button"
                              disabled
                              className="cursor-not-allowed rounded-xl border border-white/10 bg-slate-950/20 px-3 py-3 text-left text-sm font-medium text-slate-500"
                            >
                              {action}
                              <span className="mt-1 block text-xs font-normal text-slate-600">
                                Coming soon
                              </span>
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    {portfolioSummary && (
                      <PortfolioSummaryPreview summary={portfolioSummary} />
                    )}

                    <div className="mt-10 grid gap-8 lg:grid-cols-[minmax(0,1.15fr)_minmax(300px,0.85fr)]">
                      <div className="relative">
                        <div className="absolute bottom-8 left-[18px] top-8 w-px bg-gradient-to-b from-sky-300/60 via-indigo-300/40 to-violet-300/30 sm:left-1/2" />

                        <div className="space-y-7">
                          {selectedDirection.roadmap.map((node, index) => {
                            const isActive = node.id === activeRoadmapNodeId;
                            const isCompleted =
                              completedRoadmapNodeIds.includes(node.id);
                            const isRight = index % 2 === 1;
                            const guidedStepCount =
                              node.guided_steps?.length ?? 0;
                            const completedGuidedStepCount = (
                              node.guided_steps ?? []
                            ).filter((step) =>
                              completedGuidedStepIds.includes(
                                `${node.id}:${step.step_id}`,
                              ),
                            ).length;

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
                                      : isCompleted
                                        ? "border-emerald-300/30 bg-emerald-400/10"
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

                                  {guidedStepCount > 0 && (
                                    <p className="mt-3 inline-flex rounded-full border border-emerald-300/15 bg-emerald-400/[0.06] px-2.5 py-1 text-xs font-medium text-emerald-100">
                                      {completedGuidedStepCount}/{guidedStepCount} guided steps
                                    </p>
                                  )}
                                </div>

                                <div className="relative z-10 hidden h-10 w-10 place-items-center sm:grid">
                                  <div
                                    className={`grid h-9 w-9 place-items-center rounded-full border transition ${
                                      isActive
                                        ? "border-sky-200/70 bg-sky-300 text-slate-950 shadow-lg shadow-sky-300/30"
                                        : isCompleted
                                          ? "border-emerald-300/60 bg-emerald-400 text-slate-950"
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
                        completedNodeIds={completedRoadmapNodeIds}
                        guidedStepProofs={guidedStepProofs}
                        completedGuidedStepIds={completedGuidedStepIds}
                        onGuidedStepProofChange={setGuidedStepProofs}
                        onCompletedGuidedStepIdsChange={setCompletedGuidedStepIds}
                        onCompleteActiveMission={completeActiveMission}
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

function PortfolioSummaryPreview({
  summary,
}: {
  summary: PortfolioSummary;
}) {
  const [copiedSection, setCopiedSection] = useState<string | null>(null);
  const resumeParagraph = buildResumeReadyParagraph(summary);

  async function copyText(label: string, text: string) {
    await navigator.clipboard.writeText(text);
    setCopiedSection(label);

    window.setTimeout(() => {
      setCopiedSection(null);
    }, 1600);
  }

  return (
    <div className="mt-6 rounded-2xl border border-sky-300/15 bg-sky-400/[0.04] p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-sky-300">
            Portfolio summary
          </p>
          <h3 className="mt-2 text-xl font-semibold text-white">
            {summary.projectTitle}
          </h3>
          <p className="mt-2 text-sm leading-6 text-slate-300">
            {summary.goal}
          </p>
        </div>

        <div className="rounded-xl border border-white/10 bg-slate-950/35 p-3 text-sm text-slate-300">
          <p>
            {summary.missionsCompleted}/{summary.totalMissions} missions
          </p>
          <p>
            {summary.guidedStepsCompleted}/{summary.totalGuidedSteps} guided steps
          </p>
          <p>{summary.proofEntriesSaved} proof entries</p>

          <button
            type="button"
            onClick={() =>
              void copyText("full-summary", formatPortfolioSummaryText(summary))
            }
            className="mt-3 w-full rounded-lg border border-sky-300/20 bg-sky-400/10 px-3 py-2 text-xs font-semibold text-sky-100 transition hover:border-sky-200/40 hover:bg-sky-300/20"
          >
            {copiedSection === "full-summary" ? "Copied" : "Copy summary"}
          </button>
        </div>
      </div>

      <div className="mt-5 rounded-xl border border-white/[0.06] bg-white/[0.025] p-4">
        <div className="flex items-center justify-between gap-3">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
            Resume-ready paragraph
          </p>

          <button
            type="button"
            onClick={() => void copyText("resume", resumeParagraph)}
            className="rounded-lg border border-white/10 px-2.5 py-1 text-xs font-medium text-slate-300 transition hover:border-sky-300/30 hover:text-sky-100"
          >
            {copiedSection === "resume" ? "Copied" : "Copy"}
          </button>
        </div>

        <p className="mt-3 text-sm leading-6 text-slate-300">
          {resumeParagraph}
        </p>
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-2">
        <SummarySection
          title="Evidence"
          items={[
            summary.evidenceConfidenceLabel,
            summary.evidenceConfidenceDetail,
          ]}
        />

        <SummarySection
          title="Skills demonstrated"
          items={summary.skillsDemonstrated}
        />

        <SummarySection
          title="Technical decisions"
          items={summary.technicalDecisions.map(
            (decision) =>
              `${decision.missionTitle} · ${decision.stepTitle}: ${decision.decisionPoint} Answer: ${decision.proof}`,
          )}
        />

        <SummarySection
          title="Known limitations"
          items={summary.knownLimitations}
          emptyText="No limitations captured yet."
        />

        <SummarySection
          title="Interview takeaways"
          items={summary.interviewTakeaways}
        />

        <SummarySection
          title="Portfolio artifacts"
          items={summary.portfolioArtifacts}
          emptyText="No portfolio artifacts captured yet."
        />
      </div>
    </div>
  );
}

function SummarySection({
  title,
  items,
  emptyText = "Nothing captured yet.",
}: {
  title: string;
  items: string[];
  emptyText?: string;
}) {
  return (
    <div className="rounded-xl border border-white/[0.06] bg-white/[0.025] p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
        {title}
      </p>

      {items.length > 0 ? (
        <ul className="mt-3 space-y-2">
          {items.map((item, index) => (
            <li
              key={`${title}-${index}-${item}`}
              className="text-sm leading-6 text-slate-300"
            >
              {item}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-sm leading-6 text-slate-500">{emptyText}</p>
      )}
    </div>
  );
}


function RoadmapDetailPanel({
  direction,
  activeNodeId,
  completedNodeIds,
  guidedStepProofs,
  completedGuidedStepIds,
  onGuidedStepProofChange,
  onCompletedGuidedStepIdsChange,
  onCompleteActiveMission,
}: {
  direction: Direction;
  activeNodeId: string | null;
  completedNodeIds: string[];
  guidedStepProofs: Record<string, string>;
  completedGuidedStepIds: string[];
  onGuidedStepProofChange: React.Dispatch<
    React.SetStateAction<Record<string, string>>
  >;
  onCompletedGuidedStepIdsChange: React.Dispatch<
    React.SetStateAction<string[]>
  >;
  onCompleteActiveMission: () => void;
}) {
  const activeNode =
    direction.roadmap.find((node) => node.id === activeNodeId) ??
    direction.roadmap[0];

  const [guidedStepCursor, setGuidedStepCursor] = useState({
    nodeId: "",
    stepIndex: 0,
  });
  if (!activeNode) {
    return null;
  }

  const guidedSteps = activeNode.guided_steps ?? [];
  const activeGuidedStepIndex =
    guidedStepCursor.nodeId === activeNode.id ? guidedStepCursor.stepIndex : 0;
  const activeGuidedStep = guidedSteps[activeGuidedStepIndex] ?? null;
  const activeGuidedStepKey = activeGuidedStep
    ? `${activeNode.id}:${activeGuidedStep.step_id}`
    : "";
  const activeGuidedStepProof = activeGuidedStepKey
    ? guidedStepProofs[activeGuidedStepKey] ?? ""
    : "";
  const isActiveGuidedStepComplete =
    activeGuidedStepKey.length > 0 &&
    completedGuidedStepIds.includes(activeGuidedStepKey);
  const activeMissionGuidedStepKeys = guidedSteps.map(
    (step) => `${activeNode.id}:${step.step_id}`,
  );
  const completedActiveMissionGuidedStepCount =
    activeMissionGuidedStepKeys.filter((stepKey) =>
      completedGuidedStepIds.includes(stepKey),
    ).length;
  const allActiveMissionGuidedStepsComplete =
    guidedSteps.length === 0 ||
    completedActiveMissionGuidedStepCount === guidedSteps.length;
  const missionCompletionBlocked =
    guidedSteps.length > 0 && !allActiveMissionGuidedStepsComplete;

  const completedCount = direction.roadmap.filter((node) =>
    completedNodeIds.includes(node.id),
  ).length;
  const isActiveComplete = completedNodeIds.includes(activeNode.id);

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
        <div className="mb-5 rounded-2xl border border-white/[0.06] bg-white/[0.025] p-3">
          <div className="flex items-center justify-between gap-3 text-sm">
            <span className="text-slate-300">
              Mission progress
            </span>
            <span className="font-semibold text-white">
              {completedCount}/{direction.roadmap.length}
            </span>
          </div>

          <div className="mt-3 h-2 overflow-hidden rounded-full bg-white/[0.06]">
            <div
              className="h-full rounded-full bg-sky-300 transition-all"
              style={{
                width: `${
                  direction.roadmap.length > 0
                    ? (completedCount / direction.roadmap.length) * 100
                    : 0
                }%`,
              }}
            />
          </div>
        </div>

        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.14em] text-sky-300">
              Mission
            </p>

            <h3 className="mt-2 text-xl font-semibold text-white">
              {activeNode.title}
            </h3>

            {activeNode.stage_type && (
              <p className="mt-2 inline-flex rounded-full border border-sky-300/20 bg-sky-400/10 px-2.5 py-1 text-xs text-sky-100">
                {activeNode.stage_type.replaceAll("_", " ")}
              </p>
            )}
          </div>

          <Code2 className="h-5 w-5 text-sky-300" />
        </div>

        <p className="mt-3 text-sm leading-6 text-slate-400">
          {activeNode.objective ?? activeNode.purpose}
        </p>

        {activeNode.why_it_matters && (
          <div className="mt-5 rounded-2xl border border-white/[0.06] bg-white/[0.025] p-4">
            <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">
              Why this matters
            </p>

            <p className="mt-2 text-sm leading-6 text-slate-300">
              {activeNode.why_it_matters}
            </p>
          </div>
        )}

        {activeGuidedStep && (
          <GuidedStepCoach
            step={activeGuidedStep}
            stepIndex={activeGuidedStepIndex}
            totalSteps={guidedSteps.length}
            completedStepCount={completedActiveMissionGuidedStepCount}
            proofValue={activeGuidedStepProof}
            isComplete={isActiveGuidedStepComplete}
            isMissionReady={allActiveMissionGuidedStepsComplete}
            onProofChange={(value) =>
              onGuidedStepProofChange((current) => ({
                ...current,
                [activeGuidedStepKey]: value,
              }))
            }
            onCompleteStep={() => {
              if (!activeGuidedStepKey || !activeGuidedStepProof.trim()) {
                return;
              }

              onCompletedGuidedStepIdsChange((current) =>
                current.includes(activeGuidedStepKey)
                  ? current
                  : [...current, activeGuidedStepKey],
              );

              if (activeGuidedStepIndex < guidedSteps.length - 1) {
                setGuidedStepCursor({
                  nodeId: activeNode.id,
                  stepIndex: activeGuidedStepIndex + 1,
                });
              }
            }}
            onPrevious={() =>
              setGuidedStepCursor({
                nodeId: activeNode.id,
                stepIndex: Math.max(activeGuidedStepIndex - 1, 0),
              })
            }
            onNext={() =>
              setGuidedStepCursor({
                nodeId: activeNode.id,
                stepIndex: Math.min(
                  activeGuidedStepIndex + 1,
                  guidedSteps.length - 1,
                ),
              })
            }
          />
        )}

        <MissionListSection
          title="Build this next"
          items={activeNode.tasks}
          numbered
        />

        <MissionListSection
          title="Command block"
          items={activeNode.commands ?? []}
          code
        />

        <MissionListSection
          title="Expected outputs"
          items={activeNode.expected_outputs ?? []}
        />

        <MissionListSection
          title="Acceptance criteria"
          items={activeNode.acceptance_criteria ?? []}
        />

        <MissionListSection
          title="Validation checks"
          items={activeNode.validation_checks ?? []}
        />

        <MissionListSection
          title="Common errors to avoid"
          items={activeNode.common_errors ?? []}
        />

        {(activeNode.portfolio_artifact || activeNode.unlock_condition) && (
          <div className="mt-6 space-y-3 border-t border-white/10 pt-4">
            {activeNode.portfolio_artifact && (
              <p className="flex gap-3 rounded-xl border border-emerald-300/10 bg-emerald-400/5 p-3 text-sm leading-6 text-emerald-100">
                <FileCheck2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-300" />
                <span>
                  <span className="font-semibold">Portfolio artifact: </span>
                  {activeNode.portfolio_artifact}
                </span>
              </p>
            )}

            {activeNode.unlock_condition && (
              <p className="rounded-xl border border-sky-300/10 bg-sky-400/5 p-3 text-sm leading-6 text-sky-100">
                <span className="font-semibold">Unlock condition: </span>
                {activeNode.unlock_condition}
              </p>
            )}
          </div>
        )}

        <div className="mt-6 border-t border-white/10 pt-4">
          <button
            type="button"
            onClick={() => {
              if (missionCompletionBlocked) {
                return;
              }

              onCompleteActiveMission();
            }}
            disabled={isActiveComplete || missionCompletionBlocked}
            className={`inline-flex w-full items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-semibold transition ${
              isActiveComplete
                ? "cursor-not-allowed border border-emerald-300/20 bg-emerald-400/10 text-emerald-100"
                : missionCompletionBlocked
                  ? "cursor-not-allowed border border-amber-300/20 bg-amber-400/10 text-amber-100"
                  : "border border-sky-300/25 bg-sky-400/10 text-sky-100 hover:border-sky-200/50 hover:bg-sky-300/20 hover:text-white"
            }`}
          >
            <CheckCircle2 className="h-4 w-4" />
            {isActiveComplete
              ? "Mission completed"
              : missionCompletionBlocked
                ? "Complete guided steps first"
                : "Mark mission complete"}
          </button>

          {missionCompletionBlocked && (
            <p className="mt-3 rounded-xl border border-amber-300/10 bg-amber-400/[0.04] p-3 text-sm leading-6 text-amber-100">
              Save proof for every guided step before completing this mission.
            </p>
          )}

          <p className="mt-4 inline-flex items-center gap-2 text-sm text-slate-300">
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

function GuidedStepCoach({
  step,
  stepIndex,
  totalSteps,
  completedStepCount,
  proofValue,
  isComplete,
  isMissionReady,
  onProofChange,
  onCompleteStep,
  onPrevious,
  onNext,
}: {
  step: GuidedMissionStep;
  stepIndex: number;
  totalSteps: number;
  completedStepCount: number;
  proofValue: string;
  isComplete: boolean;
  isMissionReady: boolean;
  onProofChange: (value: string) => void;
  onCompleteStep: () => void;
  onPrevious: () => void;
  onNext: () => void;
}) {
  const isFirstStep = stepIndex === 0;
  const isLastStep = stepIndex === totalSteps - 1;
  const proofValidation = validateProof(
    proofValue,
    step.expected_output_patterns ?? [],
  );
  const canCompleteStep =
    proofValidation.status === "accepted" ||
    proofValidation.status === "needs_detail";

  return (
    <div className="mt-6 overflow-hidden rounded-2xl border border-emerald-300/15 bg-emerald-400/[0.035]">
      <div className="border-b border-white/10 bg-slate-950/40 p-4">
        <div className="flex items-center justify-between gap-3">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-emerald-200">
            Guided build step
          </p>

          <span className="rounded-full border border-emerald-300/20 bg-emerald-400/10 px-2.5 py-1 text-xs text-emerald-100">
            Step {stepIndex + 1} of {totalSteps}
          </span>
        </div>

        <p className="mt-2 text-xs text-emerald-100/80">
          {completedStepCount}/{totalSteps} guided steps completed
        </p>

        <div className="mt-3 flex gap-1.5">
          {Array.from({ length: totalSteps }).map((_, index) => (
            <span
              key={`guided-step-dot-${index}`}
              className={`h-1.5 flex-1 rounded-full ${
                index <= stepIndex ? "bg-emerald-300" : "bg-white/10"
              }`}
            />
          ))}
        </div>
      </div>

      <div className="space-y-4 p-4">
        <div>
          <h4 className="text-lg font-semibold text-white">{step.title}</h4>
          <p className="mt-2 text-sm leading-6 text-slate-300">
            {step.explanation}
          </p>
        </div>

        <div className="rounded-xl border border-white/[0.06] bg-white/[0.025] p-3">
          <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">
            Do this
          </p>
          <p className="mt-2 text-sm leading-6 text-slate-200">
            {step.action}
          </p>
        </div>

        {step.starter_command && (
          <div className="rounded-xl border border-sky-300/10 bg-sky-400/[0.04] p-3">
            <p className="text-xs font-medium uppercase tracking-[0.14em] text-sky-300">
              Starter command
            </p>
            <code className="mt-2 block rounded-lg bg-slate-950/80 p-3 font-mono text-xs leading-6 text-sky-100">
              {step.starter_command}
            </code>
          </div>
        )}

        {step.starter_files.length > 0 && (
          <div className="rounded-xl border border-white/[0.06] bg-white/[0.025] p-3">
            <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">
              Starter files
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              {step.starter_files.map((file) => (
                <span
                  key={file}
                  className="rounded-lg border border-white/10 bg-slate-950/50 px-2.5 py-1 font-mono text-xs text-slate-200"
                >
                  {file}
                </span>
              ))}
            </div>
          </div>
        )}

        <div className="grid gap-3">
          <div className="rounded-xl border border-emerald-300/10 bg-emerald-400/[0.04] p-3">
            <p className="text-xs font-medium uppercase tracking-[0.14em] text-emerald-300">
              Done when
            </p>
            <p className="mt-2 text-sm leading-6 text-emerald-50">
              {step.done_when}
            </p>
          </div>

          <div className="rounded-xl border border-amber-300/10 bg-amber-400/[0.04] p-3">
            <p className="text-xs font-medium uppercase tracking-[0.14em] text-amber-200">
              Common confusion
            </p>
            <p className="mt-2 text-sm leading-6 text-amber-50/90">
              {step.common_confusion}
            </p>
          </div>
        </div>

        {step.decision_point && (
          <div className="rounded-xl border border-violet-300/10 bg-violet-400/[0.04] p-3">
            <p className="text-xs font-medium uppercase tracking-[0.14em] text-violet-200">
              Decision point
            </p>
            <p className="mt-2 text-sm leading-6 text-violet-50/90">
              {step.decision_point}
            </p>
          </div>
        )}

        <div className="rounded-xl border border-white/[0.06] bg-slate-950/40 p-3">
          <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">
            Proof prompt
          </p>
          <p className="mt-2 text-sm leading-6 text-slate-200">
            {step.proof_prompt}
          </p>

          {step.expected_output_patterns.length > 0 && (
            <div className="mt-4 rounded-xl border border-emerald-300/10 bg-emerald-400/[0.035] p-3">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-200">
                Proof should include
              </p>
              <p className="mt-2 text-xs leading-5 text-slate-400">
                These signals help Solvyn confirm that your proof belongs to this exact
                step instead of being a generic completion note.
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                {step.expected_output_patterns.map((pattern) => (
                  <span
                    key={pattern}
                    className="rounded-full border border-emerald-300/15 bg-emerald-400/10 px-2.5 py-1 text-xs text-emerald-100"
                  >
                    {pattern}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="rounded-xl border border-white/[0.06] bg-white/[0.025] p-3">
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">
              Your proof
            </p>

            {isComplete && (
              <span className="rounded-full border border-emerald-300/20 bg-emerald-400/10 px-2.5 py-1 text-xs font-medium text-emerald-100">
                Step proof saved
              </span>
            )}
          </div>

          <textarea
            value={proofValue}
            onChange={(event) => onProofChange(event.target.value)}
            placeholder="Paste the command output, file list, explanation, or result that proves you completed this step."
            rows={5}
            className="mt-3 w-full resize-none rounded-xl border border-white/10 bg-slate-950/70 p-3 text-sm leading-6 text-slate-100 outline-none transition placeholder:text-slate-600 focus:border-emerald-300/40 focus:bg-slate-950"
          />

          <p
            className={`mt-2 rounded-lg border px-3 py-2 text-xs leading-5 ${
              proofValidation.status === "accepted"
                ? "border-emerald-300/20 bg-emerald-400/10 text-emerald-100"
                : proofValidation.status === "missing_expected_pattern"
                  ? "border-amber-300/20 bg-amber-400/10 text-amber-100"
                  : "border-white/10 bg-slate-950/40 text-slate-400"
            }`}
          >
            {proofValidation.feedback}
          </p>

          <button
            type="button"
            onClick={onCompleteStep}
            disabled={!canCompleteStep || isComplete}
            className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-xl border border-emerald-300/20 bg-emerald-400/10 px-3 py-2 text-sm font-semibold text-emerald-100 transition hover:border-emerald-200/40 hover:bg-emerald-300/20 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <CheckCircle2 className="h-4 w-4" />
            {isComplete
              ? "Step completed"
              : proofValidation.status === "missing_expected_pattern"
                ? "Add missing proof details"
                : proofValidation.status === "empty"
                  ? "Paste proof to continue"
                  : isLastStep
                    ? "Save proof and unlock mission"
                    : "Save proof and continue"}
          </button>
        </div>

        <div className="rounded-xl border border-sky-300/10 bg-sky-400/[0.04] p-3">
          <p className="text-xs font-medium uppercase tracking-[0.14em] text-sky-300">
            Interview takeaway
          </p>
          <p className="mt-2 text-sm leading-6 text-sky-50">
            {step.interview_takeaway}
          </p>
        </div>

        {isMissionReady && (
          <div className="rounded-xl border border-emerald-300/20 bg-emerald-400/[0.06] p-3">
            <p className="text-sm font-semibold text-emerald-100">
              Mission ready to complete
            </p>
            <p className="mt-1 text-sm leading-6 text-emerald-50/80">
              All guided proof is saved. You can now mark this mission complete.
            </p>
          </div>
        )}

        <div className="flex gap-3 border-t border-white/10 pt-4">
          <button
            type="button"
            onClick={onPrevious}
            disabled={isFirstStep}
            className="flex-1 rounded-xl border border-white/10 px-3 py-2 text-sm font-medium text-slate-300 transition hover:border-white/25 hover:bg-white/[0.04] disabled:cursor-not-allowed disabled:opacity-40"
          >
            Previous step
          </button>

          <button
            type="button"
            onClick={onNext}
            disabled={isLastStep}
            className="flex-1 rounded-xl border border-emerald-300/20 bg-emerald-400/10 px-3 py-2 text-sm font-semibold text-emerald-100 transition hover:border-emerald-200/40 hover:bg-emerald-300/20 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Next step
          </button>
        </div>
      </div>
    </div>
  );
}


function MissionListSection({
  title,
  items,
  numbered = false,
  code = false,
}: {
  title: string;
  items: string[];
  numbered?: boolean;
  code?: boolean;
}) {
  if (items.length === 0) {
    return null;
  }

  return (
    <div className="mt-6">
      <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">
        {title}
      </p>

      <ul className="mt-3 space-y-3">
        {items.map((item, index) => (
          <li
            key={`${title}-${item}-${index}`}
            className={`flex gap-3 rounded-xl border border-white/[0.06] bg-white/[0.025] p-3 text-sm leading-6 text-slate-300 ${
              code ? "font-mono text-xs text-sky-100" : ""
            }`}
          >
            <span className="grid h-6 w-6 shrink-0 place-items-center rounded-lg bg-sky-300/10 text-xs font-semibold text-sky-200">
              {numbered ? index + 1 : "✓"}
            </span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
