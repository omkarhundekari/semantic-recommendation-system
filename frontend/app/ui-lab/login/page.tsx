import Link from "next/link";

import {
  ArrowLeft,
  ArrowRight,
  GitBranch,
  Mail,
} from "lucide-react";

import SolvynBackdrop from "@/components/experience/SolvynBackdrop";
import {
  GlassSurface,
  SolvynMark,
} from "@/components/experience/SolvynPrimitives";


export default function LoginLabPage() {
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
            Back
          </Link>
        </nav>

        <div className="grid flex-1 place-items-center py-12">
          <GlassSurface className="w-full max-w-md p-6 sm:p-8">
            <div className="mb-8">
              <p className="solvyn-eyebrow">
                YOUR SOLVYN
              </p>

              <h1 className="mt-3 text-3xl font-semibold tracking-[-0.045em] text-white">
                Enter Solvyn.
              </h1>

              <p className="mt-3 text-sm leading-6 text-slate-500">
                Sign in to start building or continue where you
                left off.
              </p>
            </div>

            <div className="grid gap-3">
              <button
                type="button"
                className="flex w-full items-center justify-center gap-3 rounded-2xl border border-white/[0.08] bg-white/[0.035] px-4 py-3 text-sm font-medium text-slate-200 transition hover:border-white/[0.14] hover:bg-white/[0.06]"
              >
                <GitBranch className="h-4 w-4" />
                Continue with GitHub
              </button>

              <button
                type="button"
                className="flex w-full items-center justify-center gap-3 rounded-2xl border border-white/[0.08] bg-white/[0.035] px-4 py-3 text-sm font-medium text-slate-200 transition hover:border-white/[0.14] hover:bg-white/[0.06]"
              >
                <Mail className="h-4 w-4" />
                Continue with email
              </button>
            </div>

            <div className="my-7 flex items-center gap-4">
              <div className="h-px flex-1 bg-white/[0.06]" />
              <span className="text-[11px] uppercase tracking-[0.18em] text-slate-700">
                Experience prototype
              </span>
              <div className="h-px flex-1 bg-white/[0.06]" />
            </div>

            <Link
              href="/ui-lab/mission"
              className="solvyn-button-primary flex w-full justify-center"
            >
              Enter prototype
              <ArrowRight className="h-4 w-4" />
            </Link>

            <p className="mt-6 text-center text-xs leading-5 text-slate-700">
              Authentication is intentionally visual-only in this lab.
              Production identity remains unchanged.
            </p>
          </GlassSurface>
        </div>
      </div>
    </main>
  );
}
