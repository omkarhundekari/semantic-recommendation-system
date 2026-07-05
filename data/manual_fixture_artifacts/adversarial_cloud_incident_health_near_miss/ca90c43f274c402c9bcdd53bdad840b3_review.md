# Manual Review Packet: adversarial_cloud_incident_health_near_miss

## Artifact Identity
```json
{
  "artifact_id": "ca90c43f274c402c9bcdd53bdad840b3",
  "generation_timestamp_utc": "20260705T170301Z",
  "fixture_id": "adversarial_cloud_incident_health_near_miss"
}
```

## User Goal
Build a cloud incident investigation project that correlates deployment changes with service-health events.

## Constraints
```json
{
  "skill_level": "intermediate",
  "time_available": "3 weeks",
  "target_roles": [
    "Platform Engineer"
  ],
  "preferred_stack": [
    "Python",
    "FastAPI"
  ]
}
```

## Reviewer Focus
Can reviewers distinguish source-ID validity from true candidate-to-source relevance?

## Rubric
- Goal alignment: Read the user goal and the candidate title plus problem statement. Score 2 when the candidate directly addresses the specific goal, 1 when it addresses an adjacent problem in the same domain, and 0 when it is unrelated.
- Grounding: Read the candidate source IDs with the mapped evidence titles and excerpts. Score 2 when cited evidence clearly supports the direction, 1 when evidence is adjacent but not specific, and 0 when citations are absent, invalid, or mismatched.
- Scope realism: Read the MVP scope with the stated skill level and available time. Score 2 when it is clearly achievable, 1 when it is a reasonable stretch, and 0 when it is unrealistic.
- Distinctiveness: Assess each planner set as a whole. Score 2 for three meaningfully different problem angles, 1 for two distinct directions plus one near-duplicate, and 0 when directions are mostly variations of the same idea.
- Overall preference options: deterministic, openai, tie, both_weak.
- Response quality options: standard, limited, exploratory.

## Evidence Brief
### paper-cloud-incidents — Event Correlation for Cloud Incident Investigation
- Type: research_paper
- Support scope: direct
- Excerpt: Event Correlation for Cloud Incident Investigation Correlating deployment changes, service health, and operational telemetry supports cloud incident investigation.
### repo-incident-timeline — Cloud Incident Timeline Toolkit
- Type: github_repository
- Support scope: direct
- Excerpt: Cloud Incident Timeline Toolkit Combine deploy events, service-health metrics, and incident notes into investigation timelines.
### paper-health-events — Continuous Health Event Retrieval
- Type: research_paper
- Support scope: adjacent_planning
- Excerpt: Continuous Health Event Retrieval Retrieve and summarize event sequences from continuous personal health data.

