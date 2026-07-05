import argparse
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from planning.candidate_models import (
    CandidateDirection,
    CandidateGenerationRequest,
)
from planning.candidate_prompt import (
    CANDIDATE_GENERATION_PROMPT_VERSION,
    build_candidate_generation_payload,
)
from planning.cross_encoder_goal_adapter import (
    CrossEncoderGoalPairScorer,
)
from planning.cross_encoder_goal_relevance import (
    CrossEncoderGoalRelevanceScorer,
)
from planning.evidence_support import (
    CandidateEvidenceSupportScorer,
)
from planning.candidate_validator import validate_candidate
from planning.promotion_eligibility import (
    assess_promotion_eligibility,
)
from planning.candidate_feasibility_prescreen import (
    prescreen_candidate_feasibility,
)
from planning.candidate_source_relevance import (
    assess_candidate_set_source_relevance,
)
from planning.semantic_diversification_repair import (
    build_semantic_diversification_repair_plan,
)
from planning.semantic_goal_adapter import SemanticEngineTextEncoder
from planning.semantic_goal_relevance import GoalRelevanceScorer
from planning.semantic_candidate_diversity import (
    CandidateDiversityPair,
    CandidateDiversityTrace,
    SemanticCandidateDiversityScorer,
)
from reranker import CrossEncoderReranker
from semantic_engine import SemanticEngine
from planning.mock_generation_provider import (
    MockCandidateGenerationProvider,
)
from planning.generation_provider import CandidateGenerationProvider
from planning.live_llm_guard import require_live_openai_access
from planning.openai_generation_provider import (
    OpenAICandidateGenerationProvider,
)
from planning.shadow_runner import (
    build_generation_request,
    run_shadow_plan,
)
from planning.shadow_quality_warnings import (
    assess_shadow_quality_warnings,
)
from planning.shadow_comparison_enrichment import (
    build_shadow_comparison_enrichment,
)
from planning.manual_review_rubric import (
    build_manual_review_template,
)
from planning.evidence_brief import build_evidence_brief
from planning.evidence_quality_signals import (
    EvidenceQualityThresholds,
    assess_evidence_quality_signals,
    build_evidence_quality_metrics,
)
from planning.evidence_curation import curate_evidence
from planning.grounding_adequacy import assess_grounding_adequacy
from project_idea_generator import generate_project_ideas
from source_router import retrieve_evidence
from query_understanding import understand_query


DEFAULT_OUTPUT_DIR = Path("outputs/shadow_comparisons")


def _query_slug(query: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")
    return slug[:60] or "shadow-comparison"


def _build_generation_metadata(
    provider: Optional[CandidateGenerationProvider],
    execution_mode: str,
    prompt_content_hash: Optional[str] = None,
) -> Dict[str, Any]:
    usage = getattr(provider, "last_usage", {}) if provider else {}

    return {
        "prompt_version": CANDIDATE_GENERATION_PROMPT_VERSION,
        "prompt_content_hash": prompt_content_hash,
        "execution_mode": execution_mode,
        "provider_name": (
            provider.__class__.__name__ if provider is not None else None
        ),
        "model": getattr(provider, "model", None) if provider else None,
        "usage": {
            "input_tokens": usage.get("input_tokens"),
            "output_tokens": usage.get("output_tokens"),
            "total_tokens": usage.get("total_tokens"),
        },
    }


def _legacy_summary(ideas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "title": idea.get("project_title", ""),
            "evidence_title": idea.get("evidence_title", ""),
            "evidence_source_type": idea.get(
                "evidence_source_type",
                "",
            ),
            "detected_domain": idea.get("detected_domain", ""),
        }
        for idea in ideas
    ]


