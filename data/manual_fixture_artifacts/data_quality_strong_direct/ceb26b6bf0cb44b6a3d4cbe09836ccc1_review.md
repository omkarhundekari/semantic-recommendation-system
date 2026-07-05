# Manual Review Packet: data_quality_strong_direct

## Artifact Identity
```json
{
  "artifact_id": "ceb26b6bf0cb44b6a3d4cbe09836ccc1",
  "generation_timestamp_utc": "20260705T170301Z",
  "fixture_id": "data_quality_strong_direct"
}
```

## User Goal
Build a data engineering project that helps teams detect pipeline data-quality failures and prioritize remediation.

## Constraints
```json
{
  "skill_level": "intermediate",
  "time_available": "3 weeks",
  "target_roles": [
    "Data Engineer"
  ],
  "preferred_stack": [
    "Python",
    "FastAPI"
  ]
}
```

## Reviewer Focus
Does the planner create different operational angles rather than three validation-dashboard variants?

## Rubric
- Goal alignment: Read the user goal and the candidate title plus problem statement. Score 2 when the candidate directly addresses the specific goal, 1 when it addresses an adjacent problem in the same domain, and 0 when it is unrelated.
- Grounding: Read the candidate source IDs with the mapped evidence titles and excerpts. Score 2 when cited evidence clearly supports the direction, 1 when evidence is adjacent but not specific, and 0 when citations are absent, invalid, or mismatched.
- Scope realism: Read the MVP scope with the stated skill level and available time. Score 2 when it is clearly achievable, 1 when it is a reasonable stretch, and 0 when it is unrealistic.
- Distinctiveness: Assess each planner set as a whole. Score 2 for three meaningfully different problem angles, 1 for two distinct directions plus one near-duplicate, and 0 when directions are mostly variations of the same idea.
- Overall preference options: deterministic, openai, tie, both_weak.
- Response quality options: standard, limited, exploratory.

## Evidence Brief
### repo-observability — Pipeline Quality Observability Toolkit
- Type: github_repository
- Support scope: direct
- Excerpt: Pipeline Quality Observability Toolkit Track data checks, failed records, pipeline owners, and quality trends for engineering teams.
### paper-quality — Data Quality Monitoring for Reliable Pipelines
- Type: research_paper
- Support scope: direct
- Excerpt: Data Quality Monitoring for Reliable Pipelines Data validation, anomaly detection, and quality observability improve pipeline reliability and remediation decisions.
### paper-lineage — Lineage-Aware Impact Analysis for Data Incidents
- Type: research_paper
- Support scope: direct
- Excerpt: Lineage-Aware Impact Analysis for Data Incidents Dataset lineage can identify downstream assets affected by quality incidents and support priority-based remediation.

## Evidence Quality Diagnostics
```json
{
  "status": "not_routed_pending_calibration",
  "metrics": {
    "curation_pool_size": 3,
    "retained_source_count": 3,
    "final_brief_source_count": 3,
    "direct_source_count": 3,
    "adjacent_source_count": 0,
    "required_anchor_count": 0,
    "matched_required_anchor_count": 0,
    "query_anchor_coverage": null,
    "unique_query_term_count": 2,
    "unique_query_phrase_count": 0,
    "source_type_count": 2,
    "dominant_source_type": "research_paper",
    "dominant_source_type_fraction": 0.6666666666666666,
    "top_direct_relevance_margin": 2.0,
    "coverage_warnings": []
  },
  "thresholds": {
    "version": "v1",
    "calibration_status": "unresolved",
    "sparse_direct_source_threshold": null,
    "ambiguity_top_margin_threshold": null,
    "low_diversity_fraction_threshold": null
  },
  "evidence_sparse": null,
  "evidence_ambiguous": null,
  "source_diversity_low": null,
  "unresolved_signal_names": [
    "evidence_sparse",
    "evidence_ambiguous",
    "source_diversity_low"
  ],
  "routing_ready": false
}
```

## Deterministic Directions: Raw Inputs
### Data Pipeline Quality Monitor
- Problem / angle: Monitor ETL pipelines for freshness, schema drift, missing values, anomalies, and broken transformations.
- Evidence title: Data Quality Monitoring for Reliable Pipelines
- Evidence type: research_paper
- MVP scope:
  - Ingest a small source dataset into a staged raw table or file layer.
  - Apply transformations and create a clean analytics-ready output table.
  - Validate schema, freshness, null rates, duplicate records, and key business rules.
  - Track pipeline status, row counts, failures, and transformation lineage.
  - Build a monitoring view with failed checks and recommended remediation actions.
  - Define a measurable success metric that proves the project reduces the specific user problem identified in the evidence.
### Data Lineage and Dependency Visualizer
- Problem / angle: Map pipeline dependencies, upstream/downstream tables, transformations, and failure impact across data systems.
- Evidence title: Lineage-Aware Impact Analysis for Data Incidents
- Evidence type: research_paper
- MVP scope:
  - Ingest a small source dataset into a staged raw table or file layer.
  - Apply transformations and create a clean analytics-ready output table.
  - Validate schema, freshness, null rates, duplicate records, and key business rules.
  - Track pipeline status, row counts, failures, and transformation lineage.
  - Build a monitoring view with failed checks and recommended remediation actions.
  - Add reliability checks, warning states, and evidence-based quality indicators for risky or low-confidence outputs.
