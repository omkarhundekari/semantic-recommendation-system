from __future__ import annotations

import pytest
from pydantic import ValidationError

from execution_evidence.authorized_project_context import (
    AuthorizedProjectContext,
)


PRINCIPAL_ID = (
    "prn_123e4567-e89b-42d3-a456-426614174000"
)
MEMBERSHIP_ID = (
    "wsm_123e4567-e89b-42d3-a456-426614174001"
)


def _context(**changes):
    values = {
        "principal_id": PRINCIPAL_ID,
        "membership_id": MEMBERSHIP_ID,
        "workspace_id": "workspace-one",
        "project_id": "proj-shared",
    }
    values.update(changes)
    return AuthorizedProjectContext(**values)


def test_authorized_project_context_is_immutable():
    context = _context()

    with pytest.raises(ValidationError):
        context.project_id = "other-project"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("principal_id", "prn_bad"),
        ("membership_id", "wsm_bad"),
        ("workspace_id", ""),
        ("project_id", ""),
        ("workspace_id", " workspace-one "),
        ("project_id", " proj-shared "),
    ],
)
def test_authorized_project_context_rejects_invalid_scope(
    field,
    value,
):
    with pytest.raises(ValidationError):
        _context(**{field: value})



def test_authorized_project_context_defaults_to_unassigned_role():
    context = _context()

    assert context.membership_role is None


def test_authorized_project_context_preserves_membership_role():
    context = _context(
        membership_role="owner"
    )

    assert context.membership_role == "owner"


def test_authorized_project_context_rejects_unknown_role():
    with pytest.raises(ValidationError):
        _context(
            membership_role="superuser"
        )
