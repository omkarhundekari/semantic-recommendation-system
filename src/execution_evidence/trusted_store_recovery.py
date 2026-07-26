from __future__ import annotations

import hashlib
import json
from typing import (
    List,
    Literal,
    Optional,
    Sequence,
)

from pydantic import BaseModel, Field

from execution_evidence.storage_readiness import (
    ExecutionEvidenceStorageReadiness,
)
from execution_evidence.store_migration import (
    MIGRATION_RECEIPT_VERSION,
    RepositoryEvidenceMigrationReceipt,
)
from execution_evidence.trusted_receipt_chain import (
    TrustedReceiptChainFailureCode,
    validate_trusted_receipt_chain,
)


TrustedStoreRecoveryStatus = Literal[
    "healthy",
    "manual_intervention_required",
    "unrecoverable",
]

TrustedStoreRecoveryAction = Literal[
    "none",
    "manual_investigation",
    "restore_from_backup",
]


class TrustedStoreRecoveryAssessment(BaseModel):
    assessment_id: str
    status: TrustedStoreRecoveryStatus
    proposed_action: TrustedStoreRecoveryAction
    readiness_status: str
    failure_code: Optional[str] = None
    authoritative_tip: Optional[str] = None

    # Diagnosis-only fields. They must never become
    # fallback or truncation targets.
    last_validated_receipt_id: Optional[str] = None
    chain_break_receipt_id: Optional[str] = None
    validated_receipt_count: int = Field(ge=0)
    total_receipt_count: int = Field(ge=0)
    descendant_count_after_break: int = Field(ge=0)

    store_state_fingerprint: str
    assessed_data_version: int = Field(ge=0)
    assessed_user_version: int = Field(ge=0)
    evidence_fingerprint_available: bool = False

    mutation_allowed: Literal[False] = False
    data_loss_possible: bool = False

    explanation: str
    warnings: List[str] = Field(default_factory=list)
    blockers: List[str] = Field(default_factory=list)


def _receipt_payload(
    receipt: RepositoryEvidenceMigrationReceipt,
) -> dict:
    return receipt.model_dump(
        mode="json",
    )


def build_trusted_store_state_fingerprint(
    receipts: Sequence[
        RepositoryEvidenceMigrationReceipt
    ],
    *,
    user_version: int,
    data_version: int,
    readiness: ExecutionEvidenceStorageReadiness,
) -> str:
    ordered_receipts = sorted(
        (
            _receipt_payload(receipt)
            for receipt in receipts
        ),
        key=lambda payload: (
            str(payload.get("created_at", "")),
            str(payload.get("receipt_id", "")),
        ),
    )

    payload = {
        "receipts": ordered_receipts,
        "user_version": user_version,
        "data_version": data_version,
        "readiness": {
            "status": readiness.status,
            "backend": readiness.backend,
            "schema_version": readiness.schema_version,
            "expected_schema_version": (
                readiness.expected_schema_version
            ),
            "migration_receipt_count": (
                readiness.migration_receipt_count
            ),
            "integrity_check": (
                readiness.integrity_check
            ),
            "foreign_key_violation_count": (
                readiness.foreign_key_violation_count
            ),
            "trusted_receipt_chain_valid": (
                readiness.trusted_receipt_chain_valid
            ),
            "trusted_receipt_chain_failure_code": (
                readiness
                .trusted_receipt_chain_failure_code
            ),
            "trusted_receipt_chain_tip": (
                readiness.trusted_receipt_chain_tip
            ),
            "trusted_receipt_chain_length": (
                readiness.trusted_receipt_chain_length
            ),
            "trusted_receipt_lineage_epoch": (
                readiness
                .trusted_receipt_lineage_epoch
            ),
            "checks": dict(
                sorted(readiness.checks.items())
            ),
        },
    }

    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()


def _assessment_id(
    store_state_fingerprint: str,
) -> str:
    return (
        "recovery_assessment_"
        f"{store_state_fingerprint[:32]}"
    )


def _is_compatible_legacy_store(
    receipts: Sequence[
        RepositoryEvidenceMigrationReceipt
    ],
    readiness: ExecutionEvidenceStorageReadiness,
) -> bool:
    return (
        len(receipts) == 1
        and receipts[0].receipt_version
        == MIGRATION_RECEIPT_VERSION
        and readiness.status == "degraded"
        and readiness.checks.get(
            "trusted_receipt_compatible",
            False,
        )
        and (
            readiness
            .trusted_receipt_chain_failure_code
            == TrustedReceiptChainFailureCode
            .CHAIN_NOT_ESTABLISHED.value
        )
    )


