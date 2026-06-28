import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Union

from schemas.decision_trace_models import ProjectDecisionTrace


TRACE_OUTPUT_ENV = "WRITE_DECISION_TRACES"
DEFAULT_OUTPUT_DIR = Path("outputs/traces")


def _trace_writing_enabled() -> bool:
    value = os.getenv(TRACE_OUTPUT_ENV, "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _query_slug(query: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")
    return normalized[:60] or "project-decision-trace"


def write_decision_trace_artifact(
    query: str,
    traces: List[ProjectDecisionTrace],
    output_dir: Optional[Union[Path, str]] = None,
) -> Optional[Path]:
    if not _trace_writing_enabled():
        return None

    try:
        destination = (
            Path(output_dir)
            if output_dir is not None
            else DEFAULT_OUTPUT_DIR
        )
        destination.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_path = destination / f"{_query_slug(query)}_{timestamp}.json"

        payload = {
            "schema_version": "1.0",
            "generated_at_utc": timestamp,
            "query": query,
            "traces": [trace.model_dump() for trace in traces],
        }

        output_path.write_text(json.dumps(payload, indent=2))
        return output_path
    except OSError:
        return None