def build_shadow_comparison_artifact(
    evidence_payload: Dict[str, Any],
    user_goal: str,
    constraints: Dict[str, Any],
    fixture_response: Optional[Dict[str, Any]] = None,
    provider: Optional[CandidateGenerationProvider] = None,
    execution_mode: str = "fixture",
    semantic_goal_relevance: Optional[List[Dict[str, Any]]] = None,
    semantic_goal_scorer: Optional[Any] = None,
    semantic_candidate_diversity_scorer: Optional[Any] = None,
    cross_encoder_goal_scorer: Optional[Any] = None,
    evidence_support_scorer: Optional[Any] = None,
    comparison_encoder: Optional[Any] = None,
    fixture_id: Optional[str] = None,
    cross_encoder_top_k: int = 3,
    cross_encoder_margin_threshold: float = 0.05,
) -> Dict[str, Any]:
    inference = evidence_payload.get("inference", {})
    evidence_items = evidence_payload.get("merged_results", [])
    cross_encoder_goal_relevance: List[Dict[str, Any]] = []
    semantic_candidate_diversity: Optional[Dict[str, Any]] = None
    evidence_support: List[Dict[str, Any]] = []
    grounding_adequacy: List[Dict[str, Any]] = []
    candidate_source_relevance: List[Dict[str, Any]] = []

    legacy_ideas = generate_project_ideas(
        search_results=evidence_items,
        user_query=user_goal,
        max_ideas=3,
        constraints=constraints,
        detected_domain=inference.get("inferred_focus"),
    )

    curation = curate_evidence(
        evidence_items=evidence_items,
        user_query=user_goal,
    )
    curated_items = [
        {
            **entry.item,
            "support_scope": entry.support_scope,
            "retention_reason": entry.retention_reason,
        }
        for entry in curation.retained
    ]

    brief = build_evidence_brief(
        evidence_items=curated_items,
        user_query=user_goal,
    )
    generation_request = build_generation_request(
        user_goal=user_goal,
        constraints=constraints,
    )

    evidence_quality_metrics = build_evidence_quality_metrics(
        curation=curation,
        brief=brief,
    )
    evidence_quality_signals = assess_evidence_quality_signals(
        metrics=evidence_quality_metrics,
        thresholds=EvidenceQualityThresholds(),
    )

    v2_shadow: Dict[str, Any] = {
        "status": "prompt_ready",
        "evidence_curation": curation.to_dict(),
        "evidence_brief": brief.to_dict(),
        "evidence_quality": {
            "status": "not_routed_pending_calibration",
            **evidence_quality_signals.to_dict(),
        },
        "candidate_generation_payload": (
            build_candidate_generation_payload(
                brief=brief,
                request=generation_request,
            )
        ),
        "selected_candidates": [],
        "generation_metadata": _build_generation_metadata(
            provider=None,
            execution_mode=execution_mode,
        ),
        "diagnostics": {
            "provider_called": False,
            "message": (
                "No provider fixture was supplied. The artifact contains "
                "the exact evidence-grounded payload that a real provider "
                "must answer."
            ),
        },
    }

    if fixture_response is not None and provider is None:
        provider = MockCandidateGenerationProvider(
            response=fixture_response
        )

    if provider is not None:
        report = run_shadow_plan(
            evidence_items=evidence_items,
            user_goal=user_goal,
            constraints=constraints,
            provider=provider,
            legacy_ideas=legacy_ideas,
            max_candidates=3,
        )

        v2_shadow = {
            "status": f"{execution_mode}_evaluated",
            "report": report.to_dict(),
            "evidence_quality": {
                "status": "not_routed_pending_calibration",
                **evidence_quality_signals.to_dict(),
            },
            "selected_candidates": report.selected_candidates,
            "generation_metadata": _build_generation_metadata(
                provider=provider,
                execution_mode=execution_mode,
                prompt_content_hash=report.prompt_content_hash,
            ),
            "diagnostics": report.planning_diagnostics,
            "shadow_readiness": report.shadow_readiness,
        }

        selected_direction_models = [
            CandidateDirection(
                **{
                    key: value
                    for key, value in candidate.items()
                    if key != "ranking"
                }
            )
            for candidate in report.selected_candidates
        ]
        candidate_source_relevance = [
            trace.to_dict()
            for trace in assess_candidate_set_source_relevance(
                candidates=selected_direction_models,
                brief=brief,
                user_goal=user_goal,
            )
        ]

        if semantic_goal_scorer is not None:
            semantic_goal_relevance = (
                build_semantic_goal_relevance_shadow(
                    selected_candidates=report.selected_candidates,
                    generation_request=generation_request,
                    scorer=semantic_goal_scorer,
                )
            )

        if semantic_candidate_diversity_scorer is not None:
            semantic_candidate_diversity = (
                build_semantic_candidate_diversity_shadow(
                    selected_candidates=report.selected_candidates,
                    scorer=semantic_candidate_diversity_scorer,
                )
            )

        if (
            semantic_goal_scorer is not None
            and cross_encoder_goal_scorer is not None
        ):
            cross_encoder_goal_relevance = (
                build_cross_encoder_goal_relevance_shadow(
                    selected_candidates=report.selected_candidates,
                    generation_request=generation_request,
                    embedding_scorer=semantic_goal_scorer,
                    cross_encoder_scorer=cross_encoder_goal_scorer,
                    top_k=cross_encoder_top_k,
                    margin_threshold=cross_encoder_margin_threshold,
                )
            )

        if evidence_support_scorer is not None:
            candidate_assessments = (
                build_selected_candidate_evidence_assessments(
                    selected_candidates=report.selected_candidates,
                    brief=brief,
                    scorer=evidence_support_scorer,
                )
            )
            evidence_support = [
                assessment.to_dict()
                for _, assessment in candidate_assessments
            ]
            grounding_adequacy = [
                assess_grounding_adequacy(
                    candidate=candidate,
                    brief=brief,
                    assessment=assessment,
                ).to_dict()
                for candidate, assessment in candidate_assessments
            ]

    quality_warnings = assess_shadow_quality_warnings(
        coverage_warnings=brief.coverage_warnings,
        semantic_goal_relevance=semantic_goal_relevance or [],
        grounding_adequacy=grounding_adequacy,
        semantic_candidate_diversity=semantic_candidate_diversity,
    )

    promotion_eligibility = build_promotion_eligibility_shadow(
        selected_candidates=v2_shadow.get("selected_candidates", []),
        brief=brief,
        generation_request=generation_request,
        detected_domain=inference.get("inferred_focus") or "general",
        evidence_support_scorer=evidence_support_scorer,
        quality_warnings=quality_warnings,
        semantic_candidate_diversity=semantic_candidate_diversity,
    )

    diversification_repair = build_semantic_diversification_repair_plan(
        selected_candidates=v2_shadow.get("selected_candidates", []),
        semantic_candidate_diversity=(
            semantic_candidate_diversity or {}
        ),
    )

    enrichment_comparison = build_shadow_comparison_enrichment(
        user_goal=user_goal,
        constraints=constraints,
        detected_domain=inference.get("inferred_focus") or "general",
        brief=brief,
        legacy_ideas=legacy_ideas,
        selected_candidates=v2_shadow.get("selected_candidates", []),
        grounding_adequacy=grounding_adequacy,
        promotion_eligibility=promotion_eligibility,
        generation_metadata=v2_shadow.get("generation_metadata", {}),
        comparison_encoder=comparison_encoder,
    )

    manual_review_template = None

    if v2_shadow.get("selected_candidates"):
        manual_review_template = build_manual_review_template(
            enrichment_comparison["comparison"]
        ).to_dict()

    generated_at_utc = datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    )
    artifact_identity = {
        "artifact_id": uuid.uuid4().hex,
        "generation_timestamp_utc": generated_at_utc,
    }

    if fixture_id:
        artifact_identity["fixture_id"] = fixture_id

    return {
        "schema_version": "1.1",
        "artifact_identity": artifact_identity,
        "generated_at_utc": generated_at_utc,
        "query": user_goal,
        "constraints": constraints,
        "retrieval": {
            "selected_route": evidence_payload.get("selected_route"),
            "expanded_query": evidence_payload.get("expanded_query"),
            "focused_query": evidence_payload.get("focused_query"),
            "inference": inference,
            "merged_evidence_count": len(evidence_items),
        },
        "legacy_planner": {
            "direction_count": len(legacy_ideas),
            "directions": _legacy_summary(legacy_ideas),
            "raw_ideas": enrichment_comparison["legacy_raw_ideas"],
            "enrichment": enrichment_comparison["legacy_enrichment"],
        },
        "v2_shadow": {
            **v2_shadow,
            "semantic_goal_relevance": list(
                semantic_goal_relevance or []
            ),
            "cross_encoder_goal_relevance": (
                cross_encoder_goal_relevance
            ),
            "semantic_candidate_diversity": (
                semantic_candidate_diversity
            ),
            "evidence_support": evidence_support,
            "grounding_adequacy": grounding_adequacy,
            "candidate_source_relevance": candidate_source_relevance,
            "quality_warnings": quality_warnings.to_dict(),
            "promotion_eligibility": promotion_eligibility,
            "semantic_diversification_repair": (
                diversification_repair.to_dict()
            ),
            "raw_candidates": enrichment_comparison[
                "shadow_raw_candidates"
            ],
            "enrichment": enrichment_comparison["shadow_enrichment"],
            "shadow_vs_deterministic_comparison": (
                enrichment_comparison["comparison"]
            ),
            **(
                {"manual_review_template": manual_review_template}
                if manual_review_template is not None
                else {}
            ),
        },
    }


