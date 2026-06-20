"use client";

import { motion } from "framer-motion";
import {
  ArrowRight,
  CheckCircle2,
  Clock3,
  Code2,
  Sparkles,
  Target,
} from "lucide-react";
import { useState } from "react";

const examplePrompts = [
  "AI project for an ML engineer role in 3 weeks",
  "React portfolio project for frontend roles",
  "Cloud cost optimization project with Python",
];

const signals = [
  {
    icon: Target,
    label: "Evidence-grounded",
    detail: "Research, project patterns, and implementation references.",
  },
  {
    icon: Clock3,
    label: "Scope-aware",
    detail: "Plans adapt to your timeline and current skill level.",
  },
  {
    icon: Code2,
    label: "Portfolio-ready",
    detail: "Roadmaps include build, validate, and package stages.",
  },
];

export default function Home() {
  const [goal, setGoal] = useState("");

  return (
    <main className="min-h-screen overflow-hidden bg-[#07111f] text-slate-100">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_18%_16%,rgba(56,189,248,0.16),transparent_28%),radial-gradient(circle_at_83%_8%,rgba(129,140,248,0.17),transparent_25%),radial-gradient(circle_at_55%_92%,rgba(16,185,129,0.1),transparent_30%)]" />

      <section className="relative mx-auto flex min-h-screen max-w-7xl flex-col px-6 py-7 lg:px-10">
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

          <span className="rounded-full border border-emerald-300/20 bg-emerald-400/10 px-3 py-1.5 text-xs font-medium text-emerald-200">
            Evidence-first planning
          </span>
        </nav>

        <div className="flex flex-1 items-center py-16 lg:py-20">
          <div className="grid w-full gap-14 lg:grid-cols-[1.1fr_0.9fr] lg:items-center">
            <motion.div
              initial={{ opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.55 }}
            >
              <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-sky-300/20 bg-slate-950/30 px-3 py-1.5 text-sm text-sky-100 backdrop-blur">
                <span className="h-2 w-2 rounded-full bg-sky-300" />
                Turn evidence into a project worth building
              </div>

              <h1 className="max-w-3xl text-5xl font-semibold tracking-[-0.045em] text-white sm:text-6xl lg:text-7xl">
                Build your next{" "}
                <span className="bg-gradient-to-r from-sky-300 via-cyan-200 to-indigo-300 bg-clip-text text-transparent">
                  standout project.
                </span>
              </h1>

              <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-300">
                Describe your goal, skills, timeline, and target role. Get three
                evidence-backed project directions with an execution roadmap,
                realistic scope, and portfolio packaging guidance.
              </p>

              <div className="mt-9 rounded-3xl border border-white/10 bg-slate-950/45 p-3 shadow-2xl shadow-sky-950/30 backdrop-blur-xl">
                <textarea
                  value={goal}
                  onChange={(event) => setGoal(event.target.value)}
                  placeholder="I want an AI project for an ML engineer role. I know Python and basic React, have 3 weeks, and want something impressive but realistic."
                  className="min-h-32 w-full resize-none bg-transparent px-4 py-3 text-base leading-7 text-white outline-none placeholder:text-slate-500"
                />

                <div className="flex flex-col gap-3 border-t border-white/10 px-2 pt-3 sm:flex-row sm:items-center sm:justify-between">
                  <span className="text-sm text-slate-400">
                    Evidence-aware suggestions. No vague project lists.
                  </span>

                  <button
                    className="inline-flex items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-sky-400 to-indigo-400 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:scale-[1.02] hover:brightness-110"
                    type="button"
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
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 22 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.12 }}
              className="relative"
            >
              <div className="absolute -inset-6 rounded-[2.5rem] bg-sky-400/10 blur-3xl" />

              <div className="relative rounded-[2rem] border border-white/10 bg-slate-950/50 p-5 shadow-2xl shadow-black/30 backdrop-blur-xl sm:p-7">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-slate-400">
                      Example outcome
                    </p>
                    <h2 className="mt-1 text-xl font-semibold text-white">
                      ML Prediction Monitoring Platform
                    </h2>
                  </div>

                  <span className="rounded-full bg-amber-300/10 px-3 py-1 text-xs font-medium text-amber-200">
                    8–12 days
                  </span>
                </div>

                <p className="mt-4 leading-7 text-slate-300">
                  Track prediction quality, feature drift, alert states, and
                  model behavior over time using reproducible monitoring runs.
                </p>

                <div className="mt-6 space-y-3">
                  {[
                    "Define a constrained prediction-monitoring workflow",
                    "Build an MVP with model runs and drift signals",
                    "Validate with synthetic production-style batches",
                    "Package architecture, demo, and resume signal",
                  ].map((step, index) => (
                    <div
                      key={step}
                      className="flex items-center gap-3 rounded-2xl border border-white/8 bg-white/[0.025] p-3"
                    >
                      <div className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-sky-400/10 text-xs font-semibold text-sky-200">
                        {index + 1}
                      </div>
                      <span className="text-sm text-slate-200">{step}</span>
                      <CheckCircle2 className="ml-auto h-4 w-4 text-emerald-300/80" />
                    </div>
                  ))}
                </div>

                <div className="mt-6 grid grid-cols-3 gap-3 border-t border-white/10 pt-5">
                  <div>
                    <p className="text-xs text-slate-500">Role fit</p>
                    <p className="mt-1 text-sm font-medium text-white">ML Engineer</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Evidence</p>
                    <p className="mt-1 text-sm font-medium text-white">3 sources</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Scope</p>
                    <p className="mt-1 text-sm font-medium text-white">Ambitious</p>
                  </div>
                </div>
              </div>
            </motion.div>
          </div>
        </div>

        <div className="grid gap-4 border-t border-white/10 pt-7 md:grid-cols-3">
          {signals.map(({ icon: Icon, label, detail }) => (
            <div
              key={label}
              className="rounded-2xl border border-white/8 bg-white/[0.025] p-4"
            >
              <Icon className="h-5 w-5 text-sky-300" />
              <p className="mt-3 font-medium text-white">{label}</p>
              <p className="mt-1 text-sm leading-6 text-slate-400">{detail}</p>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
