#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPOSITORY_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


from execution_evidence.identity_provider_bootstrap import (  # noqa: E402
    IdentityProviderBootstrapConflictError,
    IdentityProviderBootstrapService,
    IdentityProviderBootstrapStoreError,
)


DEFAULT_DATABASE_PATH = (
    REPOSITORY_ROOT
    / "data"
    / "execution_evidence"
    / "solvyn.db"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Register the operator-controlled Google identity "
            "provider in Solvyn trusted SQLite storage."
        )
    )

    parser.add_argument(
        "--database-path",
        default=str(DEFAULT_DATABASE_PATH),
        help=(
            "Trusted Solvyn SQLite database path. "
            "The database must already be initialized."
        ),
    )
    parser.add_argument(
        "--identity-provider-id",
        required=True,
        help=(
            "Stable Solvyn identity-provider ID. "
            "It must match the ID used in "
            "SOLVYN_OIDC_PROVIDERS_JSON."
        ),
    )
    parser.add_argument(
        "--issuer",
        required=True,
        help=(
            "Exact Google OIDC issuer. "
            "It must match the issuer configured in "
            "SOLVYN_OIDC_PROVIDERS_JSON."
        ),
    )

    return parser


def main() -> int:
    args = build_parser().parse_args()

    service = IdentityProviderBootstrapService(
        Path(args.database_path)
    )

    try:
        result = service.ensure_google_provider(
            identity_provider_id=(
                args.identity_provider_id
            ),
            issuer=args.issuer,
            created_at=datetime.now(timezone.utc),
        )
    except IdentityProviderBootstrapConflictError as error:
        print(
            f"ERROR: {error}",
            file=sys.stderr,
        )
        return 2
    except IdentityProviderBootstrapStoreError as error:
        print(
            f"ERROR: {error}",
            file=sys.stderr,
        )
        return 3

    action = (
        "created"
        if result.created
        else "already registered"
    )

    print(
        "Google identity provider "
        f"{action}."
    )
    print(
        "identity_provider_id="
        f"{result.provider.identity_provider_id}"
    )
    print(
        f"issuer={result.provider.issuer}"
    )
    print(
        f"status={result.provider.status}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
