from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from execution_evidence.github_source_binding import (
    GitHubSourceBinding,
    create_github_source_binding_id,
)


NOW = datetime(
    2026,
    8,
    3,
    20,
    0,
    tzinfo=timezone.utc,
)
LATER = NOW + timedelta(minutes=5)


def _binding(
    *,
    binding_id: str | None = None,
    repository_id: str = "123456789",
    installation_id: str | None = None,
    workspace_id: str = "workspace-test",
    project_id: str = "project-test",
    retired_at=None,
    retired_reason=None,
) -> GitHubSourceBinding:
    return GitHubSourceBinding(
        github_source_binding_id=(
            binding_id
            or create_github_source_binding_id()
        ),
        repository_id=repository_id,
        installation_id=installation_id,
        workspace_id=workspace_id,
        project_id=project_id,
        created_at=NOW,
        retired_at=retired_at,
        retired_reason=retired_reason,
    )


def test_binding_is_immutable():
    binding = _binding()

    with pytest.raises(ValidationError):
        binding.project_id = "other-project"


def test_binding_accepts_current_state():
    binding = _binding()

    assert binding.repository_id == "123456789"
    assert binding.installation_id is None
    assert binding.retired_at is None
    assert binding.retired_reason is None


def test_binding_accepts_optional_installation_id():
    binding = _binding(
        installation_id="987654321",
    )

    assert binding.installation_id == "987654321"


def test_binding_accepts_retired_history():
    binding = _binding(
        retired_at=LATER,
        retired_reason="project reorganization",
    )

    assert binding.retired_at == LATER
    assert (
        binding.retired_reason
        == "project reorganization"
    )


def test_binding_rejects_bad_binding_prefix():
    with pytest.raises(
        ValidationError,
        match="must start with",
    ):
        _binding(
            binding_id=f"bad_{uuid4()}",
        )


def test_binding_rejects_noncanonical_binding_uuid():
    binding_id = (
        "gsb_"
        + str(uuid4()).upper()
    )

    with pytest.raises(
        ValidationError,
        match="canonical UUID4",
    ):
        _binding(
            binding_id=binding_id,
        )


@pytest.mark.parametrize(
    "repository_id",
    [
        "",
        " repository-1 ",
        "repo-1",
        "123.0",
        "+123",
        "-123",
        "１２３",
        "00123",
        "0",
    ],
)
def test_repository_id_requires_exact_canonical_numeric_identity(
    repository_id: str,
):
    with pytest.raises(ValidationError):
        _binding(
            repository_id=repository_id,
        )


def test_repository_id_preserves_exact_value():
    binding = _binding(
        repository_id="123456789",
    )

    assert binding.repository_id == "123456789"


@pytest.mark.parametrize(
    "installation_id",
    [
        "",
        " 123 ",
        "installation-123",
        "00123",
        "0",
    ],
)
def test_installation_id_requires_canonical_numeric_identity(
    installation_id: str,
):
    with pytest.raises(ValidationError):
        _binding(
            installation_id=installation_id,
        )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("workspace_id", " workspace-test "),
        ("project_id", " project-test "),
    ],
)
def test_scope_identity_rejects_surrounding_whitespace(
    field_name: str,
    value: str,
):
    values = {
        field_name: value,
    }

    with pytest.raises(ValidationError):
        _binding(**values)


def test_binding_requires_created_at_timezone():
    naive = NOW.replace(tzinfo=None)

    with pytest.raises(
        ValidationError,
        match="timezone-aware",
    ):
        GitHubSourceBinding(
            github_source_binding_id=(
                create_github_source_binding_id()
            ),
            repository_id="123",
            installation_id=None,
            workspace_id="workspace-test",
            project_id="project-test",
            created_at=naive,
        )


def test_binding_requires_retired_at_timezone():
    naive = LATER.replace(tzinfo=None)

    with pytest.raises(
        ValidationError,
        match="timezone-aware",
    ):
        _binding(
            retired_at=naive,
            retired_reason="retired",
        )


def test_current_binding_rejects_retirement_reason():
    with pytest.raises(
        ValidationError,
        match="cannot contain a retirement reason",
    ):
        _binding(
            retired_reason="retired",
        )


def test_retired_binding_requires_reason():
    with pytest.raises(
        ValidationError,
        match="require a retirement reason",
    ):
        _binding(
            retired_at=LATER,
        )


def test_retired_reason_is_normalized():
    binding = _binding(
        retired_at=LATER,
        retired_reason="  project moved  ",
    )

    assert binding.retired_reason == "project moved"


def test_blank_retired_reason_is_rejected():
    with pytest.raises(
        ValidationError,
        match="require a retirement reason",
    ):
        _binding(
            retired_at=LATER,
            retired_reason="   ",
        )


def test_retired_at_cannot_precede_created_at():
    with pytest.raises(
        ValidationError,
        match="cannot precede created_at",
    ):
        _binding(
            retired_at=NOW - timedelta(seconds=1),
            retired_reason="invalid",
        )


def test_generated_binding_ids_are_distinct():
    first = create_github_source_binding_id()
    second = create_github_source_binding_id()

    assert first != second

    for value in (first, second):
        assert value.startswith("gsb_")
        parsed = UUID(value[len("gsb_"):])
        assert parsed.version == 4


def test_same_repository_can_have_distinct_historical_binding_models():
    first = _binding(
        retired_at=LATER,
        retired_reason="moved projects",
    )
    second = _binding(
        project_id="project-two",
    )

    assert first.repository_id == second.repository_id
    assert (
        first.github_source_binding_id
        != second.github_source_binding_id
    )


def test_multiple_repositories_can_bind_same_project():
    first = _binding(
        repository_id="1001",
    )
    second = _binding(
        repository_id="1002",
    )

    assert first.project_id == second.project_id
    assert first.repository_id != second.repository_id
