from planning.evidence_brief import build_evidence_brief
from planning.live_evidence_cards import (
    build_live_evidence_card_payload_from_brief,
    build_live_evidence_cards_from_brief,
)


def test_builds_live_evidence_cards_from_research_brief():
    brief = build_evidence_brief(
        evidence_items=[
            {
                "document_id": "paper-rag-eval",
                "source_type": "research_paper",
                "title": "RAG Evaluation for Question Answering",
                "abstract": (
                    "Retrieval augmented generation systems need evaluation "
                    "for question answering, faithfulness, and citation quality."
                ),
                "support_scope": "direct",
                "category": "cs.IR",
            },
            {
                "document_id": "paper-rag-retrieval",
                "source_type": "research_paper",
                "title": "Retrieval Quality in RAG",
                "abstract": (
                    "Retrieval quality affects answer quality in RAG systems."
                ),
                "support_scope": "direct",
                "category": "cs.IR",
            },
        ],
        user_query="Build a RAG evaluation project for question answering",
    )

    cards = build_live_evidence_cards_from_brief(brief)

    assert len(cards) == 2
    assert cards[0].source_id == "paper-rag-eval"
    assert cards[0].source_type == "research_paper"
    assert cards[0].support_scope == "direct"
    assert cards[0].evidence_confidence == "Strong"
    assert cards[0].relevance_signal == "plausible"
    assert cards[0].grounding_warning is None


def test_live_cards_mark_implementation_only_evidence_as_limited():
    brief = build_evidence_brief(
        evidence_items=[
            {
                "repository_id": "repo-rag-dashboard",
                "source_type": "github_repository",
                "title": "RAG Dashboard Repository",
                "readme_excerpt": (
                    "A FastAPI and React dashboard for inspecting retrieval "
                    "and answer quality."
                ),
                "support_scope": "direct",
            }
        ],
        user_query="Build a RAG dashboard",
    )

    cards = build_live_evidence_cards_from_brief(brief)

    assert len(cards) == 1
    assert cards[0].source_id == "repo-rag-dashboard"
    assert cards[0].evidence_confidence == "Limited"
    assert cards[0].grounding_warning == "implementation_only_evidence"
    assert cards[0].specific_implementation_signal in {
        "dashboard",
        "fastapi",
        "react",
    }


def test_live_card_payload_is_json_ready():
    brief = build_evidence_brief(
        evidence_items=[
            {
                "source_id": "paper-lineage",
                "source_type": "research_paper",
                "title": "Data Lineage for Incident Triage",
                "abstract": "Lineage helps teams debug data quality incidents.",
                "support_scope": "direct",
            }
        ],
        user_query="Build a data lineage incident triage project",
    )

    payload = build_live_evidence_card_payload_from_brief(brief)

    assert payload["query"] == "Build a data lineage incident triage project"
    assert payload["card_count"] == 1
    assert payload["evidence_cards"][0]["source_id"] == "paper-lineage"
    assert payload["evidence_cards"][0]["support_scope"] == "direct"
