from pathlib import Path

from execution_evidence.sqlite_schema import (
    initialize_execution_evidence_database,
)
from execution_evidence.store_migration import (
    MIGRATION_RECEIPT_V2_HASH_DOMAIN,
    RepositoryEvidenceMigrationError,
    build_migration_receipt_v2,
    calculate_migration_receipt_content_digest,
    calculate_migration_receipt_id,
    canonical_migration_receipt_material_json,
    migration_receipt_intrinsic_material,
    migration_receipt_v2_material,
    persist_migration_receipt,
)
from execution_evidence.trusted_store import (
    build_fresh_init_receipt,
    build_fresh_init_report,
    load_valid_trusted_receipt,
    validate_trusted_store_receipt,
)


CREATED_AT = "2026-07-25T12:00:00+00:00"


def _build_v2_root():
    return build_migration_receipt_v2(
        report=build_fresh_init_report(),
        source_identifier="solvyn:fresh-init",
        created_at=CREATED_AT,
        receipt_kind="root",
        predecessor_receipt_id=None,
        schema_version_from=None,
        schema_version_to=14,
        lineage_epoch=1,
    )


def test_v1_receipt_hash_contract_remains_valid():
    receipt = build_fresh_init_receipt(
        created_at=CREATED_AT
    )

    assert receipt.receipt_version == 1
    assert receipt.receipt_id == (
        "5fd7f01523ff0bfb96a9bf8f7785ccd9d3ccf6c6f731d962833fb1716faaa74a"
    )
    assert validate_trusted_store_receipt(
        receipt
    )
    assert (
        calculate_migration_receipt_id(receipt)
        == receipt.receipt_id
    )


def test_v2_hash_material_has_domain_separation():
    receipt = _build_v2_root()

    material = migration_receipt_v2_material(
        receipt_kind=receipt.receipt_kind,
        predecessor_receipt_id=(
            receipt.predecessor_receipt_id
        ),
        predecessor_content_digest=None,
        schema_version_from=(
            receipt.schema_version_from
        ),
        schema_version_to=(
            receipt.schema_version_to
        ),
        lineage_epoch=receipt.lineage_epoch,
        source_type=receipt.source_type,
        source_identifier=(
            receipt.source_identifier
        ),
        source_root_hash=(
            receipt.source_root_hash
        ),
        canonicalization_version=(
            receipt.canonicalization_version
        ),
        report_version=receipt.report_version,
        repository_count=(
            receipt.repository_count
        ),
        evidence_count=receipt.evidence_count,
        attribution_count=(
            receipt.attribution_count
        ),
        deterministic_report_json=(
            receipt.deterministic_report_json
        ),
        created_at=receipt.created_at,
    )

    assert material["hash_domain"] == (
        MIGRATION_RECEIPT_V2_HASH_DOMAIN
    )


def test_receipt_id_is_excluded_from_v2_material():
    receipt = _build_v2_root()

    material = migration_receipt_v2_material(
        receipt_kind=receipt.receipt_kind,
        predecessor_receipt_id=None,
        predecessor_content_digest=None,
        schema_version_from=None,
        schema_version_to=14,
        lineage_epoch=1,
        source_type=receipt.source_type,
        source_identifier=(
            receipt.source_identifier
        ),
        source_root_hash=(
            receipt.source_root_hash
        ),
        canonicalization_version=(
            receipt.canonicalization_version
        ),
        report_version=receipt.report_version,
        repository_count=(
            receipt.repository_count
        ),
        evidence_count=receipt.evidence_count,
        attribution_count=(
            receipt.attribution_count
        ),
        deterministic_report_json=(
            receipt.deterministic_report_json
        ),
        created_at=receipt.created_at,
    )

    assert "receipt_id" not in material
    assert receipt.receipt_id not in (
        canonical_migration_receipt_material_json(
            material
        )
    )


