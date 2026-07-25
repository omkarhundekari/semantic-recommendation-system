from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from execution_evidence.store_migration import (
    MIGRATION_RECEIPT_VERSION,
    MIGRATION_RECEIPT_V2_VERSION,
    RepositoryEvidenceMigrationReceipt,
    calculate_migration_receipt_content_digest,
    calculate_migration_receipt_id,
)


def _validate_trusted_store_receipt(
    receipt: RepositoryEvidenceMigrationReceipt,
) -> bool:
    # Resolve lazily so trusted_store can re-export this
    # module without creating an import-time cycle.
    from execution_evidence.trusted_store import (
        validate_trusted_store_receipt,
    )

    return validate_trusted_store_receipt(receipt)


class TrustedReceiptChainFailureCode(
    str,
    Enum,
):
    CHAIN_NOT_ESTABLISHED = "chain_not_established"
    RECEIPT_LIMIT_EXCEEDED = "receipt_limit_exceeded"
    DUPLICATE_ID = "duplicate_id"
    NO_TIP = "no_tip"
    MULTIPLE_TIPS = "multiple_tips"
    TIP_SCHEMA_DESYNC = "tip_schema_desync"
    MISSING_PREDECESSOR = "missing_predecessor"
    CYCLE = "cycle"
    DISCONNECTED_RECEIPT = "disconnected_receipt"
    UNKNOWN_VERSION = "unknown_version"
    KIND_INVARIANT = "kind_invariant"
    ILLEGAL_TRANSITION = "illegal_transition"
    ID_MISMATCH = "id_mismatch"
    SCHEMA_DISCONTINUITY = "schema_discontinuity"
    EPOCH_DISCONTINUITY = "epoch_discontinuity"


@dataclass(frozen=True)
class TrustedReceiptChainFailure:
    code: TrustedReceiptChainFailureCode
    detail: str
    offending_receipt_id: str | None = None
    predecessor_receipt_id: str | None = None
    successor_receipt_id: str | None = None


@dataclass(frozen=True)
class TrustedReceiptChainValidationResult:
    valid: bool
    authoritative_tip: str | None
    lineage_epoch: int | None
    chain_length: int
    failure: TrustedReceiptChainFailure | None = None


MAX_TRUSTED_RECEIPT_CHAIN_ROWS = 1_000_000


def _trusted_receipt_chain_failure(
    code: TrustedReceiptChainFailureCode,
    detail: str,
    *,
    chain_length: int = 0,
    authoritative_tip: str | None = None,
    lineage_epoch: int | None = None,
    offending_receipt_id: str | None = None,
    predecessor_receipt_id: str | None = None,
    successor_receipt_id: str | None = None,
) -> TrustedReceiptChainValidationResult:
    return TrustedReceiptChainValidationResult(
        valid=False,
        authoritative_tip=authoritative_tip,
        lineage_epoch=lineage_epoch,
        chain_length=chain_length,
        failure=TrustedReceiptChainFailure(
            code=code,
            detail=detail,
            offending_receipt_id=(
                offending_receipt_id
            ),
            predecessor_receipt_id=(
                predecessor_receipt_id
            ),
            successor_receipt_id=(
                successor_receipt_id
            ),
        ),
    )


