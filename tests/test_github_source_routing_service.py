from __future__ import annotations

from datetime import datetime, timezone

import pytest

from execution_evidence.github_source_binding import (
    GitHubSourceBinding,
    create_github_source_binding_id,
)
from execution_evidence.github_source_binding_store import (
    GitHubSourceBindingNotFoundError,
    GitHubSourceBindingStoreError,
)
from execution_evidence.github_source_routing_service import (
    GitHubSourceRoutingNotFoundError,
    GitHubSourceRoutingService,
    GitHubSourceRoutingStoreError,
)


NOW = datetime(
    2026,
    8,
    3,
    12,
    0,
    tzinfo=timezone.utc,
)


def _binding(
    *,
    repository_id: str = "1001",
    workspace_id: str = "workspace-a",
    project_id: str = "project-a",
    retired_at=None,
    retired_reason=None,
) -> GitHubSourceBinding:
    return GitHubSourceBinding(
        github_source_binding_id=(
            create_github_source_binding_id()
        ),
        repository_id=repository_id,
        installation_id="2001",
        workspace_id=workspace_id,
        project_id=project_id,
        created_at=NOW,
        retired_at=retired_at,
        retired_reason=retired_reason,
    )


class _BindingStore:
    def __init__(
        self,
        binding: GitHubSourceBinding,
    ) -> None:
        self.binding = binding
        self.repository_ids = []

    def load_current_by_repository_id(
        self,
        repository_id: str,
    ) -> GitHubSourceBinding:
        self.repository_ids.append(repository_id)

        if repository_id != self.binding.repository_id:
            raise GitHubSourceBindingNotFoundError(
                "not found"
            )

        return self.binding


def test_resolves_explicit_workspace_and_project():
    binding = _binding(
        repository_id="1001",
        workspace_id="workspace-b",
        project_id="project-z",
    )
    store = _BindingStore(binding)

    route = GitHubSourceRoutingService(
        binding_store=store
    ).resolve("1001")

    assert route.repository_id == "1001"
    assert route.workspace_id == "workspace-b"
    assert route.project_id == "project-z"
    assert route.github_source_binding_id == (
        binding.github_source_binding_id
    )


def test_repository_identity_is_passed_exactly():
    store = _BindingStore(_binding())

    service = GitHubSourceRoutingService(
        binding_store=store
    )

    with pytest.raises(
        GitHubSourceRoutingNotFoundError,
    ):
        service.resolve(" 1001 ")

    assert store.repository_ids == [
        " 1001 ",
    ]


def test_unknown_repository_fails_closed():
    service = GitHubSourceRoutingService(
        binding_store=_BindingStore(
            _binding(repository_id="1001")
        )
    )

    with pytest.raises(
        GitHubSourceRoutingNotFoundError,
    ):
        service.resolve("9999")


def test_route_never_falls_back_to_local():
    route = GitHubSourceRoutingService(
        binding_store=_BindingStore(
            _binding(
                workspace_id="workspace-secure",
                project_id="project-secure",
            )
        )
    ).resolve("1001")

    assert route.workspace_id == (
        "workspace-secure"
    )
    assert route.workspace_id != "local"


def test_retired_binding_is_rejected_defensively():
    binding = _binding(
        retired_at=NOW,
        retired_reason="repository moved",
    )

    service = GitHubSourceRoutingService(
        binding_store=_BindingStore(binding)
    )

    with pytest.raises(
        GitHubSourceRoutingNotFoundError,
    ):
        service.resolve("1001")


def test_binding_store_failure_is_not_unresolved():
    class FailingStore:
        def load_current_by_repository_id(
            self,
            repository_id: str,
        ):
            raise GitHubSourceBindingStoreError(
                "database unavailable"
            )

    service = GitHubSourceRoutingService(
        binding_store=FailingStore()
    )

    with pytest.raises(
        GitHubSourceRoutingStoreError,
    ):
        service.resolve("1001")


@pytest.mark.parametrize(
    "repository_id",
    [
        "",
        None,
        1001,
    ],
)
def test_invalid_repository_identity_is_rejected(
    repository_id,
):
    service = GitHubSourceRoutingService(
        binding_store=_BindingStore(
            _binding()
        )
    )

    with pytest.raises(ValueError):
        service.resolve(repository_id)
