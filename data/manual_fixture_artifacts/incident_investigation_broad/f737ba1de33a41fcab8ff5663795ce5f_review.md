# Manual Review Packet: incident_investigation_broad

## Artifact Identity
```json
{
  "artifact_id": "f737ba1de33a41fcab8ff5663795ce5f",
  "generation_timestamp_utc": "20260709T052120Z",
  "fixture_id": "incident_investigation_broad"
}
```

## User Goal
Build a platform engineering project for incident investigation in three weeks.

## Constraints
```json
{
  "skill_level": "intermediate",
  "time_available": "3 weeks",
  "target_roles": [
    "Backend Engineer",
    "Platform Engineer"
  ],
  "preferred_stack": [
    "Python",
    "React"
  ]
}
```

## Reviewer Focus
Does each direction solve a concrete investigation workflow instead of merely naming a platform dashboard?

## Rubric
- Goal alignment: Read the user goal and the candidate title plus problem statement. Score 2 when the candidate directly addresses the specific goal, 1 when it addresses an adjacent problem in the same domain, and 0 when it is unrelated.
- Grounding: Read the candidate source IDs with the mapped evidence titles and excerpts. Score 2 when cited evidence clearly supports the direction, 1 when evidence is adjacent but not specific, and 0 when citations are absent, invalid, or mismatched.
- Scope realism: Read the MVP scope with the stated skill level and available time. Score 2 when it is clearly achievable, 1 when it is a reasonable stretch, and 0 when it is unrealistic.
- Distinctiveness: Assess each planner set as a whole. Score 2 for three meaningfully different problem angles, 1 for two distinct directions plus one near-duplicate, and 0 when directions are mostly variations of the same idea.
- Overall preference options: deterministic, openai, tie, both_weak.
- Response quality options: standard, limited, exploratory.

## Evidence Brief
### repo-incident-review — Incident Review Evidence Collector
- Type: github_repository
- Support scope: direct
- Excerpt: Incident Review Evidence Collector Collect alerts, deployment records, logs, ownership metadata, and investigation notes into a structured incident review packet.
### paper-incident-timeline — Timeline Reconstruction for Software Incidents
- Type: research_paper
- Support scope: adjacent_planning
- Excerpt: Timeline Reconstruction for Software Incidents Incident investigations often require reconstructing ordered timelines from logs, deployments, alerts, and operator notes to identify plausible contributing events.
### paper-observability-correlation — Correlating Observability Signals During Production Failures
- Type: research_paper
- Support scope: adjacent_planning
- Excerpt: Correlating Observability Signals During Production Failures Production failure analysis can combine logs, metrics, traces, and deployment events to find correlated signals that help engineers narrow investigation scope.

