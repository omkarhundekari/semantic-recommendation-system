# LLM Synthesis Safety Pipeline

## Purpose

This project does not expose raw LLM output directly as the product answer.

The synthesis layer is a validation-first pipeline that turns retrieved evidence into project directions while preserving grounding, confidence, failure explanations, and deterministic fallback behavior.

Core principle:

> Use LLMs when they add synthesis value, but never trust LLM output without validation.

## Pipeline Overview

```text
reviewed artifact
→ evidence cards
→ value-based routing
→ token estimation
→ structured LLM prompt
→ provider response
→ raw output validation
→ deterministic fallback if invalid
→ final synthesis
→ final synthesis validation
→ run-level and batch reports
```

## Main Components

- Evidence cards: `src/planning/evidence_cards.py`
- Routing policy: `src/planning/llm_routing_policy.py`
- Token estimation: `src/planning/token_estimation.py`
- Structured prompt: `src/planning/llm_prompt_builder.py`
- Provider abstraction: `src/planning/llm_synthesis_client.py`
- OpenAI provider: `src/planning/openai_synthesis_provider.py`
- Output validation: `src/planning/llm_synthesis_output_validator.py`
- Deterministic fallback: `src/planning/llm_synthesis_fallback.py`
- Demo orchestration: `src/planning/llm_synthesis_demo.py`
- Batch evaluation: `src/planning/llm_synthesis_batch_eval.py`

## Safety Chain

```text
raw provider output
→ saved_output_validation
→ deterministic fallback if invalid
→ final_synthesis
→ final_synthesis_validation
```

The product should trust `final_synthesis` only when `final_synthesis_validation.is_valid` is true.

## Failure Categories

```text
parse_failure
metadata_failure
schema_failure
grounding_failure
citation_failure
unknown_failure
```

## Example Safety Result

Raw validation can fail:

```text
raw valid outputs: 0
raw invalid outputs: 2
```

Final synthesis can still recover safely:

```text
final valid outputs: 2
final invalid outputs: 0
fallback used: 2
final grounded directions: 6
final ungrounded directions: 0
```

## Interview Summary

I built an evidence-grounded synthesis pipeline where LLM output is never trusted directly. The system converts retrieved evidence into evidence cards, routes to an LLM only when useful, validates the raw response for schema and source grounding, falls back deterministically when validation fails, and validates the final synthesis again before treating it as product-safe.
