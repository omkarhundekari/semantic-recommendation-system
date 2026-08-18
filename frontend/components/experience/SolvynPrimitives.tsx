import type {
  HTMLAttributes,
  ReactNode,
} from "react";

import {
  Sparkles,
} from "lucide-react";

export function SolvynMark({
  compact = false,
}: {
  compact?: boolean;
}) {
  return (
    <div className="flex items-center gap-3">
      <div className="solvyn-mark">
        <span className="solvyn-mark-orbit" />
        <Sparkles className="relative z-10 h-4 w-4 text-sky-100" />
      </div>

      {!compact && (
        <div>
          <p className="text-sm font-semibold tracking-[0.02em] text-white">
            Solvyn
          </p>

          <p className="text-[11px] tracking-[0.08em] text-slate-500">
            INTELLIGENCE ENGINE
          </p>
        </div>
      )}
    </div>
  );
}


type GlassSurfaceProps =
  HTMLAttributes<HTMLDivElement> & {
    children: ReactNode;
  };


export function GlassSurface({
  children,
  className = "",
  ...props
}: GlassSurfaceProps) {
  return (
    <div
      {...props}
      className={`solvyn-glass ${className}`}
    >
      {children}
    </div>
  );
}


export function SignalPill({
  children,
  tone = "sky",
}: {
  children: ReactNode;
  tone?: "sky" | "emerald" | "amber" | "violet";
}) {
  return (
    <span
      className={`solvyn-signal solvyn-signal-${tone}`}
    >
      <span className="solvyn-signal-dot" />
      {children}
    </span>
  );
}


export function Eyebrow({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <p className="solvyn-eyebrow">
      {children}
    </p>
  );
}
