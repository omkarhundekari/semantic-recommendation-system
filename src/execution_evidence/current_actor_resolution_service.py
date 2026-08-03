from __future__ import annotations

from typing import Optional

from execution_evidence.current_actor_resolution import (
    CurrentActorResolution,
)
from execution_evidence.execution_actor_identity_namespace_store import (
    ExecutionActorIdentityNamespaceNotFoundError,
    ExecutionActorIdentityNamespaceStore,
)
from execution_evidence.execution_event import (
    ExecutionEvent,
)
from execution_evidence.principal_identity_store import (
    PrincipalIdentityLinkNotFoundError,
    PrincipalIdentityStore,
)


class CurrentActorResolutionService:
    def __init__(
        self,
        *,
        namespace_store: (
            ExecutionActorIdentityNamespaceStore
        ),
        principal_identity_store: PrincipalIdentityStore,
    ) -> None:
        self._namespace_store = namespace_store
        self._principal_identity_store = (
            principal_identity_store
        )

    def resolve(
        self,
        event: ExecutionEvent,
    ) -> Optional[CurrentActorResolution]:
        actor_id = event.actor_id

        if actor_id is None or actor_id == "":
            return None

        # External actor identity is exact-match only.
        # Never trim, case-fold, prefix-strip, or alias it.
        if actor_id != actor_id.strip():
            return None

        try:
            namespace = (
                self._namespace_store
                .load_current_by_source_provider(
                    event.source_provider
                )
            )
        except (
            ExecutionActorIdentityNamespaceNotFoundError
        ):
            return None

        # Current resolution must never use retired
        # namespace history, even if a custom store
        # violates the current-only lookup contract.
        if namespace.retired_at is not None:
            return None

        try:
            link = (
                self._principal_identity_store
                .load_active_link(
                    issuer=namespace.issuer,
                    subject=actor_id,
                )
            )
        except PrincipalIdentityLinkNotFoundError:
            return None

        return CurrentActorResolution(
            principal_id=link.principal_id,
            identity_link_id=link.link_id,
            execution_actor_namespace_id=(
                namespace.execution_actor_namespace_id
            ),
            issuer=namespace.issuer,
            subject=actor_id,
        )
