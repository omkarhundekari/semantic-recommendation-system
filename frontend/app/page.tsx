"use client";

import { motion } from "framer-motion";
import {
  AlertCircle,
  ArrowRight,
  ChevronDown,
  ChevronUp,
  Clock3,
  LoaderCircle,
  ShieldCheck,
  Sparkles,
  Target,
} from "lucide-react";
import { FormEvent, useState } from "react";

type Verification = {
  status: string;
  score: number;
  max_score: number;
  warnings: string[];
};

type Direction = {
  id: string;
  title: string;
  summary: string;
  scope: string;
  estimated_effort: string;
  career_signal: string;
  why_it_fits: string;
  mvp_steps: string[];
  tech_stack: string[];
  repairs_applied: string[];
  verification: Verification;
};

type IntelligenceResponse = {
  status: string;
  clarification_message?: string;
  evidence_route?: string;
  source_counts?: {
    research_papers: number;
    project_patterns: number;
    github_repositories: number;
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

  async function generateDirections(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (goal.trim().length < 3) {
      setError("Describe the kind of project you want to build first.");
      return;
    }

    setError("");
    setResult(null);
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
            goal: goal.trim(),
            constraints: {
              skill_level: skillLevel,
              time_available: timeAvailable,
              target_roles: targetRole ? [targetRole] : [],
              preferred_stack: preferredStack ? [preferredStack] : [],
            },
          }),
        },
      );

      const payload = (await response.json()) as IntelligenceResponse;

      if (!response.ok) {
        throw new Error("The planning API returned an unexpected response.");
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

  return (
    <main className="min-h-screen overflow-hidden bg-[#07111f] text-slate-100">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_50%_12%,rgba(56,189,248,0.16),transparent_34%),radial-gradient(circle_at_88%_78%,rgba(129,140,248,0.1),transparent_28%)]" />

      <section className="relative mx-auto max-w-5xl px-6 py-7 lg:px-10">
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
          className="mx-auto flex w-full max-w-3xl flex-col justify-center py-16"
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
            Describe your goal. We will turn technical evidence into three
            realistic project directions, each with scope, roadmap, and
            portfolio value.
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

        {result && (
          <section className="border-t border-white/10 py-12">
            <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
              <div>
                <p className="text-sm font-medium text-sky-200">
                  Generated project directions
                </p>
                <h2 className="mt-2 text-3xl font-semibold text-white">
                  Your evidence-backed options
                </h2>
              </div>

              <p className="text-sm text-slate-400">
                Route: {result.evidence_route ?? "unknown"} ·{" "}
                {result.source_counts?.research_papers ?? 0} research ·{" "}
                {result.source_counts?.project_patterns ?? 0} patterns ·{" "}
                {result.source_counts?.github_repositories ?? 0} repositories
              </p>
            </div>

            {result.status !== "ready" ? (
              <div className="mt-7 rounded-3xl border border-amber-300/20 bg-amber-400/10 p-6 text-amber-100">
                {result.clarification_message ??
                  "Add more detail about your topic, role, or timeline."}
              </div>
            ) : (
              <div className="mt-8 grid gap-5 lg:grid-cols-3">
                {result.directions.map((direction, index) => (
                  <motion.article
                    key={direction.id}
                    initial={{ opacity: 0, y: 16 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.35, delay: index * 0.08 }}
                    className="rounded-3xl border border-white/10 bg-slate-950/45 p-5 backdrop-blur-xl"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <span className="rounded-full bg-sky-400/10 px-3 py-1 text-xs font-medium text-sky-200">
                        {direction.scope}
                      </span>
                      <span className="text-xs text-slate-400">
                        {direction.estimated_effort}
                      </span>
                    </div>

                    <h3 className="mt-4 text-xl font-semibold text-white">
                      {direction.title}
                    </h3>

                    <p className="mt-3 text-sm leading-6 text-slate-300">
                      {direction.summary}
                    </p>

                    <p className="mt-4 text-sm leading-6 text-slate-400">
                      {direction.why_it_fits}
                    </p>

                    <div className="mt-5 border-t border-white/10 pt-4">
                      <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">
                        MVP focus
                      </p>

                      <ul className="mt-3 space-y-2">
                        {direction.mvp_steps.slice(0, 4).map((step) => (
                          <li
                            key={step}
                            className="flex gap-2 text-sm leading-6 text-slate-300"
                          >
                            <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-sky-300" />
                            {step}
                          </li>
                        ))}
                      </ul>
                    </div>

                    <div className="mt-5 flex flex-wrap gap-2">
                      {direction.tech_stack.slice(0, 5).map((technology) => (
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

                      <span className="text-slate-400">
                        {direction.career_signal} signal
                      </span>
                    </div>

                    {direction.repairs_applied.length > 0 && (
                      <p className="mt-3 text-xs leading-5 text-amber-200">
                        Scoped adjustment: {direction.repairs_applied[0]}
                      </p>
                    )}
                  </motion.article>
                ))}
              </div>
            )}
          </section>
        )}
      </section>
    </main>
  );
}