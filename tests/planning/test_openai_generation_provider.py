import json
from types import SimpleNamespace

import pytest

from planning.openai_generation_provider import (
    OpenAICandidateGenerationProvider,
)


def valid_response():
    return {
        "candidates": [
            {
                "title": "Evidence-Grounded RAG Evaluator",
                "problem_statement": "RAG outputs need transparent evaluation.",
                "target_user": "ML engineers",
                "core_workflow": [
                    "Load retrieved context and generated answers.",
                    "Measure citation coverage and answer support.",
                ],
                "mvp_scope": [
                    "Load a small evaluation dataset.",
                    "Score citation coverage.",
                    "Show answer-level warnings.",
                ],
                "success_metrics": [
                    "Citation coverage across evaluation examples.",
                ],
                "evidence_relationship": (
                    "Uses only source IDs supplied in the evidence brief."
                ),
                "source_ids": ["paper-1"],
                "assumptions": ["Use a local evaluation dataset."],
                "suggested_stack": ["Python", "FastAPI"],
            },
            {
                "title": "Retrieval Failure Analysis Console",
                "problem_statement": "Teams need to inspect weak retrieval results.",
                "target_user": "LLM application engineers",
                "core_workflow": [
                    "Run sample queries against a retrieval index.",
                    "Inspect retrieved context and failure patterns.",
                ],
                "mvp_scope": [
                    "Load sample queries.",
                    "Display retrieved chunks.",
                    "Flag weak retrieval coverage.",
                ],
                "success_metrics": [
                    "Percentage of queries with useful retrieved context.",
                ],
                "evidence_relationship": (
                    "Uses only source IDs supplied in the evidence brief."
                ),
                "source_ids": ["paper-1"],
                "assumptions": ["Use a small local corpus."],
                "suggested_stack": ["Python", "Streamlit"],
            },
            {
                "title": "RAG Quality Trace Dashboard",
                "problem_statement": "Developers need one place to inspect RAG quality.",
                "target_user": "AI engineers",
                "core_workflow": [
                    "Collect retrieval and answer traces.",
                    "Compare quality signals across requests.",
                ],
                "mvp_scope": [
                    "Store sample traces.",
                    "Render quality summaries.",
                    "Show source-linked evidence details.",
                ],
                "success_metrics": [
                    "Time required to diagnose low-quality responses.",
                ],
                "evidence_relationship": (
                    "Uses only source IDs supplied in the evidence brief."
                ),
                "source_ids": ["paper-1"],
                "assumptions": ["Use synthetic traces initially."],
                "suggested_stack": ["Python", "FastAPI"],
            },
        ]
    }


class FakeResponses:
    def __init__(self, output_text):
        self.output_text = output_text
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            output_text=self.output_text,
            usage=SimpleNamespace(
                input_tokens=120,
                output_tokens=340,
                total_tokens=460,
            ),
        )


class FakeClient:
    def __init__(self, output_text):
        self.responses = FakeResponses(output_text)


def test_openai_provider_returns_json_and_records_usage():
    fake_client = FakeClient(json.dumps(valid_response()))
    provider = OpenAICandidateGenerationProvider(
        model="test-model",
        max_output_tokens=2500,
        timeout_seconds=35,
        client=fake_client,
    )

    result = provider.generate("Generate candidates.")

    assert result == valid_response()
    assert provider.last_usage == {
        "input_tokens": 120,
        "output_tokens": 340,
        "total_tokens": 460,
    }

    request = fake_client.responses.calls[0]
    assert request["model"] == "test-model"
    assert request["max_output_tokens"] == 2500
    assert request["store"] is False
    assert request["text"]["format"]["type"] == "json_schema"
    assert request["text"]["format"]["strict"] is True


def test_openai_provider_rejects_non_json_output():
    provider = OpenAICandidateGenerationProvider(
        model="test-model",
        client=FakeClient("not-json"),
    )

    with pytest.raises(RuntimeError, match="not valid JSON"):
        provider.generate("Generate candidates.")
