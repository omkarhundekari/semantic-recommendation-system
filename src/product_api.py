from typing import Dict, List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from feasibility_scorer import score_project_feasibility
from project_idea_generator import generate_project_ideas
from plan_verifier import verify_project_ideas
from query_expander import get_query_metadata
from schemas.product_models import (
    EvidenceReference,
    PipelineStep,
    ProjectDirection,
    ProjectIntelligenceRequest,
    ProjectIntelligenceResponse,
    RoadmapStage,
    VerificationResult,
)
from source_router import retrieve_evidence


app = FastAPI(
    title="Research-to-Prototype Intelligence API",
    description=(
        "Evidence-grounded project planning API that converts user goals into "
        "buildable project directions and structured execution roadmaps."
    ),
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def build_roadmap(idea: Dict) -> List[RoadmapStage]:
    mvp_steps = idea.get("mvp_scope", [])
    advanced_extensions = idea.get("advanced_extensions", [])

    return [
        RoadmapStage(
            id="define",
            title="Define the problem",
            purpose="Turn the recommendation into a narrow, measurable problem.",
            tasks=[
                idea.get("evidence_buildable_gap")
                or "Write a one-sentence problem statement and define one success metric.",
                "Choose a constrained input source and a realistic first user.",
            ],
        ),
        RoadmapStage(
            id="mvp",
            title="Build the MVP",
            purpose="Implement the smallest complete version of the idea.",
            tasks=mvp_steps[:6],
        ),
        RoadmapStage(
            id="validate",
            title="Validate the result",
            purpose="Demonstrate that the prototype works and document limitations.",
            tasks=[
                "Create representative test inputs and expected outputs.",
                "Measure one quality, accuracy, reliability, or user-value metric.",
                "Document known limitations and failure cases.",
            ],
        ),
        RoadmapStage(
            id="extend",
            title="Add one advanced extension",
            purpose="Increase technical depth only after the MVP is stable.",
            tasks=advanced_extensions[:3],
        ),
        RoadmapStage(
            id="package",
            title="Package for portfolio",
            purpose="Make the project easy for recruiters and interviewers to understand.",
            tasks=[
                "Add an architecture diagram and setup instructions to the README.",
                "Record a short demo and include realistic screenshots or GIFs.",
                "Write one resume bullet explaining the technical impact and system design.",
            ],
        ),
    ]


def build_evidence(idea: Dict) -> List[EvidenceReference]:
    title = idea.get("evidence_title")
    if not title:
        return []

    return [
        EvidenceReference(
            title=title,
            source_type=idea.get("evidence_source_type", "unknown"),
            category=idea.get("research_category"),
            url=idea.get("evidence_url") or idea.get("url"),
        )
    ]


def build_risks(idea: Dict) -> List[str]:
    scope = (
        idea.get("feasibility_analysis", {})
        .get("build_profile", {})
        .get("scope", "Moderate")
    )

    risks = [
        "Keep the first version constrained to a small, reproducible input set.",
        "Validate outputs before making claims about real-world usefulness.",
    ]

    if scope == "Ambitious":
        risks.insert(
            0,
            "Reduce scope by implementing one analysis path before adding integrations or advanced automation.",
        )

    return risks


@app.get("/health")
def health() -> Dict:
    return {
        "status": "healthy",
        "service": "research-to-prototype-intelligence-api",
        "version": "2.0.0",
    }


@app.post(
    "/v1/project-intelligence",
    response_model=ProjectIntelligenceResponse,
)
def generate_project_intelligence(
    request: ProjectIntelligenceRequest,
) -> ProjectIntelligenceResponse:
    query = request.goal.strip()
    metadata = get_query_metadata(query)
    corrected_query = metadata.get("corrected_query", query)

    base_pipeline = [
        PipelineStep(
            name="query_understanding",
            status="completed",
            detail="Parsed query intent and supported technical domain.",
        ),
    ]

    if metadata.get("query_requires_confirmation"):
        return ProjectIntelligenceResponse(
            status="needs_correction_confirmation",
            query=query,
            corrected_query=corrected_query,
            goal_summary=query,
            detected_domain=metadata.get("detected_domain"),
            detected_intent=metadata.get("detected_intent"),
            clarification_message=f"Did you mean: {corrected_query}?",
            pipeline=base_pipeline,
        )

    if metadata.get("detected_domain") == "general":
        return ProjectIntelligenceResponse(
            status="needs_clarification",
            query=query,
            corrected_query=corrected_query,
            goal_summary=query,
            detected_domain="general",
            detected_intent=metadata.get("detected_intent"),
            clarification_message=(
                "I could not confidently identify a supported technical topic yet. "
                "Add a domain, desired role, time limit, or preferred technology."
            ),
            suggested_topics=[
                "AI project for an ML engineer role in 3 weeks",
                "React portfolio project for frontend roles",
                "Cloud cost optimization project",
                "Cybersecurity automation project",
                "Healthcare AI project with Python",
            ],
            pipeline=base_pipeline,
        )

    evidence_payload = retrieve_evidence(corrected_query, top_k=6)
    evidence_items = evidence_payload["merged_results"]

    base_pipeline.extend(
        [
            PipelineStep(
                name="evidence_retrieval",
                status="completed",
                detail=f"Retrieved {len(evidence_items)} evidence items.",
            ),
            PipelineStep(
                name="project_planning_baseline",
                status="completed",
                detail=(
                    "Generated deterministic directions and applied target-role, "
                    "timeline, skill-level, and preferred-stack constraints. "
                    "This node will later be upgraded to LLM synthesis."
                ),
            ),
        ]
    )

    ideas = generate_project_ideas(
        evidence_items,
        corrected_query,
        max_ideas=3,
        constraints=request.constraints.model_dump(),
    )

    verification_results = verify_project_ideas(
        ideas,
        request.constraints.model_dump(),
    )

    base_pipeline.append(
        PipelineStep(
            name="plan_verification",
            status="completed",
            detail=(
                "Checked role alignment, preferred stack, timeline, evidence, "
                "specific MVP language, and direction diversity."
            ),
        )
    )

    directions = []
    for index, idea in enumerate(ideas, start=1):
        verification = verification_results[index - 1]
        feasibility = score_project_feasibility(idea)
        idea["feasibility_analysis"] = feasibility
        profile = feasibility.get("build_profile", {})

        directions.append(
            ProjectDirection(
                id=f"direction-{index}",
                title=idea.get("project_title", f"Project Direction {index}"),
                summary=idea.get("idea_angle", ""),
                scope=profile.get("scope", "Unknown"),
                estimated_effort=profile.get("estimated_effort", "Unknown"),
                career_signal=feasibility.get("skill_signal", "Unknown"),
                why_it_fits=" ".join(
                    part
                    for part in [
                        idea.get("constraint_summary", ""),
                        idea.get("evidence_focus_statement")
                        or idea.get("research_motivation")
                        or "Grounded in the selected technical evidence.",
                    ]
                    if part
                ),
                mvp_steps=idea.get("mvp_scope", []),
                advanced_extensions=idea.get("advanced_extensions", []),
                tech_stack=idea.get("suggested_tech_stack", []),
                target_roles=idea.get("target_roles", []),
                evidence=build_evidence(idea),
                roadmap=build_roadmap(idea),
                risks=build_risks(idea),
                verification=VerificationResult(**verification),
            )
        )

    base_pipeline.append(
        PipelineStep(
            name="response_validation",
            status="completed",
            detail=(
                f"Serialized {len(directions)} project directions with "
                "structured verification results."
            ),
        )
    )

    return ProjectIntelligenceResponse(
        status="ready",
        query=query,
        corrected_query=corrected_query,
        goal_summary=query,
        detected_domain=evidence_payload.get("detected_domain"),
        detected_intent=evidence_payload.get("detected_intent"),
        evidence_route=evidence_payload.get("selected_route"),
        source_counts={
            "research_papers": len(evidence_payload.get("research_results", [])),
            "project_patterns": len(evidence_payload.get("project_results", [])),
            "github_repositories": len(evidence_payload.get("github_results", [])),
        },
        directions=directions,
        pipeline=base_pipeline,
    )
