"use client";

import Link from "next/link";
import {
  useState,
} from "react";

import {
  ArrowLeft,
  ArrowRight,
  ChevronRight,
  Compass,
  Layers3,
  Sparkles,
} from "lucide-react";

import SolvynBackdrop from "@/components/experience/SolvynBackdrop";
import {
  GlassSurface,
  SignalPill,
  SolvynMark,
} from "@/components/experience/SolvynPrimitives";


const EXAMPLE_GOALS = [
  "Build an AI project for an ML engineer role",
  "Create a backend system that proves distributed-systems skills",
  "Turn a research idea into a portfolio-ready prototype",
];


export default function MissionStartPage() {
  const [goal, setGoal] = useState("");

  return (
    <main className="solvyn-experience min-h-screen overflow-hidden text-slate-100">
      <SolvynBackdrop />

      <div className="relative z-10 mx-auto flex min-h-screen max-w-[1480px] flex-col px-5 sm:px-8 lg:px-12">
        <nav className="solvyn-nav">
          <SolvynMark />

          <Link
            href="/ui-lab"
            className="inline-flex items-center gap-2 text-sm text-slate-500 transition hover:text-white"
          >
            <ArrowLeft className="h-4 w-4" />
            Home
          </Link>
        </nav>

        <section className="flex flex-1 items-center py-12 lg:py-20">
          <div className="mx-auto w-full max-w-4xl">
            <div className="text-center">
              <SignalPill tone="sky">
                New mission
              </SignalPill>

              <h1 className="mt-7 text-4xl font-semibold tracking-[-0.055em] text-white sm:text-6xl">
                What do you want to build?
              </h1>

              <p className="mx-auto mt-5 max-w-2xl text-base leading-7 text-slate-500">
                Start with the outcome. Solvyn will help uncover
                the technical direction only when you need it.
              </p>
            </div>

            <GlassSurface className="mt-10 p-3 sm:p-4">
              <textarea
                value={goal}
                onChange={(event) =>
                  setGoal(event.target.value)
                }
                placeholder="Describe the thing you want to build, learn, prove, or explore..."
                className="min-h-44 w-full resize-none bg-transparent px-4 py-4 text-base leading-8 text-white outline-none placeholder:text-slate-700 sm:text-lg"
              />

              <div className="flex flex-col gap-3 border-t border-white/[0.06] px-2 pt-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-center gap-2 text-xs text-slate-600">
                  <Compass className="h-3.5 w-3.5" />
                  Details come later, only when useful.
                </div>

                <Link
                  href={
                    goal.trim()
                      ? `/ui-lab/mission/workspace?goal=${encodeURIComponent(goal.trim())}`
                      : "/ui-lab/mission/workspace"
                  }
                  className="solvyn-button-primary"
                >
                  Shape my trajectory
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </div>
            </GlassSurface>

            <div className="mt-8">
              <p className="text-center text-xs uppercase tracking-[0.16em] text-slate-700">
                Or start from an example
              </p>

              <div className="mt-4 grid gap-3 md:grid-cols-3">
                {EXAMPLE_GOALS.map((example) => (
                  <button
                    key={example}
                    type="button"
                    onClick={() => setGoal(example)}
                    className="group rounded-2xl border border-white/[0.055] bg-white/[0.018] p-4 text-left transition hover:border-sky-300/[0.14] hover:bg-sky-300/[0.025]"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <Layers3 className="mt-0.5 h-4 w-4 shrink-0 text-slate-700 transition group-hover:text-sky-300" />
                      <ChevronRight className="h-4 w-4 shrink-0 text-slate-800 transition group-hover:translate-x-0.5 group-hover:text-sky-300" />
                    </div>

                    <p className="mt-6 text-sm leading-6 text-slate-500 transition group-hover:text-slate-300">
                      {example}
                    </p>
                  </button>
                ))}
              </div>
            </div>

            <div className="mt-10 flex justify-center">
              <div className="inline-flex items-center gap-2 text-xs text-slate-700">
                <Sparkles className="h-3.5 w-3.5" />
                No dashboards. No configuration wall. Start with intent.
              </div>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
