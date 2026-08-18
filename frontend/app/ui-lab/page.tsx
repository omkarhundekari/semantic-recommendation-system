import Link from "next/link";

import {
  ArrowRight,
  Orbit,
  Sparkles,
} from "lucide-react";

import SolvynBackdrop from "@/components/experience/SolvynBackdrop";
import {
  SignalPill,
  SolvynMark,
} from "@/components/experience/SolvynPrimitives";


export default function ExperienceLab() {
  return (
    <main className="solvyn-experience min-h-screen overflow-hidden text-slate-100">
      <SolvynBackdrop />

      <div className="relative z-10 mx-auto flex min-h-screen max-w-[1480px] flex-col px-5 sm:px-8 lg:px-12">
        <nav className="solvyn-nav">
          <SolvynMark />

          <div className="flex items-center gap-3">
            <span className="hidden text-xs text-slate-500 md:inline">
              Experience Lab
            </span>

            <Link
              href="/ui-lab/login"
              className="solvyn-button-secondary"
            >
              Sign in
            </Link>
          </div>
        </nav>

        <section className="flex flex-1 items-center py-16 lg:py-24">
          <div className="grid w-full items-center gap-16 lg:grid-cols-[1.08fr_0.92fr]">
            <div className="max-w-4xl">
              <SignalPill tone="sky">
                Evidence-backed project intelligence
              </SignalPill>

              <h1
                aria-label="Build with conviction."
                className="mt-7 text-[clamp(3.8rem,8vw,8rem)] font-semibold leading-[0.88] tracking-[-0.07em] text-white"
              >
                Build with
                <span className="solvyn-text-spectrum block">
                  conviction.
                </span>
              </h1>

              <p className="mt-8 max-w-2xl text-base leading-8 text-slate-400 sm:text-lg">
                Tell Solvyn what you want to build. We help you turn
                the idea into a grounded path, guide the work, and
                preserve the proof of what you actually accomplished.
              </p>

              <div className="mt-10 flex flex-wrap items-center gap-3">
                <Link
                  href="/ui-lab/login"
                  className="solvyn-button-primary"
                >
                  Start building
                  <ArrowRight className="h-4 w-4" />
                </Link>

                <Link
                  href="/ui-lab/login"
                  className="solvyn-button-secondary"
                >
                  I already have an account
                </Link>
              </div>

              <div className="mt-12 flex flex-wrap gap-x-7 gap-y-3 text-xs text-slate-600">
                <span>Research-aware</span>
                <span>Execution-aware</span>
                <span>Evidence-preserving</span>
              </div>
            </div>

            <div className="relative hidden min-h-[540px] lg:block">
              <div className="absolute inset-0 grid place-items-center">
                <div className="relative h-[430px] w-[430px]">
                  <div className="absolute inset-[10%] rounded-full border border-sky-300/[0.09]" />
                  <div className="absolute inset-[24%] rounded-full border border-violet-300/[0.08]" />
                  <div className="absolute inset-[38%] rounded-full border border-emerald-300/[0.08]" />

                  <div className="absolute inset-0 animate-[spin_34s_linear_infinite] motion-reduce:animate-none rounded-full border border-white/[0.035]">
                    <span className="absolute left-1/2 top-0 h-2 w-2 -translate-x-1/2 rounded-full bg-sky-200 shadow-[0_0_24px_rgba(125,211,252,0.9)]" />
                  </div>

                  <div className="absolute inset-[17%] animate-[spin_24s_linear_infinite_reverse] motion-reduce:animate-none rounded-full border border-white/[0.035]">
                    <span className="absolute right-0 top-1/2 h-1.5 w-1.5 -translate-y-1/2 rounded-full bg-violet-200 shadow-[0_0_20px_rgba(196,181,253,0.8)]" />
                  </div>

                  <div className="absolute inset-[35%] grid place-items-center rounded-full border border-sky-200/10 bg-slate-950/55 shadow-[0_0_80px_rgba(56,189,248,0.08)] backdrop-blur-xl">
                    <div className="text-center">
                      <div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl border border-sky-300/15 bg-sky-300/[0.06]">
                        <Orbit className="h-6 w-6 text-sky-200" />
                      </div>

                      <p className="mt-4 text-xs tracking-[0.18em] text-slate-500">
                        SOLVYN
                      </p>

                      <p className="mt-2 text-sm font-medium text-white">
                        Your work has a trajectory
                      </p>
                    </div>
                  </div>

                  <Sparkles className="absolute left-[8%] top-[28%] h-4 w-4 text-sky-200/40" />
                  <Sparkles className="absolute bottom-[18%] right-[2%] h-3 w-3 text-violet-200/30" />
                  <Sparkles className="absolute right-[18%] top-[7%] h-3 w-3 text-emerald-200/30" />
                </div>
              </div>
            </div>
          </div>
        </section>

        <footer className="flex items-center justify-between border-t border-white/[0.05] py-6 text-xs text-slate-700">
          <span>Solvyn Experience Foundation</span>
          <span>Simple first. Powerful when needed.</span>
        </footer>
      </div>
    </main>
  );
}
