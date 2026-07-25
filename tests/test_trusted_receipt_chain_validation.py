from execution_evidence.store_migration import (
    build_migration_receipt_v2,
)
from execution_evidence.trusted_store import (
    SQLITE_UPGRADE_SOURCE_TYPE,
    TrustedReceiptChainFailureCode,
    build_fresh_init_receipt,
    build_fresh_init_report,
    validate_trusted_receipt_chain,
)


CREATED_AT = "2026-07-25T12:00:00+00:00"


def _upgrade_report():
    return build_fresh_init_report().model_copy(
        update={
            "source_type": SQLITE_UPGRADE_SOURCE_TYPE,
        }
    )


def _build_root(
    *,
    schema_version_to: int = 14,
):
    return build_migration_receipt_v2(
        report=build_fresh_init_report(),
        source_identifier="solvyn:fresh-init",
        created_at=CREATED_AT,
        receipt_kind="root",
        predecessor_receipt_id=None,
        schema_version_from=None,
        schema_version_to=schema_version_to,
        lineage_epoch=1,
    )


def _build_successor(
    predecessor,
    *,
    receipt_kind: str,
    schema_version_from: int,
    schema_version_to: int,
    lineage_epoch: int,
):
    return build_migration_receipt_v2(
        report=_upgrade_report(),
        source_identifier=(
            "solvyn:sqlite-upgrade:"
            f"{predecessor.receipt_id}:"
            f"v{schema_version_from}"
            f"->v{schema_version_to}"
        ),
        created_at=CREATED_AT,
        receipt_kind=receipt_kind,
        predecessor_receipt_id=(
            predecessor.receipt_id
        ),
        predecessor_receipt=predecessor,
        schema_version_from=(
            schema_version_from
        ),
        schema_version_to=schema_version_to,
        lineage_epoch=lineage_epoch,
    )


def test_v2_root_chain_is_valid():
    root = _build_root()

    result = validate_trusted_receipt_chain(
        [root],
        user_version=14,
    )

    assert result.valid
    assert result.authoritative_tip == root.receipt_id
    assert result.lineage_epoch == 1
    assert result.chain_length == 1
    assert result.failure is None


def test_v1_only_store_reports_chain_not_established():
    legacy = build_fresh_init_receipt(
        created_at=CREATED_AT
    )

    result = validate_trusted_receipt_chain(
        [legacy],
        user_version=14,
    )

    assert not result.valid
    assert result.failure is not None
    assert (
        result.failure.code
        == TrustedReceiptChainFailureCode
        .CHAIN_NOT_ESTABLISHED
    )


def test_v1_to_v2_boundary_chain_is_valid():
    legacy = build_fresh_init_receipt(
        created_at=CREATED_AT
    )
    boundary = _build_successor(
        legacy,
        receipt_kind="epoch_boundary",
        schema_version_from=13,
        schema_version_to=14,
        lineage_epoch=1,
    )

    result = validate_trusted_receipt_chain(
        [legacy, boundary],
        user_version=14,
    )

    assert result.valid
    assert (
        result.authoritative_tip
        == boundary.receipt_id
    )
    assert result.chain_length == 2


def test_same_epoch_sqlite_upgrade_is_valid():
    root = _build_root(
        schema_version_to=14
    )
    upgrade = _build_successor(
        root,
        receipt_kind="sqlite_upgrade",
        schema_version_from=14,
        schema_version_to=16,
        lineage_epoch=1,
    )

    result = validate_trusted_receipt_chain(
        [root, upgrade],
        user_version=16,
    )

    assert result.valid
    assert result.chain_length == 2


def test_later_epoch_boundary_is_valid():
    root = _build_root(
        schema_version_to=14
    )
    boundary = _build_successor(
        root,
        receipt_kind="epoch_boundary",
        schema_version_from=14,
        schema_version_to=15,
        lineage_epoch=2,
    )
    upgrade = _build_successor(
        boundary,
        receipt_kind="sqlite_upgrade",
        schema_version_from=15,
        schema_version_to=16,
        lineage_epoch=2,
    )

    result = validate_trusted_receipt_chain(
        [root, boundary, upgrade],
        user_version=16,
    )

    assert result.valid
    assert result.lineage_epoch == 2
    assert result.chain_length == 3


