import json

from planning.openai_planner_evaluation_report import (
    build_openai_planner_evaluation_report,
)


def test_report_tracks_evaluated_and_missing_cases(tmp_path):
    user_goal = "Build a RAG evaluation project."

    artifact = {
        "generated_at_utc": "20260705T130257Z",
        "query": user_goal,
        "v2_shadow": {
            "generation_metadata": {
                "execution_mode": "live",
                "model": "test-model",
            },
            "diagnostics": {
                "provider_called": True,
                "valid_candidate_count": 3,
            },
            "shadow_readiness": {"status": "ready"},
            "semantic_candidate_diversity": {"passed": True},
            "semantic_goal_relevance": [
                {"raw_cosine": 0.7},
                {"raw_cosine": 0.8},
            ],
            "grounding_adequacy": [
                {
                    "adequacy_class": "cited_with_direct_scope",
                    "min_cited_alignment": 0.4,
                }
            ],
        },
    }

    (tmp_path / "rag.json").write_text(json.dumps(artifact))

    dataset = {
        "cases": [
            {
                "id": "rag_quality",
                "user_goal": user_goal,
                "manual_review": {
                    "verdict": None,
                    "reason": None,
                },
            },
            {
                "id": "security_triage",
                "user_goal": "Build a security triage project.",
                "manual_review": {
                    "verdict": None,
                    "reason": None,
                },
            },
        ]
    }

    report = build_openai_planner_evaluation_report(
        dataset=dataset,
        output_dir=tmp_path,
    )

    assert report["summary"]["configured_case_count"] == 2
    assert report["summary"]["evaluated_case_count"] == 1
    assert report["summary"]["missing_artifact_case_count"] == 1
    assert report["summary"]["ready_case_count"] == 1
    assert report["summary"]["diversity_pass_case_count"] == 1

    rag = report["case_reports"]["rag_quality"]
    assert rag["status"] == "evaluated"
    assert rag["quality_warnings"]["warnings"] == []
    assert rag["quality_warnings"]["signals"][
        "quality_warning_count"
    ] == 0
    assert rag["goal_relevance_summary"]["minimum_raw_cosine"] == 0.7
    assert rag["goal_relevance_summary"]["average_raw_cosine"] == 0.75
    assert rag["grounding_summary"]["minimum_cited_alignment"] == 0.4
    assert rag["grounding_summary"]["average_cited_alignment"] == 0.4
    assert rag["diversity_summary"]["highest_pair_similarity"] is None

    assert report["summary"]["average_case_goal_relevance"] == 0.75
    assert report["summary"]["minimum_candidate_goal_relevance"] == 0.7
    assert report["summary"]["average_case_grounding_alignment"] == 0.4
    assert report["summary"]["minimum_candidate_grounding_alignment"] == 0.4
    assert report["summary"]["highest_candidate_pair_similarity"] is None
    assert report["summary"]["total_tokens"] == 0
    assert report["summary"]["quality_warning_case_count"] == 0
    assert report["summary"]["quality_warning_counts"] == {}

    missing = report["case_reports"]["security_triage"]
    assert missing["status"] == "missing_artifact"


def test_recomputes_promotion_eligibility_for_older_artifacts(tmp_path):
    user_goal = "Build an incident investigation project."

    artifact = {
        "generated_at_utc": "20260705T140000Z",
        "query": user_goal,
        "v2_shadow": {
            "generation_metadata": {"usage": {}},
            "diagnostics": {},
            "shadow_readiness": {"status": "ready"},
            "semantic_candidate_diversity": {
                "similarity_threshold": 0.82,
                "pairwise_similarity": [
                    {
                        "candidate_a_title": (
                            "Incident Correlation Workbench"
                        ),
                        "candidate_b_title": "Incident Timeline Tool",
                        "raw_cosine": 0.71,
                        "flagged": False,
                    }
                ],
                "passed": True,
            },
            "semantic_goal_relevance": [
                {
                    "candidate_title": (
                        "Incident Correlation Workbench"
                    ),
                    "raw_cosine": 0.63,
                }
            ],
            "grounding_adequacy": [
                {
                    "candidate_title": "Incident Correlation Workbench",
                    "adequacy_class": "cited_with_direct_scope",
                    "cited_source_ids": ["paper-1"],
                    "cited_source_scopes": ["direct"],
                    "cited_alignment_scores": [0.46],
                    "min_cited_alignment": 0.46,
                    "max_cited_alignment": 0.46,
                    "direct_sources_in_brief": 1,
                    "uncited_direct_sources": [],
                    "adequacy_reason": "Cites direct evidence.",
                }
            ],
            "selected_candidates": [
                {
                    "title": "Incident Correlation Workbench",
                    "problem_statement": (
                        "Operational signals are fragmented during "
                        "incident response."
                    ),
                    "target_user": "Platform engineers",
                    "core_workflow": [
                        "Load incident events.",
                        "Correlate related signals.",
                    ],
                    "mvp_scope": [
                        "Load sample records.",
                        "Correlate event signals.",
                        "Render an investigation timeline.",
                    ],
                    "success_metrics": [
                        "Reduce investigation time."
                    ],
                    "evidence_relationship": (
                        "Uses retained incident evidence."
                    ),
                    "source_ids": ["paper-1"],
                    "assumptions": [],
                    "suggested_stack": ["Python", "FastAPI"],
                    "ranking": {"score": 0.9},
                }
            ],
            "report": {
                "evidence_brief": {
                    "query": user_goal,
                    "sources": [
                        {
                            "source_id": "paper-1",
                            "source_type": "research_paper",
                            "title": "Incident Correlation Research",
                            "excerpt": (
                                "Incident correlation supports response "
                                "workflows."
                            ),
                            "support_scope": "direct",
                        }
                    ],
                    "source_counts": {"research_paper": 1},
                    "recurring_concepts": [],
                    "coverage_warnings": [],
                }
            },
        },
    }

    (tmp_path / "incident.json").write_text(json.dumps(artifact))

    report = build_openai_planner_evaluation_report(
        dataset={
            "cases": [
                {
                    "id": "incident",
                    "user_goal": user_goal,
                    "manual_review": {
                        "verdict": None,
                        "reason": None,
                    },
                }
            ]
        },
        output_dir=tmp_path,
    )

    promotion = report["case_reports"]["incident"][
        "promotion_eligibility"
    ]

    assert promotion["status"] == "recomputed"
    assert promotion["summary"] == {
        "eligible_count": 1,
        "needs_review_count": 0,
        "ineligible_count": 0,
    }
    assert report["summary"]["promotion_eligibility_counts"] == {
        "eligible_count": 1,
        "needs_review_count": 0,
        "ineligible_count": 0,
        "not_assessed_case_count": 0,
    }

    audit = report["case_reports"]["incident"]["promotion_audit"]

    assert audit == [
        {
            "candidate_title": "Incident Correlation Workbench",
            "promotion_status": "eligible",
            "eligible_for_product_promotion": True,
            "blocking_reasons": [],
            "review_reasons": [],
            "quality_warning_codes": [],
            "goal_relevance_raw_cosine": 0.63,
            "grounding_adequacy_class": "cited_with_direct_scope",
            "minimum_cited_alignment": 0.46,
            "nearest_candidate_pair": {
                "candidate_title": "Incident Timeline Tool",
                "raw_cosine": 0.71,
                "flagged": False,
            },
        }
    ]


