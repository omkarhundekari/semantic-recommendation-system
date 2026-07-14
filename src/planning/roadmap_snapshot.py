from __future__ import annotations

import hashlib
import json
from typing import List

from pydantic import BaseModel, Field

from schemas.product_models import RoadmapStage


ROADMAP_SNAPSHOT_VERSION = 1
ROADMAP_CANONICALIZATION_VERSION = 1


class RoadmapStageSnapshot(BaseModel):
    stage_id: str = Field(min_length=1)
    position: int = Field(ge=0)
    content_hash: str = Field(
        min_length=64,
        max_length=64,
    )
    content: dict


class RoadmapSnapshot(BaseModel):
    snapshot_version: int = ROADMAP_SNAPSHOT_VERSION
    canonicalization_version: int = (
        ROADMAP_CANONICALIZATION_VERSION
    )
    roadmap_hash: str = Field(
        min_length=64,
        max_length=64,
    )
    stages: List[RoadmapStageSnapshot]


def build_roadmap_snapshot(
    stages: List[RoadmapStage],
) -> RoadmapSnapshot:
    stage_ids = [stage.id.strip() for stage in stages]

    if any(not stage_id for stage_id in stage_ids):
        raise ValueError(
            "Roadmap stages must have non-empty IDs."
        )

    if len(stage_ids) != len(set(stage_ids)):
        raise ValueError(
            "Roadmap stage IDs must be unique."
        )

    stage_snapshots = [
        _build_stage_snapshot(
            stage=stage,
            position=position,
        )
        for position, stage in enumerate(stages)
    ]

    roadmap_payload = {
        "snapshot_version": ROADMAP_SNAPSHOT_VERSION,
        "canonicalization_version": (
            ROADMAP_CANONICALIZATION_VERSION
        ),
        "stages": [
            {
                "stage_id": snapshot.stage_id,
                "position": snapshot.position,
                "content_hash": snapshot.content_hash,
            }
            for snapshot in stage_snapshots
        ],
    }

    return RoadmapSnapshot(
        roadmap_hash=_hash_payload(roadmap_payload),
        stages=stage_snapshots,
    )


def _build_stage_snapshot(
    *,
    stage: RoadmapStage,
    position: int,
) -> RoadmapStageSnapshot:
    content = stage.model_dump(
        mode="json",
        exclude_none=False,
    )

    return RoadmapStageSnapshot(
        stage_id=stage.id.strip(),
        position=position,
        content_hash=_hash_payload(content),
        content=content,
    )


def _hash_payload(payload: object) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()
