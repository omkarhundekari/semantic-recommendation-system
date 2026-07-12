# Solvyn

[![Frontend CI](https://github.com/omkarhundekari/semantic-recommendation-system/actions/workflows/frontend-ci.yml/badge.svg)](https://github.com/omkarhundekari/semantic-recommendation-system/actions/workflows/frontend-ci.yml)
[![Backend CI](https://github.com/omkarhundekari/semantic-recommendation-system/actions/workflows/backend-ci.yml/badge.svg)](https://github.com/omkarhundekari/semantic-recommendation-system/actions/workflows/backend-ci.yml)

**A Research-to-Prototype Intelligence Engine**

Solvyn turns technical goals and research evidence into grounded, buildable software projects with execution roadmaps, proof-driven progress, technical decision capture, and portfolio-ready outputs.

## Core Workflow

```text
User goal
  → query understanding
  → research and implementation evidence retrieval
  → evidence coverage and confidence assessment
  → project direction generation
  → domain-aware execution roadmap
  → guided proof and technical decision capture
  → Build Passport, README outline, and interview story
```

## Backend Setup

Create and activate a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

Install runtime and development dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

Run the backend test suite:

```bash
python -m pytest -q
```

The generated GitHub implementation corpus is optional. When `data/github_project_corpus.csv` is unavailable, Solvyn continues using research-paper and project-pattern evidence.

## Frontend Setup

Install dependencies:

```bash
cd frontend
npm ci
```

Start the development server:

```bash
npm run dev
```

Run frontend quality checks:

```bash
npm test
npm run lint
npx tsc --noEmit
npm run build
```

## Quality Gates

GitHub Actions runs separate backend and frontend workflows on relevant pushes and pull requests.

The backend workflow uses Python 3.11, installs `requirements-dev.txt`, and runs the complete pytest suite.

The frontend workflow uses Node.js 24 and runs Vitest, ESLint, TypeScript, and the Next.js production build.

## Local Data and Secrets

Generated corpora, runtime outputs, environment files, and API keys remain local and must not be committed. OpenAI-backed synthesis is isolated behind provider interfaces, while tests use fake providers and clients to avoid live API charges.

## Evaluation and LLM Synthesis Architecture

This project separates evidence retrieval, evidence curation, LLM synthesis, and output validation into independently testable layers. The goal is not to treat LLM output as automatically correct, but to make every generated project direction auditable.

### Evidence Cards

Retrieved research papers and implementation references are compressed into structured evidence cards. Each card preserves source identity, support scope, evidence confidence, implementation signals, grounding warnings, and user-facing explanations. Raw retrieval noise, review labels, oracle labels, and internal comparison artifacts are not passed into the LLM.

### Value-Based Routing

The system decides whether LLM synthesis is useful before considering cost. Routing uses evidence quality signals such as query-aligned source count, evidence confidence, weak or suspicious relevance, and grounding adequacy.

Fast mode keeps the deterministic output path. Deep and interview modes can route to LLM synthesis when evidence is strong enough. Exploratory or no-query-aligned cases are blocked instead of forcing a model response.

### Structured Prompt Contract

LLM prompts are built from user goals, constraints, curated evidence cards, a required output schema, and grounding rules. The LLM is instructed to cite only source IDs that appear in the evidence cards, preserve uncertainty, avoid invented claims, and return valid JSON only.

### Token Estimation

Token estimation runs on the actual structured prompt, not a loose word-count approximation. Readiness reports show estimated prompt tokens, largest prompt sections, routing decisions, and reasons before any real API call is made.

### OpenAI Synthesis Provider

The OpenAI integration is behind a provider interface. Tests use fake providers and fake clients, so the pipeline can be validated without spending API credits. The active model is resolved from environment configuration, and API keys are never committed.

### Saved Output Validation

LLM responses are not accepted blindly. Saved synthesis outputs are validated for parsed structured responses, empty response warnings, valid source IDs, no invented citations, valid confidence labels, preserved routing metadata, and preserved token estimates.

During development, a real truncated response was caught when the output token budget was too low. A sanitized invalid sample is committed as a regression fixture to prove the validator detects this failure mode.

### Curated Sample Fixtures

Committed samples live in data/sample_llm_synthesis_outputs/.

These are curated validator fixtures, not raw API logs:

- valid_synthesis_sample.json demonstrates a successful grounded synthesis output.
- invalid_truncated_sample.json demonstrates a truncated response that the validator rejects.

Real runtime outputs are saved locally under outputs/llm_synthesis_runs/ and are ignored by Git. This keeps the repository stable while preserving local auditability.