### Warehouse Query and Cost Intelligence Dashboard
- Problem / angle: Analyze SQL usage, expensive queries, warehouse cost patterns, and optimization opportunities.
- Evidence title: Data Quality Monitoring for Reliable Pipelines
- Evidence type: research_paper
- MVP scope:
  - Ingest a small source dataset into a staged raw table or file layer.
  - Apply transformations and create a clean analytics-ready output table.
  - Validate schema, freshness, null rates, duplicate records, and key business rules.
  - Track pipeline status, row counts, failures, and transformation lineage.
  - Build a monitoring view with failed checks and recommended remediation actions.
  - Add reliability checks, warning states, and evidence-based quality indicators for risky or low-confidence outputs.

## Shadow Directions: Raw Candidates
### Pipeline Data-Quality Monitor
- Problem: Data engineers need a focused way to detect and triage recurring quality failures in pipelines.
- Target user: Data engineers
- Evidence relationship: Uses direct evidence on data validation and quality observability.
- Source IDs: ['paper-quality']
- Cited evidence:
  - paper-quality: Data Quality Monitoring for Reliable Pipelines (direct)
- MVP scope:
  - Load sample pipeline records and quality rules.
  - Run completeness and schema validation checks.
  - Store failed checks with timestamps.
  - Show a dashboard of active quality failures.
### Quality Trend and Ownership Workbench
- Problem: Engineering teams need to see whether recurring quality issues are concentrated by pipeline and owner.
- Target user: Data platform teams
- Evidence relationship: Uses implementation context for pipeline quality observability workflows.
- Source IDs: ['repo-observability']
- Cited evidence:
  - repo-observability: Pipeline Quality Observability Toolkit (direct)
- MVP scope:
  - Load historical quality-event records.
  - Group failures by pipeline and owner.
  - Calculate recurring failure counts.
  - Show trend and ownership views.
### Lineage Impact Explorer for Data Incidents
- Problem: Teams struggle to identify downstream datasets and owners affected by a known quality incident.
- Target user: Data engineers
- Evidence relationship: Uses direct evidence on lineage-aware impact analysis for incidents.
- Source IDs: ['paper-lineage']
- Cited evidence:
  - paper-lineage: Lineage-Aware Impact Analysis for Data Incidents (direct)
- MVP scope:
  - Store sample dataset lineage edges.
  - Load a known data-quality incident.
  - Compute affected downstream datasets.
  - Show an owner and impact report.

## Comparison Diagnostics
```json
{
  "semantic_comparison_status": "not_assessed_no_comparison_encoder",
  "set_similarity_score": null,
  "unique_angle_count": null,
  "unique_openai_titles": [],
  "notes": [
    "Cross-set semantic similarity is a difference signal, not a quality score.",
    "Portfolio tiers are preserved for review but are assigned by candidate order and must not be interpreted as quality labels.",
    "Deterministic grounding is not assessed by this contract yet; only shadow grounding traces are currently comparable."
  ]
}
```

## Unscored Manual Review Template
```json
{
  "rubric_version": "v1",
  "query_fingerprint": "5f606fbf06b73b46",
  "deterministic_review": {
    "planner_path": "deterministic",
    "candidate_reviews": [
      {
        "candidate_title": "Data Pipeline Quality Monitor",
        "goal_alignment": null,
        "grounding": null,
        "scope_realism": null,
        "notes": ""
      },
      {
        "candidate_title": "Data Lineage and Dependency Visualizer",
        "goal_alignment": null,
        "grounding": null,
        "scope_realism": null,
        "notes": ""
      },
      {
        "candidate_title": "Warehouse Query and Cost Intelligence Dashboard",
        "goal_alignment": null,
        "grounding": null,
        "scope_realism": null,
        "notes": ""
      }
    ],
    "distinctiveness": null,
    "notes": ""
  },
  "openai_review": {
    "planner_path": "openai",
    "candidate_reviews": [
      {
        "candidate_title": "Pipeline Data-Quality Monitor",
        "goal_alignment": null,
        "grounding": null,
        "scope_realism": null,
        "notes": ""
      },
      {
        "candidate_title": "Quality Trend and Ownership Workbench",
        "goal_alignment": null,
        "grounding": null,
        "scope_realism": null,
        "notes": ""
      },
      {
        "candidate_title": "Lineage Impact Explorer for Data Incidents",
        "goal_alignment": null,
        "grounding": null,
        "scope_realism": null,
        "notes": ""
      }
    ],
    "distinctiveness": null,
    "notes": ""
  },
  "overall_preference": null,
  "overall_preference_reason": "",
  "response_quality": null,
  "response_quality_reason": "",
  "unique_angle_quality": null,
  "unique_angle_quality_reason": "",
  "reviewer_notes": ""
}
```