def test_v2_receipt_is_valid_and_recomputable():
    receipt = _build_v2_root()

    assert validate_trusted_store_receipt(
        receipt
    )
    assert (
        calculate_migration_receipt_id(receipt)
        == receipt.receipt_id
    )


def test_v2_created_at_is_bound_by_hash():
    receipt = _build_v2_root().model_copy(
        update={
            "created_at": (
                "2026-07-26T12:00:00+00:00"
            )
        }
    )

    assert not validate_trusted_store_receipt(
        receipt
    )


def test_v2_counts_are_bound_by_hash():
    receipt = _build_v2_root().model_copy(
        update={
            "repository_count": 1,
        }
    )

    assert not validate_trusted_store_receipt(
        receipt
    )


def test_v2_lineage_fields_are_bound_by_hash():
    receipt = _build_v2_root().model_copy(
        update={
            "lineage_epoch": 2,
        }
    )

    assert not validate_trusted_store_receipt(
        receipt
    )


def test_unknown_receipt_version_fails_closed():
    receipt = _build_v2_root().model_copy(
        update={
            "receipt_version": 3,
        }
    )

    assert not validate_trusted_store_receipt(
        receipt
    )


def test_hash_material_rejects_receipt_id():
    try:
        canonical_migration_receipt_material_json(
            {
                "receipt_id": "self-reference",
            }
        )
    except RepositoryEvidenceMigrationError:
        pass
    else:
        raise AssertionError(
            "receipt_id must be rejected from "
            "hash material"
        )