def test_marks_sparse_legacy_artifact_promotion_as_not_assessed(tmp_path):
    user_goal = "Build a sparse project."

    (tmp_path / "sparse.json").write_text(
        json.dumps(
            {
                "query": user_goal,
                "v2_shadow": {
                    "generation_metadata": {"usage": {}},
                    "shadow_readiness": {"status": "ready"},
                    "semantic_candidate_diversity": None,
                    "semantic_goal_relevance": [],
                    "grounding_adequacy": [],
                },
            }
        )
    )

    report = build_openai_planner_evaluation_report(
        dataset={
            "cases": [
                {
                    "id": "sparse",
                    "user_goal": user_goal,
                    "manual_review": {
                        "verdict": None,
                        "reason": None,
                    },
                }
            ]
        },
        output_dir=tmp_path,
    )

    promotion = report["case_reports"]["sparse"][
        "promotion_eligibility"
    ]

    assert promotion["status"] == "not_assessed"
    assert report["summary"]["promotion_eligibility_counts"] == {
        "eligible_count": 0,
        "needs_review_count": 0,
        "ineligible_count": 0,
        "not_assessed_case_count": 1,
    }


def test_recomputes_diversification_repair_for_older_artifacts(tmp_path):
    user_goal = "Build a data quality project."

    artifact = {
        "query": user_goal,
        "v2_shadow": {
            "generation_metadata": {"usage": {}},
            "shadow_readiness": {"status": "ready"},
            "semantic_candidate_diversity": {
                "similarity_threshold": 0.82,
                "pairwise_similarity": [
                    {
                        "candidate_a_title": "Pipeline Monitor",
                        "candidate_b_title": "Pipeline Failure Triage",
                        "raw_cosine": 0.7915,
                        "flagged": False,
                    }
                ],
                "passed": True,
            },
            "semantic_goal_relevance": [],
            "grounding_adequacy": [],
            "selected_candidates": [
                {
                    "title": "Pipeline Monitor",
                    "core_workflow": [
                        "Run validation checks.",
                        "Show quality alerts.",
                    ],
                    "mvp_scope": [
                        "Load records.",
                        "Run checks.",
                        "Show alerts.",
                    ],
                    "ranking": {"score": 0.93},
                },
                {
                    "title": "Pipeline Failure Triage",
                    "core_workflow": [
                        "Run validation checks.",
                        "Review failed records.",
                    ],
                    "mvp_scope": [
                        "Load records.",
                        "Run checks.",
                        "Show failures.",
                    ],
                    "ranking": {"score": 0.84},
                },
            ],
        },
    }

    (tmp_path / "pipeline.json").write_text(json.dumps(artifact))

    report = build_openai_planner_evaluation_report(
        dataset={
            "cases": [
                {
                    "id": "pipeline",
                    "user_goal": user_goal,
                    "manual_review": {
                        "verdict": None,
                        "reason": None,
                    },
                }
            ]
        },
        output_dir=tmp_path,
    )

    repair = report["case_reports"]["pipeline"][
        "semantic_diversification_repair"
    ]

    assert repair["status"] == "repair_planned"
    assert repair["signals"]["close_cluster_count"] == 1
    assert repair["signals"]["replacement_count"] == 1
    assert repair["directives"][0]["replace_candidate_title"] == (
        "Pipeline Failure Triage"
    )

    assert report["summary"][
        "semantic_diversification_repair_counts"
    ] == {
        "repair_planned_case_count": 1,
        "no_repair_needed_case_count": 0,
        "not_assessed_case_count": 0,
        "close_cluster_count": 1,
        "planned_replacement_count": 1,
    }
