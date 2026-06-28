# Evidence-Driven Planner Design

## Goal
Replace fixed domain idea banks as the primary project-generation mechanism.

## Current state
The planner uses domain profiles, fixed titles, keyword maps, and title-specific MVP templates.

## Target flow
1. Retrieve ranked evidence.
2. Build a structured EvidenceBrief from papers, repositories, and patterns.
3. Generate candidate project directions from the EvidenceBrief and user constraints.
4. Rank candidates for relevance, feasibility, evidence support, and diversity.
5. Generate a roadmap.
6. Validate claims and attach a decision trace.
7. Fall back to deterministic templates only when evidence or generation quality is insufficient.

## Guardrails
- No invented papers, repositories, datasets, metrics, or claims.
- Named evidence is shown only when support is sufficiently specific.
- The LLM is a constrained synthesizer, never the evidence authority.
- Deterministic validation remains mandatory.
