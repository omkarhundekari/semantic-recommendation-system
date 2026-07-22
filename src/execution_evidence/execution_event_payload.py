from __future__ import annotations

import re
from typing import Dict, Optional, Type

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


GITHUB_ZERO_SHA = "0" * 40
GITHUB_SHA_PATTERN = re.compile(
    r"^[0-9a-fA-F]{40}$"
)


class ExecutionEventPayload(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )


class GitHubRefUpdatedPayload(ExecutionEventPayload):
    repository_id: str = Field(min_length=1)
    ref: str = Field(min_length=1)
    before_sha: str = Field(min_length=1)
    after_sha: str = Field(min_length=1)
    created: bool = False
    deleted: bool = False
    forced: bool = False
    included_commit_count: int = Field(
        ge=0,
    )
    sender_id: str = Field(min_length=1)

    @field_validator("ref")
    @classmethod
    def validate_ref(
        cls,
        value: str,
    ) -> str:
        if not value.startswith("refs/"):
            raise ValueError(
                "GitHub ref must begin with 'refs/'."
            )

        return value

    @field_validator(
        "before_sha",
        "after_sha",
    )
    @classmethod
    def validate_sha(
        cls,
        value: str,
        info,
    ) -> str:
        if not GITHUB_SHA_PATTERN.fullmatch(value):
            raise ValueError(
                f"{info.field_name} must be a "
                "40-character hexadecimal Git SHA."
            )

        return value.lower()

    @model_validator(mode="after")
    def validate_ref_update_semantics(
        self,
    ) -> "GitHubRefUpdatedPayload":
        if self.created and self.deleted:
            raise ValueError(
                "A GitHub ref cannot be both "
                "created and deleted."
            )

        if (
            self.created
            and self.before_sha != GITHUB_ZERO_SHA
        ):
            raise ValueError(
                "A created ref must use the zero SHA "
                "as before_sha."
            )

        if (
            not self.created
            and self.before_sha == GITHUB_ZERO_SHA
        ):
            raise ValueError(
                "A non-created ref cannot use the "
                "zero SHA as before_sha."
            )

        if (
            self.deleted
            and self.after_sha != GITHUB_ZERO_SHA
        ):
            raise ValueError(
                "A deleted ref must use the zero SHA "
                "as after_sha."
            )

        if (
            not self.deleted
            and self.after_sha == GITHUB_ZERO_SHA
        ):
            raise ValueError(
                "A non-deleted ref cannot use the "
                "zero SHA as after_sha."
            )

        if (
            self.deleted
            and self.included_commit_count != 0
        ):
            raise ValueError(
                "A deleted ref cannot include commits."
            )

        return self


class GitHubDeploymentSucceededPayload(
    ExecutionEventPayload
):
    repository_id: str = Field(min_length=1)
    deployment_status_id: str = Field(min_length=1)
    sha: str = Field(min_length=1)
    ref: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    environment_url: Optional[str] = None
    sender_id: str = Field(min_length=1)

    @field_validator("sha")
    @classmethod
    def validate_sha(
        cls,
        value: str,
    ) -> str:
        if not GITHUB_SHA_PATTERN.fullmatch(value):
            raise ValueError(
                "sha must be a 40-character hexadecimal "
                "Git SHA."
            )

        return value.lower()


class GitHubWorkflowRunCompletedPayload(
    ExecutionEventPayload
):
    repository_id: str = Field(min_length=1)
    workflow_name: str = Field(min_length=1)
    run_number: int = Field(gt=0)
    head_sha: str = Field(min_length=1)
    head_branch: str = Field(min_length=1)
    conclusion: str = Field(min_length=1)
    sender_id: str = Field(min_length=1)

    @field_validator("head_sha")
    @classmethod
    def validate_head_sha(
        cls,
        value: str,
    ) -> str:
        if not GITHUB_SHA_PATTERN.fullmatch(value):
            raise ValueError(
                "head_sha must be a 40-character "
                "hexadecimal Git SHA."
            )

        return value.lower()


class GitHubReleasePublishedPayload(
    ExecutionEventPayload
):
    repository_id: str = Field(min_length=1)
    tag_name: str = Field(min_length=1)
    release_name: str = Field(min_length=1)
    sender_id: str = Field(min_length=1)


class GitHubIssueClosedPayload(
    ExecutionEventPayload
):
    repository_id: str = Field(min_length=1)
    issue_number: int = Field(gt=0)
    title: str = Field(min_length=1)
    sender_id: str = Field(min_length=1)


class GitHubPullRequestMergedPayload(
    ExecutionEventPayload
):
    repository_id: str = Field(min_length=1)
    pull_request_number: int = Field(gt=0)
    merge_commit_sha: str = Field(min_length=1)
    base_ref: str = Field(min_length=1)
    head_ref: str = Field(min_length=1)
    sender_id: str = Field(min_length=1)


EXECUTION_EVENT_PAYLOAD_REGISTRY: Dict[
    str,
    Type[ExecutionEventPayload],
] = {
    "github.ref.updated": GitHubRefUpdatedPayload,
    "github.pull_request.merged": (
        GitHubPullRequestMergedPayload
    ),
    "github.issue.closed": GitHubIssueClosedPayload,
    "github.release.published": (
        GitHubReleasePublishedPayload
    ),
    "github.workflow_run.completed": (
        GitHubWorkflowRunCompletedPayload
    ),
    "github.deployment.succeeded": (
        GitHubDeploymentSucceededPayload
    ),
}


def validate_execution_event_payload(
    *,
    event_type: str,
    payload: object,
) -> ExecutionEventPayload:
    expected_type = (
        EXECUTION_EVENT_PAYLOAD_REGISTRY.get(
            event_type
        )
    )

    if expected_type is None:
        raise ValueError(
            f"Unsupported execution event type: "
            f"{event_type}"
        )

    if type(payload) is not expected_type:
        raise TypeError(
            "Execution event payload type does not "
            f"match event type '{event_type}'."
        )

    return payload
