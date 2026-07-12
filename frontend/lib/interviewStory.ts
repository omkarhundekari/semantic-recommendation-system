import type { PortfolioSummary } from "@/lib/portfolioSummary";

export type InterviewStory = {
  title: string;
  openingAnswer: string;
  problem: string;
  approach: string;
  implementation: string;
  validation: string;
  tradeoff: string;
  improvement: string;
  proofPoints: string[];
  conciseVersion: string;
};

export function buildInterviewStory(summary: PortfolioSummary): InterviewStory {
  const primarySkill = summary.skillsDemonstrated[0] ?? "full-stack engineering";
  const secondarySkill =
    summary.skillsDemonstrated[1] ?? "validation-driven development";
  const firstProof = summary.proofEntries[0]?.proof;
  const firstDecision = summary.technicalDecisions[0];

  const validationSignal =
    summary.knownLimitations.find((item) =>
      item.toLowerCase().includes("validation"),
    ) ?? summary.evidenceConfidenceDetail;

  const problem = `I built ${summary.projectTitle} to solve the problem behind this goal: ${summary.goal}. The focus was not just making a demo, but turning the idea into a measurable project with clear inputs, outputs, validation signals, and portfolio-ready proof.`;

  const approach = `My approach was to break the project into guided engineering missions instead of jumping straight into random implementation. I started by defining the scope, then built the smallest working workflow, validated it, extended it carefully, and finally packaged the work so it could be explained in an interview.`;

  const implementation = firstProof
    ? `For implementation, I used saved proof from the build process. One concrete proof point was: ${firstProof}`
    : `For implementation, I focused on building the core workflow first and saving evidence at each stage so the project could be reviewed later.`;

  const validation = `I validated the project with explicit completion proof and evidence confidence. The project reached ${summary.evidenceConfidenceLabel}, and the validation story was: ${validationSignal}`;

  const tradeoff = firstDecision
    ? `One tradeoff I made was during ${firstDecision.missionTitle}. The decision point was: ${firstDecision.decisionPoint} My answer was: ${firstDecision.proof}`
    : `One tradeoff was keeping the first version focused. Instead of adding too many features early, I prioritized a working, testable MVP that could be improved safely.`;

  const improvement =
    summary.knownLimitations[0] ??
    "The next improvement would be to add stronger automated validation, more edge-case testing, and a more polished deployment or demo workflow.";

  const openingAnswer = [
    problem,
    approach,
    `Technically, this demonstrates ${primarySkill}, ${secondarySkill}, and the ability to connect implementation decisions with validation.`,
    validation,
    tradeoff,
    `If I continued this project, I would improve it by addressing this limitation: ${improvement}`,
  ].join(" ");

  const conciseVersion = `I built ${summary.projectTitle} as a validation-driven project for: ${summary.goal}. I broke it into scoped missions, implemented the MVP workflow, saved proof at each step, validated the output, and packaged the result into a portfolio-ready artifact. The strongest skills demonstrated were ${summary.skillsDemonstrated
    .slice(0, 3)
    .join(", ") || "project execution, validation, and technical communication"}.`;

  return {
    title: summary.projectTitle,
    openingAnswer,
    problem,
    approach,
    implementation,
    validation,
    tradeoff,
    improvement,
    proofPoints: summary.proofEntries.slice(0, 5).map((entry) => entry.proof),
    conciseVersion,
  };
}

export function formatInterviewStoryText(story: InterviewStory): string {
  return [
    `Interview Story: ${story.title}`,
    "",
    "60-90 second answer:",
    story.openingAnswer,
    "",
    "Concise version:",
    story.conciseVersion,
    "",
    "Problem:",
    story.problem,
    "",
    "Approach:",
    story.approach,
    "",
    "Implementation:",
    story.implementation,
    "",
    "Validation:",
    story.validation,
    "",
    "Tradeoff:",
    story.tradeoff,
    "",
    "Improvement:",
    story.improvement,
    "",
    "Proof points:",
    ...formatListOrFallback(story.proofPoints, "No proof points saved yet.").map(
      (item) => `- ${item}`,
    ),
  ].join("\n");
}

function formatListOrFallback(items: string[], fallback: string): string[] {
  return items.length > 0 ? items : [fallback];
}