def _candidate_diversity_trace_from_dict(
    payload: Optional[Dict[str, Any]],
) -> Optional[CandidateDiversityTrace]:
    if not payload:
        return None

    pairs = [
        CandidateDiversityPair(
            candidate_a_title=str(
                pair.get("candidate_a_title", "")
            ),
            candidate_b_title=str(
                pair.get("candidate_b_title", "")
            ),
            raw_cosine=float(pair.get("raw_cosine", 0.0)),
            flagged=bool(pair.get("flagged", False)),
        )
        for pair in payload.get("pairwise_similarity", [])
    ]

    return CandidateDiversityTrace(
        similarity_threshold=float(
            payload.get("similarity_threshold", 0.82)
        ),
        pairwise_similarity=pairs,
        passed=bool(payload.get("passed", False)),
    )


def build_promotion_eligibility_shadow(
    selected_candidates: List[Dict[str, Any]],
    brief: Any,
    generation_request: CandidateGenerationRequest,
    detected_domain: str,
    evidence_support_scorer: Optional[Any],
    quality_warnings: Any,
    semantic_candidate_diversity: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    if evidence_support_scorer is None:
        return {
            "status": "not_assessed",
            "candidate_assessments": [],
            "summary": {
                "eligible_count": 0,
                "needs_review_count": 0,
                "ineligible_count": 0,
            },
            "reason": (
                "Evidence-support shadow was not enabled, so promotion "
                "eligibility could not assess direct grounding."
            ),
        }

    candidates = [
        CandidateDirection(
            **{
                key: value
                for key, value in candidate.items()
                if key != "ranking"
            }
        )
        for candidate in selected_candidates
    ]

    diversity_trace = _candidate_diversity_trace_from_dict(
        semantic_candidate_diversity
    )
    assessments = []

    for candidate in candidates:
        validation = validate_candidate(candidate, brief)
        evidence_assessment = evidence_support_scorer.assess_candidate(
            candidate=candidate,
            brief=brief,
        )
        grounding = assess_grounding_adequacy(
            candidate=candidate,
            brief=brief,
            assessment=evidence_assessment,
        )

        feasibility_prescreen = prescreen_candidate_feasibility(
            candidate=candidate,
            brief=brief,
            request=generation_request,
            detected_domain=detected_domain,
        )

        assessments.append(
            assess_promotion_eligibility(
                candidate=candidate,
                validation=validation,
                grounding=grounding,
                quality_warnings=quality_warnings,
                semantic_candidate_diversity=diversity_trace,
                feasibility_prescreen=feasibility_prescreen,
            ).to_dict()
        )

    status_counts = {
        "eligible_count": sum(
            assessment["status"] == "eligible"
            for assessment in assessments
        ),
        "needs_review_count": sum(
            assessment["status"] == "needs_review"
            for assessment in assessments
        ),
        "ineligible_count": sum(
            assessment["status"] == "ineligible"
            for assessment in assessments
        ),
    }

    return {
        "status": "assessed",
        "candidate_assessments": assessments,
        "summary": status_counts,
    }


def build_semantic_goal_relevance_shadow(
    selected_candidates: List[Dict[str, Any]],
    generation_request: Any,
    scorer: GoalRelevanceScorer,
) -> List[Dict[str, Any]]:
    candidates = [
        CandidateDirection(
            **{
                key: value
                for key, value in candidate.items()
                if key != "ranking"
            }
        )
        for candidate in selected_candidates
    ]

    return [
        result.trace.to_dict()
        for result in scorer.score_candidates(
            generation_request,
            candidates,
        )
    ]



def build_semantic_candidate_diversity_shadow(
    selected_candidates: List[Dict[str, Any]],
    scorer: SemanticCandidateDiversityScorer,
) -> Dict[str, Any]:
    candidates = [
        CandidateDirection(
            **{
                key: value
                for key, value in candidate.items()
                if key != "ranking"
            }
        )
        for candidate in selected_candidates
    ]

    return scorer.assess_candidates(candidates).to_dict()


def build_selected_candidate_evidence_assessments(
    selected_candidates: List[Dict[str, Any]],
    brief: Any,
    scorer: Any,
) -> List[Any]:
    candidates = [
        CandidateDirection(
            **{
                key: value
                for key, value in candidate.items()
                if key != "ranking"
            }
        )
        for candidate in selected_candidates
    ]

    return [
        (
            candidate,
            scorer.assess_candidate(
                candidate=candidate,
                brief=brief,
            ),
        )
        for candidate in candidates
    ]


def build_evidence_support_shadow(
    selected_candidates: List[Dict[str, Any]],
    brief: Any,
    scorer: Any,
) -> List[Dict[str, Any]]:
    return [
        assessment.to_dict()
        for _, assessment in build_selected_candidate_evidence_assessments(
            selected_candidates=selected_candidates,
            brief=brief,
            scorer=scorer,
        )
    ]


def build_cross_encoder_goal_relevance_shadow(
    selected_candidates: List[Dict[str, Any]],
    generation_request: Any,
    embedding_scorer: Any,
    cross_encoder_scorer: Any,
    top_k: int,
    margin_threshold: float,
) -> List[Dict[str, Any]]:
    from planning.semantic_escalation import (
        build_low_margin_escalation_details,
    )

    candidates = [
        CandidateDirection(
            **{
                key: value
                for key, value in candidate.items()
                if key != "ranking"
            }
        )
        for candidate in selected_candidates
    ]

    embedding_results = embedding_scorer.score_candidates(
        generation_request,
        candidates,
    )

    escalation_details = build_low_margin_escalation_details(
        results=embedding_results,
        top_k=top_k,
        margin_threshold=margin_threshold,
    )
    escalated_keys = {
        candidate_key
        for candidate_key, detail in escalation_details.items()
        if detail["escalated"]
    }

    escalated_pairs = [
        (candidate, embedding_result)
        for candidate, embedding_result in zip(
            candidates,
            embedding_results,
        )
        if embedding_result.candidate_key in escalated_keys
    ]

    if not escalated_pairs:
        return []

    cross_encoder_results = cross_encoder_scorer.score_candidates(
        generation_request,
        [candidate for candidate, _ in escalated_pairs],
    )

    return [
        {
            "candidate_key": embedding_result.candidate_key,
            "candidate_title": candidate.title,
            "embedding_raw_cosine": (
                embedding_result.trace.raw_cosine
            ),
            "embedding_normalized_score": (
                embedding_result.trace.normalized_score
            ),
            "cross_encoder_raw_score": (
                cross_encoder_result.raw_score
            ),
            "embedding_rank": escalation_details[
                embedding_result.candidate_key
            ]["embedding_rank"],
            "top_embedding_margin": escalation_details[
                embedding_result.candidate_key
            ]["top_embedding_margin"],
            "cohort_size": escalation_details[
                embedding_result.candidate_key
            ]["cohort_size"],
            "escalated": True,
            "escalation_reason": "within_top_margin",
        }
        for (candidate, embedding_result), cross_encoder_result in zip(
            escalated_pairs,
            cross_encoder_results,
        )
    ]


def write_shadow_comparison_artifact(
    artifact: Dict[str, Any],
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / (
        f"{_query_slug(artifact['query'])}_"
        f"{artifact['generated_at_utc']}.json"
    )
    output_path.write_text(json.dumps(artifact, indent=2))
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare legacy planning with the V2 shadow-planning path."
        )
    )
    parser.add_argument(
        "--query",
        required=True,
        help="Natural-language project goal.",
    )
    parser.add_argument(
        "--selected-direction",
        default=None,
        help="Optional confirmed planning direction.",
    )
    parser.add_argument(
        "--skill-level",
        default="",
    )
    parser.add_argument(
        "--time-available",
        default="",
    )
    parser.add_argument(
        "--target-role",
        action="append",
        default=[],
        help="Repeat for multiple roles.",
    )
    parser.add_argument(
        "--preferred-stack",
        action="append",
        default=[],
        help="Repeat for multiple technologies.",
    )
    parser.add_argument(
        "--fixture-response",
        default=None,
        help=(
            "Optional JSON provider-response fixture. When omitted, "
            "the artifact contains a V2 prompt-ready payload only."
        ),
    )
    parser.add_argument(
        "--provider",
        choices=["mock", "openai"],
        default="mock",
        help="Provider used only for an explicit local evaluation.",
    )
    parser.add_argument(
        "--allow-live-llm",
        action="store_true",
        help="Required together with .env settings for a paid OpenAI run.",
    )
    parser.add_argument(
        "--semantic-shadow",
        action="store_true",
        help=(
            "Add local embedding-based goal-relevance traces to the "
            "comparison artifact without changing candidate selection."
        ),
    )
    parser.add_argument(
        "--semantic-diversity-shadow",
        action="store_true",
        help=(
            "Add pairwise semantic candidate-diversity traces without "
            "changing candidate selection."
        ),
    )
    parser.add_argument(
        "--cross-encoder-shadow",
        action="store_true",
        help=(
            "Add local cross-encoder traces for ambiguous embedding "
            "candidates. Requires --semantic-shadow."
        ),
    )
    parser.add_argument(
        "--shadow-vs-deterministic-shadow",
        action="store_true",
        help=(
            "Add local semantic comparison between deterministic and "
            "shadow candidate sets without changing selection."
        ),
    )
    parser.add_argument(
        "--evidence-support-shadow",
        action="store_true",
        help=(
            "Add candidate-to-evidence support traces without changing "
            "candidate selection."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if (
        getattr(args, "cross_encoder_shadow", False)
        and not getattr(args, "semantic_shadow", False)
    ):
        raise SystemExit(
            "--cross-encoder-shadow requires --semantic-shadow"
        )

    if args.provider == "openai":
        require_live_openai_access(
            provider_name=args.provider,
            allow_live_llm=args.allow_live_llm,
        )

    constraints = {
        "skill_level": args.skill_level,
        "time_available": args.time_available,
        "target_roles": args.target_role,
        "preferred_stack": args.preferred_stack,
    }

    understanding = understand_query(
        goal=args.query,
        constraints=constraints,
    )

    evidence_payload = retrieve_evidence(
        user_query=args.query,
        top_k=6,
        intent_hints=understanding["direction_hints"],
        selected_direction=args.selected_direction,
    )

    fixture_response = None

    if args.fixture_response:
        fixture_path = Path(args.fixture_response)

        if not fixture_path.exists():
            raise SystemExit(
                f"Fixture response was not found: {fixture_path}"
            )

        fixture_response = json.loads(fixture_path.read_text())

    provider = None
    execution_mode = "fixture"
    semantic_goal_scorer = None
    semantic_candidate_diversity_scorer = None
    cross_encoder_goal_scorer = None
    evidence_support_scorer = None

    if (
        args.semantic_shadow
        or getattr(args, "semantic_diversity_shadow", False)
        or getattr(args, "shadow_vs_deterministic_shadow", False)
    ):
        semantic_encoder = SemanticEngineTextEncoder(SemanticEngine())

        if args.semantic_shadow:
            semantic_goal_scorer = GoalRelevanceScorer(
                semantic_encoder
            )

        if args.semantic_diversity_shadow:
            semantic_candidate_diversity_scorer = (
                SemanticCandidateDiversityScorer(
                    semantic_encoder
                )
            )

    if args.cross_encoder_shadow:
        cross_encoder_goal_scorer = (
            CrossEncoderGoalRelevanceScorer(
                CrossEncoderGoalPairScorer(
                    CrossEncoderReranker()
                )
            )
        )

    if getattr(args, "evidence_support_shadow", False):
        evidence_support_scorer = CandidateEvidenceSupportScorer(
            SemanticEngineTextEncoder(SemanticEngine())
        )

    if args.provider == "openai":
        if fixture_response is not None:
            raise SystemExit(
                "Use either --fixture-response or --provider openai, not both."
            )

        provider = OpenAICandidateGenerationProvider()
        execution_mode = "live"

    artifact = build_shadow_comparison_artifact(
        evidence_payload=evidence_payload,
        user_goal=args.query,
        constraints=constraints,
        fixture_response=fixture_response,
        provider=provider,
        execution_mode=execution_mode,
        semantic_goal_scorer=semantic_goal_scorer,
        semantic_candidate_diversity_scorer=(
            semantic_candidate_diversity_scorer
        ),
        cross_encoder_goal_scorer=cross_encoder_goal_scorer,
        evidence_support_scorer=evidence_support_scorer,
        comparison_encoder=(
            semantic_encoder
            if getattr(
                args,
                "shadow_vs_deterministic_shadow",
                False,
            )
            else None
        ),
    )

    output_path = write_shadow_comparison_artifact(
        artifact=artifact,
        output_dir=Path(args.output_dir),
    )

    print(f"Wrote shadow comparison artifact: {output_path}")
    print(
        "Legacy directions:",
        artifact["legacy_planner"]["direction_count"],
    )
    print(
        "V2 status:",
        artifact["v2_shadow"]["status"],
    )

if __name__ == "__main__":
    main()