def validate_trusted_receipt_chain(
    receipts: Sequence[
        RepositoryEvidenceMigrationReceipt
    ],
    *,
    user_version: int,
    maximum_receipts: int = (
        MAX_TRUSTED_RECEIPT_CHAIN_ROWS
    ),
) -> TrustedReceiptChainValidationResult:
    receipt_rows = tuple(receipts)

    if user_version < 0:
        raise ValueError(
            "user_version must be non-negative."
        )

    if maximum_receipts < 1:
        raise ValueError(
            "maximum_receipts must be positive."
        )

    if len(receipt_rows) > maximum_receipts:
        return _trusted_receipt_chain_failure(
            TrustedReceiptChainFailureCode
            .RECEIPT_LIMIT_EXCEEDED,
            (
                "Receipt count exceeds the configured "
                "chain-validation limit."
            ),
        )

    if not receipt_rows:
        return _trusted_receipt_chain_failure(
            TrustedReceiptChainFailureCode
            .CHAIN_NOT_ESTABLISHED,
            "No trusted-store receipts are present.",
        )

    receipts_by_id = {}

    for receipt in receipt_rows:
        if receipt.receipt_id in receipts_by_id:
            return _trusted_receipt_chain_failure(
                TrustedReceiptChainFailureCode
                .DUPLICATE_ID,
                (
                    "Multiple loaded rows use the same "
                    "receipt identifier."
                ),
                offending_receipt_id=receipt.receipt_id,
            )

        receipts_by_id[receipt.receipt_id] = receipt

    referenced_ids = {
        receipt.predecessor_receipt_id
        for receipt in receipt_rows
        if receipt.predecessor_receipt_id is not None
    }

    tips = [
        receipt
        for receipt in receipt_rows
        if receipt.receipt_id not in referenced_ids
    ]

    if not tips:
        return _trusted_receipt_chain_failure(
            TrustedReceiptChainFailureCode.NO_TIP,
            (
                "No structural receipt tip exists. "
                "The lineage may contain a cycle."
            ),
        )

    if len(tips) != 1:
        return _trusted_receipt_chain_failure(
            TrustedReceiptChainFailureCode
            .MULTIPLE_TIPS,
            (
                "The receipt set contains multiple "
                "disconnected structural tips."
            ),
        )

    tip = tips[0]

    if tip.receipt_version == MIGRATION_RECEIPT_VERSION:
        if len(receipt_rows) == 1:
            if not _validate_trusted_store_receipt(tip):
                return _trusted_receipt_chain_failure(
                    TrustedReceiptChainFailureCode
                    .ID_MISMATCH,
                    (
                        "The legacy trusted-store receipt "
                        "does not validate."
                    ),
                    authoritative_tip=tip.receipt_id,
                    offending_receipt_id=tip.receipt_id,
                )

            return _trusted_receipt_chain_failure(
                TrustedReceiptChainFailureCode
                .CHAIN_NOT_ESTABLISHED,
                (
                    "The store has a valid legacy receipt "
                    "but no version 2 lineage."
                ),
                chain_length=1,
                authoritative_tip=tip.receipt_id,
            )

        return _trusted_receipt_chain_failure(
            TrustedReceiptChainFailureCode
            .KIND_INVARIANT,
            (
                "A legacy receipt cannot be the tip of a "
                "multi-row trusted lineage."
            ),
            authoritative_tip=tip.receipt_id,
            offending_receipt_id=tip.receipt_id,
        )

    if (
        tip.receipt_version
        != MIGRATION_RECEIPT_V2_VERSION
    ):
        return _trusted_receipt_chain_failure(
            TrustedReceiptChainFailureCode
            .UNKNOWN_VERSION,
            "The structural tip has an unsupported version.",
            authoritative_tip=tip.receipt_id,
            offending_receipt_id=tip.receipt_id,
        )

    if tip.schema_version_to != user_version:
        return _trusted_receipt_chain_failure(
            TrustedReceiptChainFailureCode
            .TIP_SCHEMA_DESYNC,
            (
                "The structural receipt tip does not match "
                "the live SQLite user_version."
            ),
            authoritative_tip=tip.receipt_id,
            lineage_epoch=tip.lineage_epoch,
            offending_receipt_id=tip.receipt_id,
        )

    reverse_chain = []
    visited = set()
    current = tip

    while True:
        if current.receipt_id in visited:
            return _trusted_receipt_chain_failure(
                TrustedReceiptChainFailureCode.CYCLE,
                (
                    "The receipt predecessor chain "
                    "contains a cycle."
                ),
                chain_length=len(reverse_chain),
                authoritative_tip=tip.receipt_id,
                lineage_epoch=tip.lineage_epoch,
                offending_receipt_id=current.receipt_id,
            )

        visited.add(current.receipt_id)
        reverse_chain.append(current)

        if len(reverse_chain) > len(receipt_rows):
            return _trusted_receipt_chain_failure(
                TrustedReceiptChainFailureCode.CYCLE,
                (
                    "The predecessor walk exceeded the "
                    "number of loaded receipts."
                ),
                chain_length=len(reverse_chain),
                authoritative_tip=tip.receipt_id,
                lineage_epoch=tip.lineage_epoch,
                offending_receipt_id=current.receipt_id,
            )

        predecessor_id = (
            current.predecessor_receipt_id
        )

        if predecessor_id is None:
            break

        predecessor = receipts_by_id.get(
            predecessor_id
        )

        if predecessor is None:
            return _trusted_receipt_chain_failure(
                TrustedReceiptChainFailureCode
                .MISSING_PREDECESSOR,
                (
                    "A receipt references a predecessor "
                    "that is not present."
                ),
                chain_length=len(reverse_chain),
                authoritative_tip=tip.receipt_id,
                lineage_epoch=tip.lineage_epoch,
                offending_receipt_id=current.receipt_id,
                predecessor_receipt_id=predecessor_id,
                successor_receipt_id=current.receipt_id,
            )

        current = predecessor

    if len(visited) != len(receipt_rows):
        disconnected = next(
            receipt
            for receipt in receipt_rows
            if receipt.receipt_id not in visited
        )

        return _trusted_receipt_chain_failure(
            TrustedReceiptChainFailureCode
            .DISCONNECTED_RECEIPT,
            (
                "At least one receipt is not reachable "
                "from the structural tip."
            ),
            chain_length=len(reverse_chain),
            authoritative_tip=tip.receipt_id,
            lineage_epoch=tip.lineage_epoch,
            offending_receipt_id=(
                disconnected.receipt_id
            ),
        )

    chain = tuple(reversed(reverse_chain))

    for index, receipt in enumerate(chain):
        if receipt.receipt_version not in {
            MIGRATION_RECEIPT_VERSION,
            MIGRATION_RECEIPT_V2_VERSION,
        }:
            return _trusted_receipt_chain_failure(
                TrustedReceiptChainFailureCode
                .UNKNOWN_VERSION,
                "A receipt has an unsupported version.",
                chain_length=index,
                authoritative_tip=tip.receipt_id,
                lineage_epoch=tip.lineage_epoch,
                offending_receipt_id=receipt.receipt_id,
            )

        predecessor = (
            chain[index - 1]
            if index > 0
            else None
        )

        if (
            receipt.receipt_version
            == MIGRATION_RECEIPT_VERSION
        ):
            if predecessor is not None:
                return _trusted_receipt_chain_failure(
                    TrustedReceiptChainFailureCode
                    .ILLEGAL_TRANSITION,
                    (
                        "A version 1 receipt may only be "
                        "the lineage origin."
                    ),
                    chain_length=index,
                    authoritative_tip=tip.receipt_id,
                    lineage_epoch=tip.lineage_epoch,
                    offending_receipt_id=receipt.receipt_id,
                )

            if not _validate_trusted_store_receipt(
                receipt
            ):
                return _trusted_receipt_chain_failure(
                    TrustedReceiptChainFailureCode
                    .ID_MISMATCH,
                    (
                        "The legacy lineage origin does "
                        "not validate."
                    ),
                    chain_length=index,
                    authoritative_tip=tip.receipt_id,
                    lineage_epoch=tip.lineage_epoch,
                    offending_receipt_id=receipt.receipt_id,
                )

            continue

        if receipt.receipt_kind not in {
            "root",
            "sqlite_upgrade",
            "epoch_boundary",
        }:
            return _trusted_receipt_chain_failure(
                TrustedReceiptChainFailureCode
                .KIND_INVARIANT,
                "A version 2 receipt has an invalid kind.",
                chain_length=index,
                authoritative_tip=tip.receipt_id,
                lineage_epoch=tip.lineage_epoch,
                offending_receipt_id=receipt.receipt_id,
            )

        if (
            receipt.schema_version_to is None
            or receipt.lineage_epoch is None
            or receipt.lineage_epoch < 1
        ):
            return _trusted_receipt_chain_failure(
                TrustedReceiptChainFailureCode
                .KIND_INVARIANT,
                (
                    "A version 2 receipt is missing "
                    "required lineage fields."
                ),
                chain_length=index,
                authoritative_tip=tip.receipt_id,
                lineage_epoch=tip.lineage_epoch,
                offending_receipt_id=receipt.receipt_id,
            )

        if receipt.receipt_kind == "root":
            if (
                predecessor is not None
                or receipt.predecessor_receipt_id
                is not None
                or receipt.schema_version_from
                is not None
                or receipt.lineage_epoch != 1
            ):
                return _trusted_receipt_chain_failure(
                    TrustedReceiptChainFailureCode
                    .KIND_INVARIANT,
                    (
                        "A version 2 root has invalid "
                        "lineage fields."
                    ),
                    chain_length=index,
                    authoritative_tip=tip.receipt_id,
                    lineage_epoch=tip.lineage_epoch,
                    offending_receipt_id=receipt.receipt_id,
                )

            if not _validate_trusted_store_receipt(
                receipt
            ):
                return _trusted_receipt_chain_failure(
                    TrustedReceiptChainFailureCode
                    .ID_MISMATCH,
                    (
                        "The version 2 root receipt does "
                        "not validate."
                    ),
                    chain_length=index,
                    authoritative_tip=tip.receipt_id,
                    lineage_epoch=tip.lineage_epoch,
                    offending_receipt_id=receipt.receipt_id,
                )

            continue

        if predecessor is None:
            return _trusted_receipt_chain_failure(
                TrustedReceiptChainFailureCode
                .MISSING_PREDECESSOR,
                (
                    "A non-root version 2 receipt has no "
                    "predecessor."
                ),
                chain_length=index,
                authoritative_tip=tip.receipt_id,
                lineage_epoch=tip.lineage_epoch,
                offending_receipt_id=receipt.receipt_id,
            )

        if (
            receipt.predecessor_receipt_id
            != predecessor.receipt_id
        ):
            return _trusted_receipt_chain_failure(
                TrustedReceiptChainFailureCode
                .MISSING_PREDECESSOR,
                (
                    "The receipt edge does not reference "
                    "the collected predecessor."
                ),
                chain_length=index,
                authoritative_tip=tip.receipt_id,
                lineage_epoch=tip.lineage_epoch,
                offending_receipt_id=receipt.receipt_id,
                predecessor_receipt_id=(
                    predecessor.receipt_id
                ),
                successor_receipt_id=receipt.receipt_id,
            )

        if (
            receipt.schema_version_from is None
            or receipt.schema_version_to
            <= receipt.schema_version_from
        ):
            return _trusted_receipt_chain_failure(
                TrustedReceiptChainFailureCode
                .SCHEMA_DISCONTINUITY,
                (
                    "A non-root version 2 receipt must "
                    "advance the schema."
                ),
                chain_length=index,
                authoritative_tip=tip.receipt_id,
                lineage_epoch=tip.lineage_epoch,
                offending_receipt_id=receipt.receipt_id,
                predecessor_receipt_id=(
                    predecessor.receipt_id
                ),
                successor_receipt_id=receipt.receipt_id,
            )

        if (
            predecessor.receipt_version
            == MIGRATION_RECEIPT_VERSION
        ):
            if (
                receipt.receipt_kind
                != "epoch_boundary"
            ):
                return _trusted_receipt_chain_failure(
                    TrustedReceiptChainFailureCode
                    .ILLEGAL_TRANSITION,
                    (
                        "A version 1 receipt may only "
                        "transition to an epoch boundary."
                    ),
                    chain_length=index,
                    authoritative_tip=tip.receipt_id,
                    lineage_epoch=tip.lineage_epoch,
                    offending_receipt_id=receipt.receipt_id,
                    predecessor_receipt_id=(
                        predecessor.receipt_id
                    ),
                    successor_receipt_id=receipt.receipt_id,
                )

            if receipt.lineage_epoch != 1:
                return _trusted_receipt_chain_failure(
                    TrustedReceiptChainFailureCode
                    .EPOCH_DISCONTINUITY,
                    (
                        "The first version 1 to version 2 "
                        "boundary must establish epoch 1."
                    ),
                    chain_length=index,
                    authoritative_tip=tip.receipt_id,
                    lineage_epoch=tip.lineage_epoch,
                    offending_receipt_id=receipt.receipt_id,
                    predecessor_receipt_id=(
                        predecessor.receipt_id
                    ),
                    successor_receipt_id=receipt.receipt_id,
                )

        else:
            predecessor_schema_to = (
                predecessor.schema_version_to
            )
            predecessor_epoch = (
                predecessor.lineage_epoch
            )

            if (
                predecessor_schema_to is None
                or predecessor_epoch is None
            ):
                return _trusted_receipt_chain_failure(
                    TrustedReceiptChainFailureCode
                    .KIND_INVARIANT,
                    (
                        "A version 2 predecessor is "
                        "missing lineage fields."
                    ),
                    chain_length=index,
                    authoritative_tip=tip.receipt_id,
                    lineage_epoch=tip.lineage_epoch,
                    offending_receipt_id=(
                        predecessor.receipt_id
                    ),
                )

            if (
                receipt.schema_version_from
                != predecessor_schema_to
            ):
                return _trusted_receipt_chain_failure(
                    TrustedReceiptChainFailureCode
                    .SCHEMA_DISCONTINUITY,
                    (
                        "Successor schema_version_from "
                        "does not equal predecessor "
                        "schema_version_to."
                    ),
                    chain_length=index,
                    authoritative_tip=tip.receipt_id,
                    lineage_epoch=tip.lineage_epoch,
                    offending_receipt_id=receipt.receipt_id,
                    predecessor_receipt_id=(
                        predecessor.receipt_id
                    ),
                    successor_receipt_id=receipt.receipt_id,
                )

            if receipt.receipt_kind == "sqlite_upgrade":
                if (
                    receipt.lineage_epoch
                    != predecessor_epoch
                ):
                    return _trusted_receipt_chain_failure(
                        TrustedReceiptChainFailureCode
                        .EPOCH_DISCONTINUITY,
                        (
                            "A SQLite upgrade must remain "
                            "in its predecessor's epoch."
                        ),
                        chain_length=index,
                        authoritative_tip=tip.receipt_id,
                        lineage_epoch=tip.lineage_epoch,
                        offending_receipt_id=receipt.receipt_id,
                        predecessor_receipt_id=(
                            predecessor.receipt_id
                        ),
                        successor_receipt_id=receipt.receipt_id,
                    )

            elif receipt.receipt_kind == "epoch_boundary":
                if (
                    predecessor.receipt_kind
                    not in {
                        "root",
                        "sqlite_upgrade",
                    }
                ):
                    return _trusted_receipt_chain_failure(
                        TrustedReceiptChainFailureCode
                        .ILLEGAL_TRANSITION,
                        (
                            "An epoch boundary has an "
                            "invalid predecessor kind."
                        ),
                        chain_length=index,
                        authoritative_tip=tip.receipt_id,
                        lineage_epoch=tip.lineage_epoch,
                        offending_receipt_id=receipt.receipt_id,
                    )

                if (
                    receipt.lineage_epoch
                    != predecessor_epoch + 1
                ):
                    return _trusted_receipt_chain_failure(
                        TrustedReceiptChainFailureCode
                        .EPOCH_DISCONTINUITY,
                        (
                            "A later epoch boundary must "
                            "increment the epoch by one."
                        ),
                        chain_length=index,
                        authoritative_tip=tip.receipt_id,
                        lineage_epoch=tip.lineage_epoch,
                        offending_receipt_id=receipt.receipt_id,
                        predecessor_receipt_id=(
                            predecessor.receipt_id
                        ),
                        successor_receipt_id=receipt.receipt_id,
                    )

        predecessor_digest = (
            calculate_migration_receipt_content_digest(
                predecessor
            )
        )

        expected_receipt_id = (
            calculate_migration_receipt_id(
                receipt,
                predecessor_content_digest=(
                    predecessor_digest
                ),
            )
        )

        if expected_receipt_id != receipt.receipt_id:
            return _trusted_receipt_chain_failure(
                TrustedReceiptChainFailureCode
                .ID_MISMATCH,
                (
                    "A non-root version 2 receipt does "
                    "not match its predecessor-bound hash."
                ),
                chain_length=index,
                authoritative_tip=tip.receipt_id,
                lineage_epoch=tip.lineage_epoch,
                offending_receipt_id=receipt.receipt_id,
                predecessor_receipt_id=(
                    predecessor.receipt_id
                ),
                successor_receipt_id=receipt.receipt_id,
            )

    return TrustedReceiptChainValidationResult(
        valid=True,
        authoritative_tip=tip.receipt_id,
        lineage_epoch=tip.lineage_epoch,
        chain_length=len(chain),
        failure=None,
    )
