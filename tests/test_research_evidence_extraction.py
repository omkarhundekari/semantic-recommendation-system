from research_evidence_extraction import extract_research_evidence


def test_extracts_traceable_signals_from_rag_paper():
    paper = {
        "document_id": "arxiv:2403.01234",
        "title": "Improving Retrieval-Augmented Generation for Question Answering",
        "abstract": (
            "We propose a retrieval method for retrieval-augmented generation "
            "systems used in open-domain question answering. Our experiments "
            "compare retrieval quality against baseline methods on benchmark datasets."
        ),
        "category": "cs.IR",
    }

    result = extract_research_evidence(paper)

    assert result["document_id"] == "arxiv:2403.01234"
    assert result["title"] == paper["title"]

    assert "method" in result["evidence_tags"]
    assert "application" in result["evidence_tags"]
    assert "benchmark" in result["evidence_tags"]

    assert "retrieval" in result["signals"]["methods"]
    assert "question_answering" in result["signals"]["applications"]
    assert "benchmarks" in result["signals"]["evaluation"]

    assert result["matched_phrases"]["retrieval"]
    assert result["evidence_snippets"]


def test_returns_empty_evidence_for_unmatched_paper():
    paper = {
        "document_id": "arxiv:2501.00001",
        "title": "A General Mathematical Note",
        "abstract": "We study an abstract algebraic construction.",
        "category": "math.GM",
    }

    result = extract_research_evidence(paper)

    assert result["evidence_tags"] == []
    assert result["signals"] == {
        "methods": [],
        "datasets": [],
        "benchmarks": [],
        "limitations": [],
        "applications": [],
        "implementation": [],
        "risks": [],
        "trends": [],
        "evaluation": [],
    }
    assert result["matched_phrases"] == {}
    assert result["evidence_snippets"] == []


def test_extracts_named_datasets_and_comparison_evidence():
    paper = {
        "document_id": "arxiv:2009.08553",
        "title": "Generation-Augmented Retrieval for Open-domain Question Answering",
        "abstract": (
            "We demonstrate that retrieval accuracy improves compared with "
            "state-of-the-art dense retrieval methods. GAR achieves state-of-the-art "
            "performance on Natural Questions and TriviaQA datasets and consistently "
            "outperforms other retrieval methods."
        ),
        "category": "cs.CL",
    }

    result = extract_research_evidence(paper)

    assert "natural_questions" in result["signals"]["datasets"]
    assert "triviaqa" in result["signals"]["datasets"]
    assert "comparisons" in result["signals"]["evaluation"]
    assert "benchmark" in result["evidence_tags"]


def test_keeps_snippets_specific_to_each_signal():
    paper = {
        "document_id": "arxiv:3333.33333",
        "title": "A Retrieval Classification System",
        "abstract": (
            "We use classification to route user requests. "
            "Our retrieval method improves question answering."
        ),
        "category": "cs.IR",
    }

    result = extract_research_evidence(paper)

    assert "classification" in result["signal_snippets"]
    assert result["signal_snippets"]["classification"] == [
        "We use classification to route user requests."
    ]

    assert "retrieval" in result["signal_snippets"]
    assert result["signal_snippets"]["retrieval"] == [
        "Our retrieval method improves question answering."
    ]


def test_distinguishes_named_datasets_from_generic_dataset_mentions():
    paper = {
        "document_id": "arxiv:4444.44444",
        "title": "A Retrieval Study",
        "abstract": (
            "We evaluate on a corpus of documents and report results on a dataset. "
            "No named benchmark is provided."
        ),
        "category": "cs.IR",
    }

    result = extract_research_evidence(paper)

    assert "dataset_mentions" in result["signals"]["datasets"]
    assert "natural_questions" not in result["signals"]["datasets"]
    assert "triviaqa" not in result["signals"]["datasets"]
    assert "dataset" not in result["evidence_tags"]
