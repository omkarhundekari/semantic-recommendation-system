import pytest

from research_records import build_research_record


def test_builds_canonical_research_record():
    paper = {
        "document_id": "arxiv:2009.08553",
        "title": "Generation-Augmented Retrieval",
        "content": "A paper abstract.",
        "category": "cs.CL",
        "authors": "Example Author",
        "published": "2020-09-17T23:08:01Z",
        "url": "https://arxiv.org/abs/2009.08553v4",
        "source": "arXiv",
    }

    result = build_research_record(paper, index=12)

    assert result["document_id"] == "arxiv:2009.08553"
    assert result["index"] == 12
    assert result["title"] == "Generation-Augmented Retrieval"
    assert result["content"] == "A paper abstract."
    assert result["abstract"] == "A paper abstract."
    assert result["category"] == "cs.CL"


def test_uses_safe_defaults_for_optional_metadata():
    paper = {
        "document_id": "arxiv:2408.00884",
        "title": "",
        "content": None,
        "category": None,
        "authors": None,
        "published": None,
        "url": None,
        "source": None,
    }

    result = build_research_record(paper, index=3)

    assert result["title"] == "Untitled Paper"
    assert result["content"] == ""
    assert result["abstract"] == ""
    assert result["category"] == "Unknown Category"
    assert result["authors"] == ""
    assert result["url"] == ""


def test_rejects_missing_stable_document_id():
    with pytest.raises(ValueError, match="document_id"):
        build_research_record(
            {
                "title": "Missing ID Paper",
                "content": "Example content",
            },
            index=0,
        )
