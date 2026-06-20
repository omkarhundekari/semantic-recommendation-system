"use client";

import { motion } from "framer-motion";
import {
  ArrowRight,
  ChevronDown,
  ChevronUp,
  Clock3,
  Sparkles,
  Target,
} from "lucide-react";
import { useState } from "react";

const examplePrompts = [
  "AI project for an ML engineer role in 3 weeks",
  "React portfolio project for frontend roles",
  "Cloud cost optimization project with Python",
];

export default function Home() {
  const [goal, setGoal] = useState("");
  const [showConstraints, setShowConstraints] = useState(false);
  const [skillLevel, setSkillLevel] = useState("intermediate");
  const [timeAvailable, setTimeAvailable] = useState("3 weeks");
  const [targetRole, setTargetRole] = useState("");
  const [preferredStack, setPreferredStack] = useState("");

  return (
    <main className="min-h-screen overflow-hidden bg-[#07111f] text-slate-100">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_50%_12%,rgba(56,189,248,0.16),transparent_34%),radial-gradient(circle_at_88%_78%,rgba(129,140,248,0.1),transparent_28%)]" />

      <section className="relative mx-auto flex min-h-screen max-w-5xl flex-col px-6 py-7 lg:px-10">
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
          className="mx-auto flex w-full max-w-3xl flex-1 flex-col justify-center py-16"
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

          <div className="mt-10 rounded-[1.75rem] border border-white/10 bg-slate-950/45 p-3 shadow-2xl shadow-sky-950/30 backdrop-blur-xl">
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
                type="button"
                className="inline-flex items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-sky-400 to-indigo-400 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:scale-[1.02] hover:brightness-110"
              >
                Generate directions
                <ArrowRight className="h-4 w-4" />
              </button>
            </div>
          </div>

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
      </section>
    </main>
  );
}