def assess_trusted_store_recovery(
    receipts: Sequence[
        RepositoryEvidenceMigrationReceipt
    ],
    *,
    user_version: int,
    data_version: int,
    readiness: ExecutionEvidenceStorageReadiness,
) -> TrustedStoreRecoveryAssessment:
    receipts = tuple(receipts)

    store_state_fingerprint = (
        build_trusted_store_state_fingerprint(
            receipts,
            user_version=user_version,
            data_version=data_version,
            readiness=readiness,
        )
    )

    common = {
        "assessment_id": _assessment_id(
            store_state_fingerprint
        ),
        "readiness_status": readiness.status,
        "total_receipt_count": len(receipts),
        "store_state_fingerprint": (
            store_state_fingerprint
        ),
        "assessed_data_version": data_version,
        "assessed_user_version": user_version,
        "evidence_fingerprint_available": False,
        "mutation_allowed": False,
    }

    integrity_valid = readiness.checks.get(
        "integrity_valid",
        False,
    )
    foreign_keys_valid = readiness.checks.get(
        "foreign_keys_valid",
        False,
    )

    # Do not reason about receipt history when the
    # underlying SQLite state is not structurally sound.
    if not integrity_valid:
        return TrustedStoreRecoveryAssessment(
            **common,
            status="manual_intervention_required",
            proposed_action="manual_investigation",
            failure_code="integrity_validation_failed",
            authoritative_tip=None,
            validated_receipt_count=0,
            descendant_count_after_break=0,
            data_loss_possible=True,
            explanation=(
                "SQLite integrity validation failed. "
                "Receipt-chain reasoning was skipped "
                "because the database contents cannot "
                "be treated as a reliable forensic input."
            ),
            blockers=[
                "A validated backup manifest is not "
                "available.",
                "The database must be preserved for "
                "manual investigation.",
            ],
        )

    if not foreign_keys_valid:
        return TrustedStoreRecoveryAssessment(
            **common,
            status="manual_intervention_required",
            proposed_action="manual_investigation",
            failure_code=(
                "foreign_key_validation_failed"
            ),
            authoritative_tip=None,
            validated_receipt_count=0,
            descendant_count_after_break=0,
            data_loss_possible=True,
            explanation=(
                "SQLite foreign-key validation failed. "
                "Receipt-chain reasoning was skipped "
                "because relational consistency is not "
                "established."
            ),
            blockers=[
                "The violating rows must be inspected "
                "without mutating trusted history.",
                "No verified backup manifest is "
                "available.",
            ],
        )

    if not receipts:
        return TrustedStoreRecoveryAssessment(
            **common,
            status="manual_intervention_required",
            proposed_action="manual_investigation",
            failure_code=(
                readiness
                .trusted_receipt_chain_failure_code
                or "receipt_set_empty"
            ),
            authoritative_tip=None,
            validated_receipt_count=0,
            descendant_count_after_break=0,
            data_loss_possible=False,
            explanation=(
                "No trusted-store receipts were found. "
                "An existing database must not be given "
                "a newly minted trust root automatically."
            ),
            blockers=[
                "The origin and history of the existing "
                "database cannot be established.",
                "Trust bootstrap requires a separate "
                "authorized workflow.",
            ],
        )

    chain_result = validate_trusted_receipt_chain(
        receipts,
        user_version=user_version,
    )

    readiness_matches_valid_chain = (
        chain_result.valid
        and readiness.status == "ready"
        and readiness.trusted_receipt_chain_valid
        is True
        and readiness.trusted_receipt_chain_tip
        == chain_result.authoritative_tip
        and readiness.trusted_receipt_chain_length
        == chain_result.chain_length
    )

    if readiness_matches_valid_chain:
        return TrustedStoreRecoveryAssessment(
            **common,
            status="healthy",
            proposed_action="none",
            failure_code=None,
            authoritative_tip=(
                chain_result.authoritative_tip
            ),
            last_validated_receipt_id=(
                chain_result.authoritative_tip
            ),
            validated_receipt_count=(
                chain_result.chain_length
            ),
            descendant_count_after_break=0,
            data_loss_possible=False,
            explanation=(
                "The authoritative trusted receipt "
                "chain is valid. No recovery action is "
                "required."
            ),
        )

    legacy_chain_validated = (
        chain_result.failure is not None
        and chain_result.failure.code
        == TrustedReceiptChainFailureCode
        .CHAIN_NOT_ESTABLISHED
        and chain_result.chain_length == 1
        and chain_result.authoritative_tip
        is not None
    )

    if (
        legacy_chain_validated
        and _is_compatible_legacy_store(
            receipts,
            readiness,
        )
        and readiness.trusted_receipt_chain_tip
        == chain_result.authoritative_tip
        and readiness.trusted_receipt_chain_length
        == chain_result.chain_length
    ):
        legacy_receipt = receipts[0]

        return TrustedStoreRecoveryAssessment(
            **common,
            status="healthy",
            proposed_action="none",
            failure_code=(
                TrustedReceiptChainFailureCode
                .CHAIN_NOT_ESTABLISHED.value
            ),
            authoritative_tip=(
                chain_result.authoritative_tip
            ),
            last_validated_receipt_id=(
                chain_result.authoritative_tip
            ),
            validated_receipt_count=1,
            descendant_count_after_break=0,
            data_loss_possible=False,
            explanation=(
                "The store has one valid compatible "
                "legacy receipt. The store does not "
                "require recovery."
            ),
            warnings=[
                "Version 2 receipt lineage is not "
                "established. That is a separate "
                "authorized trust-bootstrap operation, "
                "not a recovery action."
            ],
        )

    if (
        chain_result.valid
        and not readiness_matches_valid_chain
    ):
        return TrustedStoreRecoveryAssessment(
            **common,
            status="manual_intervention_required",
            proposed_action="manual_investigation",
            failure_code="readiness_state_mismatch",
            authoritative_tip=(
                chain_result.authoritative_tip
            ),
            last_validated_receipt_id=None,
            chain_break_receipt_id=None,
            validated_receipt_count=0,
            descendant_count_after_break=0,
            data_loss_possible=False,
            explanation=(
                "The receipt chain validates, but the "
                "supplied readiness snapshot does not "
                "describe the same authoritative state."
            ),
            blockers=[
                "Readiness and receipt-chain state must "
                "be captured from the same read "
                "transaction.",
                "No recovery action may rely on a stale "
                "or inconsistent readiness snapshot.",
            ],
        )

    failure_code = (
        chain_result.failure.code.value
        if chain_result.failure is not None
        else (
            readiness
            .trusted_receipt_chain_failure_code
            or "unknown_trust_failure"
        )
    )

    authoritative_tip = (
        chain_result.authoritative_tip
        or readiness.trusted_receipt_chain_tip
    )

    # The current validator does not expose a precise
    # stopping receipt. Do not infer one and accidentally
    # create a fallback trust boundary.
    last_validated_receipt_id = None
    chain_break_receipt_id = None
    validated_receipt_count = 0
    descendant_count_after_break = 0

    blockers = [
        "Trusted receipt history must not be "
        "truncated, rewritten, or reconstructed.",
        "No recovery executor is authorized by this "
        "assessment.",
    ]

    if (
        failure_code
        == TrustedReceiptChainFailureCode
        .TIP_SCHEMA_DESYNC.value
    ):
        blockers.append(
            "No independent schema or evidence "
            "fingerprint exists to determine which "
            "metadata is authoritative."
        )

    return TrustedStoreRecoveryAssessment(
        **common,
        status="manual_intervention_required",
        proposed_action="manual_investigation",
        failure_code=failure_code,
        authoritative_tip=authoritative_tip,
        last_validated_receipt_id=(
            last_validated_receipt_id
        ),
        chain_break_receipt_id=(
            chain_break_receipt_id
        ),
        validated_receipt_count=(
            validated_receipt_count
        ),
        descendant_count_after_break=(
            descendant_count_after_break
        ),
        data_loss_possible=True,
        explanation=(
            "Trusted receipt history did not validate. "
            "Any apparently valid earlier segment is "
            "forensic information only and must not be "
            "used as a fallback trust boundary."
        ),
        blockers=blockers,
    )