def test_v2_receipt_persistence_round_trip(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(
        database_path
    )
    receipt = _build_v2_root()

    persist_migration_receipt(
        database_path=database_path,
        receipt=receipt,
    )

    assert (
        load_valid_trusted_receipt(
            database_path
        )
        == receipt
    )





def _build_v2_boundary(
    predecessor,
):
    return build_migration_receipt_v2(
        report=build_fresh_init_report().model_copy(
            update={
                "source_type": "sqlite_upgrade",
            }
        ),
        source_identifier=(
            "solvyn:sqlite-upgrade:"
            f"{predecessor.receipt_id}:v13->v14"
        ),
        created_at=CREATED_AT,
        receipt_kind="epoch_boundary",
        predecessor_receipt_id=(
            predecessor.receipt_id
        ),
        predecessor_receipt=predecessor,
        schema_version_from=13,
        schema_version_to=14,
        lineage_epoch=1,
    )


def test_v1_intrinsic_digest_matches_frozen_v1_id():
    receipt = build_fresh_init_receipt(
        created_at=CREATED_AT
    )

    assert (
        calculate_migration_receipt_content_digest(
            receipt
        )
        == receipt.receipt_id
    )
    assert (
        calculate_migration_receipt_content_digest(
            receipt
        )
        == "5fd7f01523ff0bfb96a9bf8f7785ccd9d3ccf6c6f731d962833fb1716faaa74a"
    )


def test_intrinsic_digest_excludes_receipt_id():
    receipt = _build_v2_root()
    changed_id = receipt.model_copy(
        update={
            "receipt_id": "different-stored-id",
        }
    )

    assert (
        calculate_migration_receipt_content_digest(
            changed_id
        )
        == calculate_migration_receipt_content_digest(
            receipt
        )
    )


def test_intrinsic_digest_changes_with_persisted_content():
    receipt = _build_v2_root()
    changed = receipt.model_copy(
        update={
            "source_root_hash": (
                "0" * 64
            ),
        }
    )

    assert (
        calculate_migration_receipt_content_digest(
            changed
        )
        != calculate_migration_receipt_content_digest(
            receipt
        )
    )


def test_v2_intrinsic_material_has_no_derived_digest():
    predecessor = build_fresh_init_receipt(
        created_at=CREATED_AT
    )
    receipt = _build_v2_boundary(
        predecessor
    )

    material = migration_receipt_intrinsic_material(
        receipt
    )

    assert "receipt_id" not in material
    assert (
        "predecessor_content_digest"
        not in material
    )


def test_non_root_v2_hash_requires_digest():
    predecessor = build_fresh_init_receipt(
        created_at=CREATED_AT
    )
    receipt = _build_v2_boundary(
        predecessor
    )

    try:
        calculate_migration_receipt_id(
            receipt
        )
    except RepositoryEvidenceMigrationError:
        pass
    else:
        raise AssertionError(
            "Non-root v2 receipt hashing must "
            "require predecessor content"
        )


def test_non_root_v2_requires_chain_validation():
    predecessor = build_fresh_init_receipt(
        created_at=CREATED_AT
    )
    receipt = _build_v2_boundary(
        predecessor
    )

    assert not validate_trusted_store_receipt(
        receipt
    )


def test_non_root_v2_hash_recomputes_with_digest():
    predecessor = build_fresh_init_receipt(
        created_at=CREATED_AT
    )
    receipt = _build_v2_boundary(
        predecessor
    )
    digest = (
        calculate_migration_receipt_content_digest(
            predecessor
        )
    )

    assert (
        calculate_migration_receipt_id(
            receipt,
            predecessor_content_digest=digest,
        )
        == receipt.receipt_id
    )


def test_non_root_builder_requires_predecessor_receipt():
    predecessor = build_fresh_init_receipt(
        created_at=CREATED_AT
    )

    try:
        build_migration_receipt_v2(
            report=build_fresh_init_report().model_copy(
                update={
                    "source_type": "sqlite_upgrade",
                }
            ),
            source_identifier="upgrade",
            created_at=CREATED_AT,
            receipt_kind="epoch_boundary",
            predecessor_receipt_id=(
                predecessor.receipt_id
            ),
            schema_version_from=13,
            schema_version_to=14,
            lineage_epoch=1,
        )
    except RepositoryEvidenceMigrationError:
        pass
    else:
        raise AssertionError(
            "Non-root v2 construction must require "
            "the predecessor receipt"
        )


def test_non_root_builder_rejects_predecessor_id_mismatch():
    predecessor = build_fresh_init_receipt(
        created_at=CREATED_AT
    )

    try:
        build_migration_receipt_v2(
            report=build_fresh_init_report().model_copy(
                update={
                    "source_type": "sqlite_upgrade",
                }
            ),
            source_identifier="upgrade",
            created_at=CREATED_AT,
            receipt_kind="epoch_boundary",
            predecessor_receipt_id="wrong-id",
            predecessor_receipt=predecessor,
            schema_version_from=13,
            schema_version_to=14,
            lineage_epoch=1,
        )
    except RepositoryEvidenceMigrationError:
        pass
    else:
        raise AssertionError(
            "Predecessor object and id must match"
        )


def test_successor_hash_binds_predecessor_intrinsic_content():
    predecessor = build_fresh_init_receipt(
        created_at=CREATED_AT
    )
    original = _build_v2_boundary(
        predecessor
    )

    tampered_predecessor = predecessor.model_copy(
        update={
            "source_root_hash": "0" * 64,
        }
    )
    changed = _build_v2_boundary(
        tampered_predecessor
    )

    assert (
        tampered_predecessor.receipt_id
        == predecessor.receipt_id
    )
    assert changed.receipt_id != original.receipt_id


def test_v2_lineage_epoch_must_be_positive():
    try:
        build_migration_receipt_v2(
            report=build_fresh_init_report(),
            source_identifier="solvyn:fresh-init",
            created_at=CREATED_AT,
            receipt_kind="root",
            predecessor_receipt_id=None,
            schema_version_from=None,
            schema_version_to=14,
            lineage_epoch=0,
        )
    except RepositoryEvidenceMigrationError:
        pass
    else:
        raise AssertionError(
            "Version 2 lineage epochs must be positive"
        )
