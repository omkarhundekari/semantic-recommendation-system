import type { PortfolioSummary } from "@/lib/portfolioSummary";

export type ReadmeSection = {
  title: string;
  body: string;
};

export type ReadmeOutline = {
  title: string;
  markdown: string;
  sections: ReadmeSection[];
};

export function buildReadmeOutline(summary: PortfolioSummary): ReadmeOutline {
  const topSkills =
    summary.skillsDemonstrated.slice(0, 5).join(", ") ||
    "project execution, validation, and technical communication";

  const limitations =
    summary.knownLimitations.length > 0
      ? summary.knownLimitations
      : [
          "Add more automated tests.",
          "Improve deployment and demo instructions.",
          "Expand validation with more edge cases.",
        ];

  const artifacts =
    summary.portfolioArtifacts.length > 0
      ? summary.portfolioArtifacts
      : ["Portfolio summary", "Interview explanation", "Saved proof entries"];

  const proofPoints =
    summary.proofEntries.length > 0
      ? summary.proofEntries.slice(0, 5).map((entry) => entry.proof)
      : ["Proof entries will appear here after guided build steps are completed."];

  const sections: ReadmeSection[] = [
    {
      title: "Overview",
      body: `${summary.projectTitle} is a project built for the goal: ${summary.goal}. It was developed through a guided execution process where each stage required proof, validation, and a portfolio-ready artifact.`,
    },
    {
      title: "Problem Statement",
      body: `The project focuses on turning a technical idea into a measurable implementation. Instead of stopping at a concept or demo, it defines clear inputs, outputs, validation signals, and limitations.`,
    },
    {
      title: "Core Features",
      body: formatBullets([
        "Guided project execution through scoped roadmap missions",
        "Saved proof for completed implementation steps",
        "Validation-aware project packaging",
        "Portfolio-ready summary generation",
        "Interview-ready explanation generation",
      ]),
    },
    {
      title: "Skills Demonstrated",
      body: topSkills,
    },
    {
      title: "Validation Approach",
      body: `${summary.evidenceConfidenceDetail} The project includes ${summary.proofEntriesSaved} saved proof entries across ${summary.guidedStepsCompleted}/${summary.totalGuidedSteps} guided steps.`,
    },
    {
      title: "Proof Points",
      body: formatBullets(proofPoints),
    },
    {
      title: "Portfolio Artifacts",
      body: formatBullets(artifacts),
    },
    {
      title: "Known Limitations",
      body: formatBullets(limitations),
    },
    {
      title: "Future Improvements",
      body: formatBullets([
        "Add stronger automated validation checks.",
        "Improve deployment and reproducibility instructions.",
        "Add more realistic datasets, examples, or edge cases.",
        "Polish the user-facing demo and documentation.",
      ]),
    },
    {
      title: "Interview Explanation",
      body: `I built this project to show ${topSkills}. The main focus was not only implementation, but also proving that the work was scoped, validated, and explainable as an engineering project.`,
    },
  ];

  return {
    title: summary.projectTitle,
    sections,
    markdown: formatReadmeMarkdown(summary.projectTitle, sections),
  };
}

export function formatReadmeMarkdown(
  title: string,
  sections: ReadmeSection[],
): string {
  return [`# ${title}`, "", ...sections.flatMap((section) => [
    `## ${section.title}`,
    "",
    section.body,
    "",
  ])].join("\n");
}

function formatBullets(items: string[]): string {
  return items.map((item) => `- ${item}`).join("\n");
}
