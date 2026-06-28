# Project Decision Trace: Field Mapping Audit

## Purpose

This document records how the Phase 1 `ProjectDecisionTrace` contract maps to the live RAG pipeline before implementation begins.

Audit artifacts used:

- `outputs/traces/rag_decision_trace_audit.json`
- `outputs/traces/rag_internal_ideas_audit.json`

## Reliable Session-Level Research Evidence

Source:
`research_evidence_assessment.evidence.supporting_papers`

Available now:

- `document_id`
- `title`
- `category`
- `retrieval_rank`
- `evidence_tags`
- `evidence_snippets`
- `alignment`
- `matched_query_terms`
- `matched_query_phrases`
- `matched_required_anchor_terms`
- alignment reason

These fields are the source of truth for research-paper support in a decision trace.

## Session-Level Confidence

Source:
`research_evidence_assessment.confidence`

Available now:

- confidence level: Strong / Limited / Exploratory
- confidence reason
- paper count
- direct paper count
- adjacent paper count
- weak paper count

## Internal Idea Fields

Source:
internal output from `generate_project_ideas(...)`

Available now:

- stable idea source field: `project_title`
- planning domain: `detected_domain`
- buildable gap: `evidence_buildable_gap`
- planning rationale: `evidence_focus_statement`
- evidence-driven angle: `evidence_driven_angle`
- project opportunity: `evidence_project_opportunity`
- research motivation: `research_motivation`
- implementation references: `source_contributions`
- implementation technologies: `implementation_technologies`
- MVP scope: `mvp_scope`
- advanced extensions: `advanced_extensions`
- target roles: `target_roles`

## Important Mapping Rules

1. `based_on_paper` is not a reliable research-paper identifier.
   It may point to a project pattern or GitHub repository.

2. `source_contributions` should be represented separately as implementation references.
   It must not be presented as direct research support.

3. Research-paper support for every idea must be selected from the session-level
   `supporting_papers` evidence payload.

4. RAG ideas currently share session-level direct research evidence.
   Phase 1 must clearly distinguish:
   - research support for the planning domain,
   - idea-specific primary inspiration,
   - implementation references.

5. Current `feasibility_analysis` is legacy/template-driven and inconsistent:
   it can report High complexity / 8–14 days while its later build profile says
   Small scope / 3–5 days.

   It must not populate final trace feasibility fields.

## Fields Available for Phase 1

- idea ID
- idea title
- supporting research papers
- evidence tags
- detected signals
- buildable gap
- confidence level and reason
- planning domain
- planning-domain reason
- assumptions
- evidence gaps
- implementation references

## Fields Deferred to Phase 2

- feasibility result
- feasibility reason
- feasibility factors
- feasibility constraints
- feasibility policy explanation

## Required Phase 1 Output Principle

A decision trace must make it possible to answer:

- Which research evidence supports this idea?
- Which evidence signals influenced the idea?
- Why was this planning domain selected?
- What gap is the project intended to address?
- Which parts are supported by research versus implementation references?
- What remains assumed, adjacent, or unsupported?
