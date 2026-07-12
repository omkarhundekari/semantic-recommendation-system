import type { PortfolioSummary } from "@/lib/portfolioSummary";

export type PassportStatus = {
  label: string;
  passed: boolean;
};

export type BuildPassport = {
  title: string;
  goal: string;
  domain: string | null;
  evidence: string;
  executionSummary: string;
  statuses: PassportStatus[];
  skills: string[];
  proofDigest: string[];
  adaptationAudit: string[];
  artifacts: string[];
  shareableSummary: string;
  markdown: string;
};

export function buildPassport(summary: PortfolioSummary): BuildPassport {
  const statuses: PassportStatus[] = [
    {
      label: "Evidence-backed",
      passed: summary.completionState.evidenceBacked,
    },
    {
      label: "Fully executed",
      passed: summary.completionState.fullyExecuted,
    },
    {
      label: "Portfolio-ready",
      passed: summary.completionState.portfolioReady,
    },
    {
      label: "Interview-prepped",
      passed: summary.completionState.interviewPrepped,
    },
    {
      label: "Accepted adaptations evidenced",
      passed:
        summary.adaptationAudit.acceptedMissingEvidenceCount === 0,
    },
  ];

  const proofDigest =
    summary.proofEntries.length > 0
      ? summary.proofEntries.slice(0, 6).map((entry) => entry.proof)
      : ["No proof entries saved yet."];

  const artifacts =
    summary.portfolioArtifacts.length > 0
      ? summary.portfolioArtifacts
      : ["Portfolio summary", "Interview story", "README outline"];

  const adaptationAudit = [
    ...summary.adaptationAudit.implemented.map(
      (entry) =>
        `Implemented: ${entry.title} — Evidence: ${entry.evidence}`,
    ),
    ...summary.adaptationAudit.acceptedMissingEvidence.map(
      (entry) =>
        `Accepted but missing evidence: ${entry.title}`,
    ),
    ...summary.adaptationAudit.deferred.map(
      (entry) =>
        `Deferred: ${entry.title}${
          entry.rationale ? ` — ${entry.rationale}` : ""
        }`,
    ),
    ...summary.adaptationAudit.rejected.map(
      (entry) =>
        `Rejected: ${entry.title}${
          entry.rationale ? ` — ${entry.rationale}` : ""
        }`,
    ),
  ];

  const executionSummary = `${summary.missionsCompleted}/${summary.totalMissions} missions completed, ${summary.guidedStepsCompleted}/${summary.totalGuidedSteps} guided steps completed, ${summary.proofEntriesSaved} proof entries saved, and ${summary.adaptationAudit.implementedCount}/${summary.adaptationAudit.totalDecided} decided roadmap adaptations implemented with evidence.`;

  const adaptationPhrase =
    summary.adaptationAudit.implementedCount > 0
      ? ` It also includes ${summary.adaptationAudit.implementedCount} implemented decision-driven roadmap adjustment${
          summary.adaptationAudit.implementedCount === 1 ? "" : "s"
        } with saved evidence.`
      : "";

  const shareableSummary = `${summary.projectTitle} is a ${summary.evidenceConfidenceLabel.toLowerCase()} project built for: ${summary.goal}. It completed ${summary.missionsCompleted}/${summary.totalMissions} missions with ${summary.proofEntriesSaved} saved proof entries and demonstrates ${formatInlineList(summary.skillsDemonstrated.slice(0, 3))}.${adaptationPhrase}`;

  const passport: BuildPassport = {
    title: summary.projectTitle,
    goal: summary.goal,
    domain: summary.domain,
    evidence: `${summary.evidenceConfidenceLabel}: ${summary.evidenceConfidenceDetail}`,
    executionSummary,
    statuses,
    skills: summary.skillsDemonstrated,
    proofDigest,
    adaptationAudit,
    artifacts,
    shareableSummary,
    markdown: "",
  };

  return {
    ...passport,
    markdown: formatBuildPassportMarkdown(passport),
  };
}

export function formatBuildPassportMarkdown(passport: BuildPassport): string {
  return [
    `# Build Passport: ${passport.title}`,
    "",
    `Goal: ${passport.goal}`,
    passport.domain ? `Domain: ${passport.domain}` : null,
    "",
    "## Status",
    "",
    ...passport.statuses.map((status) =>
      `- ${status.passed ? "✅" : "◻️"} ${status.label}`,
    ),
    "",
    "## Evidence",
    "",
    passport.evidence,
    "",
    "## Execution",
    "",
    passport.executionSummary,
    "",
    "## Skills Demonstrated",
    "",
    ...formatBullets(passport.skills),
    "",
    "## Proof Digest",
    "",
    ...formatBullets(passport.proofDigest),
    "",
    "## Roadmap Adaptation Audit",
    "",
    ...formatBullets(
      passport.adaptationAudit.length > 0
        ? passport.adaptationAudit
        : ["No roadmap adaptation decisions captured yet."],
    ),
    "",
    "## Portfolio Artifacts",
    "",
    ...formatBullets(passport.artifacts),
    "",
    "## Shareable Summary",
    "",
    passport.shareableSummary,
  ]
    .filter((line): line is string => line !== null)
    .join("\n");
}

function formatBullets(items: string[]): string[] {
  return items.length > 0
    ? items.map((item) => `- ${item}`)
    : ["- No items available yet."];
}

function formatInlineList(items: string[]): string {
  if (items.length === 0) {
    return "project execution, validation, and technical communication";
  }

  if (items.length === 1) {
    return items[0];
  }

  return `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;
}