## Evidence Quality Diagnostics
```json
{
  "status": "not_routed_pending_calibration",
  "metrics": {
    "curation_pool_size": 3,
    "retained_source_count": 3,
    "final_brief_source_count": 3,
    "direct_source_count": 1,
    "adjacent_source_count": 2,
    "required_anchor_count": 0,
    "matched_required_anchor_count": 0,
    "query_anchor_coverage": null,
    "unique_query_term_count": 0,
    "unique_query_phrase_count": 1,
    "source_type_count": 2,
    "dominant_source_type": "research_paper",
    "dominant_source_type_fraction": 0.6666666666666666,
    "top_direct_relevance_margin": null,
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
- Evidence title: Incident Review Evidence Collector
- Evidence type: github_repository
- MVP scope:
  - Define one narrow, measurable workflow for Project Opportunity Discovery Engine.
  - Create a small reproducible input dataset or sample scenario.
  - Implement a transparent scoring, recommendation, or analysis pipeline.
  - Show outputs with explanations, confidence signals, and known limitations.
  - Validate the workflow against representative expected outcomes.
  - Define a measurable success metric that proves the project reduces the specific user problem identified in the evidence.
### Technical Roadmap Recommendation System
- Problem / angle: Generate learning paths, project roadmaps, and role alignment from user goals.
- Evidence title: Timeline Reconstruction for Software Incidents
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
- Evidence title: Incident Review Evidence Collector
- Evidence type: github_repository
- MVP scope:
  - Define one narrow, measurable workflow for Evidence-Grounded Portfolio Planner.
  - Create a small reproducible input dataset or sample scenario.
  - Implement a transparent scoring, recommendation, or analysis pipeline.
  - Show outputs with explanations, confidence signals, and known limitations.
  - Validate the workflow against representative expected outcomes.
  - Add reliability checks, warning states, and evidence-based quality indicators for risky or low-confidence outputs.

## Shadow Directions: Raw Candidates
### Observability Signal Correlation Board
- Problem: Engineers investigating a production failure need to compare logs, metrics, traces, and deployments to find correlated signals.
- Target user: Backend engineers and SREs
- Evidence relationship: Uses direct observability correlation evidence for production failure analysis.
- Source IDs: ['paper-observability-correlation']
- Cited evidence:
  - paper-observability-correlation: Correlating Observability Signals During Production Failures (adjacent_planning)
- MVP scope:
  - Create fixture data for metrics, logs, traces, and deploys.
  - Compute simple time-window correlations.
  - Rank correlated signals with transparent rules.
  - Render a board of candidate investigation leads.
### Incident Review Evidence Packet Builder
- Problem: Support teams need a structured packet that collects incident evidence before a postmortem or escalation.
- Target user: Support engineers
- Evidence relationship: Uses implementation context for structured incident review evidence collection.
- Source IDs: ['repo-incident-review']
- Cited evidence:
  - repo-incident-review: Incident Review Evidence Collector (direct)
- MVP scope:
  - Create forms or fixtures for incident evidence.
  - Store evidence items with type, owner, and timestamp.
  - Generate a Markdown or JSON review packet.
  - Highlight missing evidence sections before review.
### Incident Timeline Reconstruction Assistant
- Problem: Support engineers need a way to assemble alerts, deployments, logs, and notes into a coherent incident timeline.
- Target user: Support engineers and SREs
- Evidence relationship: Uses direct incident timeline reconstruction evidence.
- Source IDs: ['paper-incident-timeline']
- Cited evidence:
  - paper-incident-timeline: Timeline Reconstruction for Software Incidents (adjacent_planning)
- MVP scope:
  - Create sample alert, log, deployment, and note fixtures.
  - Normalize timestamps and event types.
  - Sort and group events into an incident timeline.
  - Show likely contributing events with source labels.

## Candidate-to-Source Relevance Diagnostics
```json
[
  {
    "candidate_title": "Observability Signal Correlation Board",
    "source_id": "paper-observability-correlation",
    "source_type": "research_paper",
    "support_scope": "adjacent_planning",
    "candidate_source_shared_terms": [
      "correlated",
      "failure",
      "find",
      "logs",
      "metrics",
      "observability",
      "production",
      "signals",
      "traces"
    ],
    "goal_source_shared_terms": [
      "investigation"
    ],
    "relevance_status": "adjacent_context_only",
    "relevance_reason": "The cited source is retained only as adjacent planning context and should not be treated as core grounding."
  },
  {
    "candidate_title": "Incident Review Evidence Packet Builder",
    "source_id": "repo-incident-review",
    "source_type": "github_repository",
    "support_scope": "direct",
    "candidate_source_shared_terms": [
      "alerts",
      "collect",
      "evidence",
      "incident",
      "logs",
      "metadata",
      "notes",
      "packet",
      "review",
      "structured"
    ],
    "goal_source_shared_terms": [
      "incident",
      "investigation"
    ],
    "relevance_status": "lexically_supported",
    "relevance_reason": "Candidate and source share content terms: alerts, collect, evidence, incident, logs."
  },
  {
    "candidate_title": "Incident Timeline Reconstruction Assistant",
    "source_id": "paper-incident-timeline",
    "source_type": "research_paper",
    "support_scope": "adjacent_planning",
    "candidate_source_shared_terms": [
      "alerts",
      "deployments",
      "events",
      "incident",
      "logs",
      "notes",
      "reconstruction",
      "timeline"
    ],
    "goal_source_shared_terms": [
      "incident"
    ],
    "relevance_status": "adjacent_context_only",
    "relevance_reason": "The cited source is retained only as adjacent planning context and should not be treated as core grounding."
  }
]
```

## Quality Warnings
```json
{
  "warnings": [
    {
      "code": "adjacent_context_only_candidate",
      "message": "One or more candidates cite only adjacent-context sources and should not be treated as strongly grounded.",
      "details": {
        "candidates": [
          {
            "candidate_title": "Observability Signal Correlation Board",
            "source_ids": [
              "paper-observability-correlation"
            ],
            "relevance_statuses": [
              "adjacent_context_only"
            ]
          },
          {
            "candidate_title": "Incident Timeline Reconstruction Assistant",
            "source_ids": [
              "paper-incident-timeline"
            ],
            "relevance_statuses": [
              "adjacent_context_only"
            ]
          }
        ]
      }
    }
  ],
  "signals": {
    "coverage_warning_count": 0,
    "goal_trace_count": 0,
    "grounding_trace_count": 0,
    "diversity_pair_count": 0,
    "source_relevance_trace_count": 3,
    "quality_warning_count": 1
  }
}
```

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
  "query_fingerprint": "2c21043a4a0f5ec0",
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
        "candidate_title": "Observability Signal Correlation Board",
        "goal_alignment": null,
        "grounding": null,
        "scope_realism": null,
        "notes": ""
      },
      {
        "candidate_title": "Incident Review Evidence Packet Builder",
        "goal_alignment": null,
        "grounding": null,
        "scope_realism": null,
        "notes": ""
      },
      {
        "candidate_title": "Incident Timeline Reconstruction Assistant",
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