## Evidence Quality Diagnostics
```json
{
  "status": "not_routed_pending_calibration",
  "metrics": {
    "curation_pool_size": 3,
    "retained_source_count": 3,
    "final_brief_source_count": 3,
    "direct_source_count": 2,
    "adjacent_source_count": 1,
    "required_anchor_count": 0,
    "matched_required_anchor_count": 0,
    "query_anchor_coverage": null,
    "unique_query_term_count": 3,
    "unique_query_phrase_count": 3,
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
### Project Opportunity Discovery Engine
- Problem / angle: Turn technical evidence into buildable project opportunities with scope, risks, and career signal.
- Evidence title: Event Correlation for Cloud Incident Investigation
- Evidence type: research_paper
- MVP scope:
  - Define one narrow, measurable workflow for Project Opportunity Discovery Engine.
  - Create a small reproducible input dataset or sample scenario.
  - Implement a transparent scoring, recommendation, or analysis pipeline.
  - Show outputs with explanations, confidence signals, and known limitations.
  - Validate the workflow against representative expected outcomes.
  - Define a measurable success metric that proves the project reduces the specific user problem identified in the evidence.
### Technical Roadmap Recommendation System
- Problem / angle: Generate learning paths, project roadmaps, and role alignment from user goals.
- Evidence title: Event Correlation for Cloud Incident Investigation
- Evidence type: research_paper
- MVP scope:
  - Define one narrow, measurable workflow for Technical Roadmap Recommendation System.
  - Create a small reproducible input dataset or sample scenario.
  - Implement a transparent scoring, recommendation, or analysis pipeline.
  - Show outputs with explanations, confidence signals, and known limitations.
  - Validate the workflow against representative expected outcomes.
  - Add reliability checks, warning states, and evidence-based quality indicators for risky or low-confidence outputs.
### Evidence-Grounded Portfolio Planner
- Problem / angle: Recommend portfolio projects grounded in evidence, skills, and target roles.
- Evidence title: Event Correlation for Cloud Incident Investigation
- Evidence type: research_paper
- MVP scope:
  - Define one narrow, measurable workflow for Evidence-Grounded Portfolio Planner.
  - Create a small reproducible input dataset or sample scenario.
  - Implement a transparent scoring, recommendation, or analysis pipeline.
  - Show outputs with explanations, confidence signals, and known limitations.
  - Validate the workflow against representative expected outcomes.
  - Add reliability checks, warning states, and evidence-based quality indicators for risky or low-confidence outputs.

## Shadow Directions: Raw Candidates
### Deployment-to-Incident Correlation Workbench
- Problem: Platform engineers need to inspect whether deployment changes align with service-health degradation during incidents.
- Target user: Platform engineers
- Evidence relationship: Uses direct cloud incident correlation evidence.
- Source IDs: ['paper-cloud-incidents']
- Cited evidence:
  - paper-cloud-incidents: Event Correlation for Cloud Incident Investigation (direct)
- MVP scope:
  - Load sample deploy and service-health events.
  - Normalize timestamps into one timeline.
  - Calculate simple correlation signals.
  - Show likely deployment-to-incident links.
### Incident Timeline Evidence Explorer
- Problem: Investigators need a concise view of operational events, health signals, and incident notes.
- Target user: Platform engineers
- Evidence relationship: Uses cloud incident implementation context.
- Source IDs: ['repo-incident-timeline']
- Cited evidence:
  - repo-incident-timeline: Cloud Incident Timeline Toolkit (direct)
- MVP scope:
  - Load sample incident records.
  - Merge deployment and health-event timestamps.
  - Filter timeline entries by service.
  - Show a focused incident timeline.
### Health Event Incident Correlator
- Problem: Teams need to correlate health events during operational incidents.
- Target user: Platform engineers
- Evidence relationship: Uses event-retrieval evidence.
- Source IDs: ['paper-health-events']
- Cited evidence:
  - paper-health-events: Continuous Health Event Retrieval (adjacent_planning)
- MVP scope:
  - Load sample event records.
  - Correlate event sequences.
  - Show related events.

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
  "query_fingerprint": "3ea7f74efff01331",
  "deterministic_review": {
    "planner_path": "deterministic",
    "candidate_reviews": [
      {
        "candidate_title": "Project Opportunity Discovery Engine",
        "goal_alignment": null,
        "grounding": null,
        "scope_realism": null,
        "notes": ""
      },
      {
        "candidate_title": "Technical Roadmap Recommendation System",
        "goal_alignment": null,
        "grounding": null,
        "scope_realism": null,
        "notes": ""
      },
      {
        "candidate_title": "Evidence-Grounded Portfolio Planner",
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
        "candidate_title": "Deployment-to-Incident Correlation Workbench",
        "goal_alignment": null,
        "grounding": null,
        "scope_realism": null,
        "notes": ""
      },
      {
        "candidate_title": "Incident Timeline Evidence Explorer",
        "goal_alignment": null,
        "grounding": null,
        "scope_realism": null,
        "notes": ""
      },
      {
        "candidate_title": "Health Event Incident Correlator",
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
