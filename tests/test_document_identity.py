import pytest

from document_identity import build_document_id, normalize_arxiv_id


def test_normalizes_modern_arxiv_url_with_version():
    assert (
        normalize_arxiv_id("https://arxiv.org/abs/2009.08553v4")
        == "2009.08553"
    )


def test_normalizes_legacy_arxiv_url_with_version():
    assert (
        normalize_arxiv_id("https://arxiv.org/abs/cs/0112017v2")
        == "cs/0112017"
    )


def test_normalizes_bare_modern_arxiv_id():
    assert normalize_arxiv_id("2408.00884v2") == "2408.00884"


def test_returns_none_for_invalid_identifier():
    assert normalize_arxiv_id("https://example.com/paper.pdf") is None


def test_builds_namespaced_arxiv_document_id():
    assert (
        build_document_id(
            source="arXiv",
            url="https://arxiv.org/abs/2009.08553v4",
        )
        == "arxiv:2009.08553"
    )


def test_builds_future_source_id_from_external_id():
    assert (
        build_document_id(
            source="github",
            url=None,
            external_id="owner/repository",
        )
        == "github:owner/repository"
    )


def test_rejects_unknown_source_without_stable_identifier():
    with pytest.raises(ValueError):
        build_document_id(
            source="unknown",
            url=None,
        )
