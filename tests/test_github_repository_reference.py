import pytest

from execution_evidence.github_repository import (
    parse_github_repository_url,
)


@pytest.mark.parametrize(
    ("value", "expected_url"),
    [
        (
            "https://github.com/Owner/Repository",
            "https://github.com/Owner/Repository",
        ),
        (
            "https://github.com/Owner/Repository.git",
            "https://github.com/Owner/Repository",
        ),
        (
            "git@github.com:Owner/Repository.git",
            "https://github.com/Owner/Repository",
        ),
        (
            "ssh://git@github.com/Owner/Repository.git",
            "https://github.com/Owner/Repository",
        ),
    ],
)
def test_parse_github_repository_url_normalizes_supported_forms(
    value,
    expected_url,
):
    reference = parse_github_repository_url(value)

    assert reference.owner == "Owner"
    assert reference.repository == "Repository"
    assert reference.canonical_url == expected_url
    assert reference.repository_key == (
        "github:owner/repository"
    )


@pytest.mark.parametrize(
    "value",
    [
        "",
        "https://gitlab.com/owner/repository",
        "github.com/owner/repository",
        "https://github.com/owner",
        "https://github.com/owner/repository/issues",
    ],
)
def test_parse_github_repository_url_rejects_invalid_references(
    value,
):
    with pytest.raises(ValueError):
        parse_github_repository_url(value)