def test_tip_must_match_live_user_version():
    root = _build_root(
        schema_version_to=14
    )

    result = validate_trusted_receipt_chain(
        [root],
        user_version=15,
    )

    assert not result.valid
    assert result.failure is not None
    assert (
        result.failure.code
        == TrustedReceiptChainFailureCode
        .TIP_SCHEMA_DESYNC
    )


def test_schema_discontinuity_is_rejected():
    root = _build_root(
        schema_version_to=14
    )
    upgrade = _build_successor(
        root,
        receipt_kind="sqlite_upgrade",
        schema_version_from=13,
        schema_version_to=16,
        lineage_epoch=1,
    )

    result = validate_trusted_receipt_chain(
        [root, upgrade],
        user_version=16,
    )

    assert not result.valid
    assert result.failure is not None
    assert (
        result.failure.code
        == TrustedReceiptChainFailureCode
        .SCHEMA_DISCONTINUITY
    )


def test_sqlite_upgrade_cannot_change_epoch():
    root = _build_root(
        schema_version_to=14
    )
    upgrade = _build_successor(
        root,
        receipt_kind="sqlite_upgrade",
        schema_version_from=14,
        schema_version_to=15,
        lineage_epoch=2,
    )

    result = validate_trusted_receipt_chain(
        [root, upgrade],
        user_version=15,
    )

    assert not result.valid
    assert result.failure is not None
    assert (
        result.failure.code
        == TrustedReceiptChainFailureCode
        .EPOCH_DISCONTINUITY
    )


def test_later_boundary_must_increment_epoch_by_one():
    root = _build_root(
        schema_version_to=14
    )
    boundary = _build_successor(
        root,
        receipt_kind="epoch_boundary",
        schema_version_from=14,
        schema_version_to=15,
        lineage_epoch=3,
    )

    result = validate_trusted_receipt_chain(
        [root, boundary],
        user_version=15,
    )

    assert not result.valid
    assert result.failure is not None
    assert (
        result.failure.code
        == TrustedReceiptChainFailureCode
        .EPOCH_DISCONTINUITY
    )


def test_tampered_predecessor_is_rejected():
    legacy = build_fresh_init_receipt(
        created_at=CREATED_AT
    )
    boundary = _build_successor(
        legacy,
        receipt_kind="epoch_boundary",
        schema_version_from=13,
        schema_version_to=14,
        lineage_epoch=1,
    )
    tampered = legacy.model_copy(
        update={
            "source_root_hash": "f" * 64,
        }
    )

    result = validate_trusted_receipt_chain(
        [tampered, boundary],
        user_version=14,
    )

    assert not result.valid
    assert result.failure is not None
    assert (
        result.failure.code
        == TrustedReceiptChainFailureCode
        .ID_MISMATCH
    )


def test_disconnected_receipts_are_rejected():
    first = _build_root(
        schema_version_to=14
    )
    second = _build_root(
        schema_version_to=15
    )

    result = validate_trusted_receipt_chain(
        [first, second],
        user_version=14,
    )

    assert not result.valid
    assert result.failure is not None
    assert (
        result.failure.code
        == TrustedReceiptChainFailureCode
        .MULTIPLE_TIPS
    )


def test_unknown_receipt_version_fails_closed():
    root = _build_root()
    unknown = root.model_copy(
        update={
            "receipt_version": 3,
        }
    )

    result = validate_trusted_receipt_chain(
        [unknown],
        user_version=14,
    )

    assert not result.valid
    assert result.failure is not None
    assert (
        result.failure.code
        == TrustedReceiptChainFailureCode
        .UNKNOWN_VERSION
    )

def test_trusted_store_reexports_chain_api():
    from execution_evidence import trusted_receipt_chain
    from execution_evidence import trusted_store

    assert (
        trusted_store.TrustedReceiptChainFailureCode
        is trusted_receipt_chain
        .TrustedReceiptChainFailureCode
    )
    assert (
        trusted_store.TrustedReceiptChainFailure
        is trusted_receipt_chain
        .TrustedReceiptChainFailure
    )
    assert (
        trusted_store
        .TrustedReceiptChainValidationResult
        is trusted_receipt_chain
        .TrustedReceiptChainValidationResult
    )
    assert (
        trusted_store.validate_trusted_receipt_chain
        is trusted_receipt_chain
        .validate_trusted_receipt_chain
    )
