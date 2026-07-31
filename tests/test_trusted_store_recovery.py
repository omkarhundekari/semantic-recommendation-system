from execution_evidence.storage_readiness import (
    ExecutionEvidenceStorageReadiness,
)
from execution_evidence.store_migration import (
    build_migration_receipt_v2,
)
from execution_evidence.trusted_receipt_chain import (
    TrustedReceiptChainFailureCode,
)
from execution_evidence.trusted_store import (
    build_fresh_init_receipt,
    build_fresh_init_report,
)
from execution_evidence.trusted_store_recovery import (
    assess_trusted_store_recovery,
)


CREATED_AT = "2026-07-25T12:00:00+00:00"


def _readiness(
    *,
    status="misconfigured",
    storage_failure_code=None,
    integrity_valid=True,
    foreign_keys_valid=True,
    chain_valid=None,
    failure_code=None,
    chain_tip=None,
    chain_length=None,
    compatible=False,
):
    return ExecutionEvidenceStorageReadiness(
        storage_failure_code=storage_failure_code,
        status=status,
        backend="sqlite",
        writable_store_initialized=True,
        schema_version=14,
        expected_schema_version=14,
        migration_receipt_count=1,
        integrity_check=(
            "ok"
            if integrity_valid
            else "database disk image is malformed"
        ),
        foreign_key_violation_count=(
            0 if foreign_keys_valid else 1
        ),
        trusted_receipt_chain_valid=chain_valid,
        trusted_receipt_chain_failure_code=(
            failure_code
        ),
        trusted_receipt_chain_tip=chain_tip,
        trusted_receipt_chain_length=chain_length,
        checks={
            "database_exists": True,
            "database_readable": True,
            "required_tables_present": True,
            "schema_current": True,
            "integrity_valid": integrity_valid,
            "foreign_keys_valid": (
                foreign_keys_valid
            ),
            "trusted_receipt_present": True,
            "trusted_receipt_chain_valid": (
                chain_valid is True
            ),
            "trusted_receipt_compatible": (
                compatible
            ),
        },
    )


def _v2_root():
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


def test_valid_v2_chain_is_healthy():
    root = _v2_root()
    readiness = _readiness(
        status="ready",
        chain_valid=True,
        chain_tip=root.receipt_id,
        chain_length=1,
    )

    assessment = assess_trusted_store_recovery(
        [root],
        user_version=14,
        data_version=7,
        readiness=readiness,
    )

    assert assessment.status == "healthy"
    assert assessment.proposed_action == "none"
    assert assessment.mutation_allowed is False
    assert assessment.data_loss_possible is False
    assert (
        assessment.authoritative_tip
        == root.receipt_id
    )
    assert assessment.validated_receipt_count == 1


def test_valid_legacy_store_is_healthy_not_recoverable():
    legacy = build_fresh_init_receipt(
        created_at=CREATED_AT
    )
    readiness = _readiness(
        chain_valid=False,
        status="degraded",
        failure_code=(
            TrustedReceiptChainFailureCode
            .CHAIN_NOT_ESTABLISHED.value
        ),
        chain_tip=legacy.receipt_id,
        chain_length=1,
        compatible=True,
    )

    assessment = assess_trusted_store_recovery(
        [legacy],
        user_version=14,
        data_version=8,
        readiness=readiness,
    )

    assert assessment.status == "healthy"
    assert assessment.proposed_action == "none"
    assert assessment.mutation_allowed is False
    assert assessment.warnings
    assert "trust-bootstrap" in assessment.warnings[0]


def test_broken_history_requires_manual_investigation():
    root = _v2_root()
    unknown = root.model_copy(
        update={
            "receipt_version": 3,
        }
    )
    readiness = _readiness(
        chain_valid=False,
        storage_failure_code=(
            "trusted_receipt_chain_invalid"
        ),
        failure_code=(
            TrustedReceiptChainFailureCode
            .UNKNOWN_VERSION.value
        ),
    )

    assessment = assess_trusted_store_recovery(
        [unknown],
        user_version=14,
        data_version=9,
        readiness=readiness,
    )

    assert (
        assessment.status
        == "manual_intervention_required"
    )
    assert (
        assessment.proposed_action
        == "manual_investigation"
    )
    assert assessment.mutation_allowed is False
    assert assessment.data_loss_possible is True
    assert assessment.last_validated_receipt_id is None
    assert assessment.chain_break_receipt_id is None
    assert assessment.validated_receipt_count == 0


def test_integrity_failure_short_circuits_chain_reasoning(
    monkeypatch,
):
    root = _v2_root()
    readiness = _readiness(
        storage_failure_code=(
            "integrity_validation_failed"
        ),
        integrity_valid=False,
    )

    def fail_if_called(*args, **kwargs):
        raise AssertionError(
            "Receipt-chain validator must not run."
        )

    monkeypatch.setattr(
        "execution_evidence.trusted_store_recovery."
        "validate_trusted_receipt_chain",
        fail_if_called,
    )

    assessment = assess_trusted_store_recovery(
        [root],
        user_version=14,
        data_version=10,
        readiness=readiness,
    )

    assert (
        assessment.status
        == "manual_intervention_required"
    )
    assert (
        assessment.failure_code
        == "integrity_validation_failed"
    )
    assert assessment.validated_receipt_count == 0
    assert assessment.mutation_allowed is False


def test_empty_receipt_set_never_mints_trust():
    readiness = _readiness(
        chain_valid=False,
        storage_failure_code=(
            "trusted_receipt_chain_invalid"
        ),
        failure_code="chain_not_established",
    )
    readiness.migration_receipt_count = 0
    readiness.checks[
        "trusted_receipt_present"
    ] = False

    assessment = assess_trusted_store_recovery(
        [],
        user_version=14,
        data_version=11,
        readiness=readiness,
    )

    assert (
        assessment.status
        == "manual_intervention_required"
    )
    assert assessment.proposed_action == (
        "manual_investigation"
    )
    assert assessment.authoritative_tip is None
    assert assessment.mutation_allowed is False


def test_assessment_identity_is_deterministic():
    root = _v2_root()
    readiness = _readiness(
        status="ready",
        chain_valid=True,
        chain_tip=root.receipt_id,
        chain_length=1,
    )

    first = assess_trusted_store_recovery(
        [root],
        user_version=14,
        data_version=12,
        readiness=readiness,
    )
    second = assess_trusted_store_recovery(
        [root],
        user_version=14,
        data_version=12,
        readiness=readiness,
    )

    assert first == second
    assert (
        first.store_state_fingerprint
        == second.store_state_fingerprint
    )
    assert first.assessment_id == second.assessment_id


def test_changed_data_version_preserves_assessment_identity():
    root = _v2_root()
    readiness = _readiness(
        status="ready",
        chain_valid=True,
        chain_tip=root.receipt_id,
        chain_length=1,
    )

    first = assess_trusted_store_recovery(
        [root],
        user_version=14,
        data_version=12,
        readiness=readiness,
    )
    second = assess_trusted_store_recovery(
        [root],
        user_version=14,
        data_version=13,
        readiness=readiness,
    )

    assert (
        first.store_state_fingerprint
        == second.store_state_fingerprint
    )
    assert first.assessment_id == second.assessment_id
    assert first.assessed_data_version == 12
    assert second.assessed_data_version == 13


def test_changed_user_version_changes_assessment_identity():
    root = _v2_root()
    readiness = _readiness(
        status="ready",
        chain_valid=True,
        chain_tip=root.receipt_id,
        chain_length=1,
    )

    first = assess_trusted_store_recovery(
        [root],
        user_version=14,
        data_version=12,
        readiness=readiness,
    )
    second = assess_trusted_store_recovery(
        [root],
        user_version=15,
        data_version=12,
        readiness=readiness,
    )

    assert (
        first.store_state_fingerprint
        != second.store_state_fingerprint
    )
    assert first.assessment_id != second.assessment_id


def test_changed_receipt_changes_assessment_identity():
    root = _v2_root()
    changed = root.model_copy(
        update={
            "source_root_hash": "0" * 64,
        }
    )
    readiness = _readiness(
        status="ready",
        chain_valid=True,
        chain_tip=root.receipt_id,
        chain_length=1,
    )

    first = assess_trusted_store_recovery(
        [root],
        user_version=14,
        data_version=12,
        readiness=readiness,
    )
    second = assess_trusted_store_recovery(
        [changed],
        user_version=14,
        data_version=12,
        readiness=readiness,
    )

    assert (
        first.store_state_fingerprint
        != second.store_state_fingerprint
    )
    assert first.assessment_id != second.assessment_id


def test_tip_schema_desync_never_proposes_metadata_repair():
    root = _v2_root()
    readiness = _readiness(
        chain_valid=False,
        storage_failure_code=(
            "trusted_receipt_chain_invalid"
        ),
        failure_code=(
            TrustedReceiptChainFailureCode
            .TIP_SCHEMA_DESYNC.value
        ),
        chain_tip=root.receipt_id,
    )

    assessment = assess_trusted_store_recovery(
        [root],
        user_version=15,
        data_version=14,
        readiness=readiness,
    )

    assert (
        assessment.status
        == "manual_intervention_required"
    )
    assert (
        assessment.proposed_action
        == "manual_investigation"
    )
    assert assessment.mutation_allowed is False
    assert any(
        "fingerprint" in blocker
        for blocker in assessment.blockers
    )



def test_forged_ready_snapshot_cannot_hide_invalid_receipt():
    root = _v2_root()
    invalid = root.model_copy(
        update={
            "receipt_version": 3,
        }
    )
    readiness = _readiness(
        status="ready",
        chain_valid=True,
        chain_tip=invalid.receipt_id,
        chain_length=1,
    )

    assessment = assess_trusted_store_recovery(
        [invalid],
        user_version=14,
        data_version=15,
        readiness=readiness,
    )

    assert (
        assessment.status
        == "manual_intervention_required"
    )
    assert (
        assessment.failure_code
        == TrustedReceiptChainFailureCode
        .UNKNOWN_VERSION.value
    )
    assert assessment.mutation_allowed is False


def test_tampered_legacy_receipt_cannot_be_marked_healthy():
    legacy = build_fresh_init_receipt(
        created_at=CREATED_AT
    )
    tampered = legacy.model_copy(
        update={
            "source_root_hash": "f" * 64,
        }
    )
    readiness = _readiness(
        chain_valid=False,
        status="degraded",
        failure_code=(
            TrustedReceiptChainFailureCode
            .CHAIN_NOT_ESTABLISHED.value
        ),
        chain_tip=tampered.receipt_id,
        chain_length=1,
        compatible=True,
    )

    assessment = assess_trusted_store_recovery(
        [tampered],
        user_version=14,
        data_version=16,
        readiness=readiness,
    )

    assert (
        assessment.status
        == "manual_intervention_required"
    )
    assert (
        assessment.failure_code
        == TrustedReceiptChainFailureCode
        .ID_MISMATCH.value
    )
    assert assessment.mutation_allowed is False


def test_valid_chain_with_stale_readiness_requires_investigation():
    root = _v2_root()
    readiness = _readiness(
        status="ready",
        chain_valid=True,
        chain_tip="receipt_stale",
        chain_length=1,
    )

    assessment = assess_trusted_store_recovery(
        [root],
        user_version=14,
        data_version=17,
        readiness=readiness,
    )

    assert (
        assessment.status
        == "manual_intervention_required"
    )
    assert (
        assessment.failure_code
        == "readiness_state_mismatch"
    )
    assert assessment.mutation_allowed is False


# trusted_store_recovery_fail_closed_hardening


def test_unknown_storage_failure_code_is_rejected_at_model_boundary():
    import pytest
    from pydantic import ValidationError

    payload = _readiness(
        status="ready",
        chain_valid=True,
        chain_tip="receipt_tip",
        chain_length=1,
    ).model_dump(mode="python")

    payload.update(
        {
            "status": "misconfigured",
            "storage_failure_code": (
                "future_unrecognized_failure"
            ),
            "trusted_receipt_chain_valid": None,
            "trusted_receipt_chain_failure_code": None,
            "trusted_receipt_chain_tip": None,
            "trusted_receipt_chain_length": None,
        }
    )

    with pytest.raises(ValidationError):
        ExecutionEvidenceStorageReadiness.model_validate(
            payload
        )


def test_unknown_storage_failure_code_defense_in_depth():
    root = _v2_root()
    readiness = _readiness(
        status="ready",
        chain_valid=True,
        chain_tip=root.receipt_id,
        chain_length=1,
    )

    # model_copy deliberately bypasses validation so this
    # test can exercise the future boundary defense branch.
    readiness = readiness.model_copy(
        update={
            "status": "misconfigured",
            "storage_failure_code": (
                "future_unrecognized_failure"
            ),
            "trusted_receipt_chain_valid": None,
            "trusted_receipt_chain_failure_code": None,
            "trusted_receipt_chain_tip": None,
            "trusted_receipt_chain_length": None,
        }
    )

    assessment = assess_trusted_store_recovery(
        [root],
        user_version=14,
        data_version=18,
        readiness=readiness,
    )

    assert (
        assessment.status
        == "manual_intervention_required"
    )
    assert (
        assessment.proposed_action
        == "manual_investigation"
    )
    assert (
        assessment.failure_code
        == "unknown_storage_failure_code"
    )
    assert assessment.mutation_allowed is False
    assert assessment.data_loss_possible is True


def test_unknown_storage_code_changes_recovery_identity():
    root = _v2_root()
    readiness = _readiness(
        status="ready",
        chain_valid=True,
        chain_tip=root.receipt_id,
        chain_length=1,
    )

    first = readiness.model_copy(
        update={
            "status": "misconfigured",
            "storage_failure_code": "future_code_one",
            "trusted_receipt_chain_valid": None,
            "trusted_receipt_chain_failure_code": None,
        }
    )
    second = first.model_copy(
        update={
            "storage_failure_code": "future_code_two",
        }
    )

    first_assessment = assess_trusted_store_recovery(
        [root],
        user_version=14,
        data_version=19,
        readiness=first,
    )
    second_assessment = assess_trusted_store_recovery(
        [root],
        user_version=14,
        data_version=19,
        readiness=second,
    )

    assert (
        first_assessment.store_state_fingerprint
        != second_assessment.store_state_fingerprint
    )
    assert (
        first_assessment.assessment_id
        != second_assessment.assessment_id
    )


# trusted_store_data_loss_policy


def test_pre_lineage_data_loss_policy_is_explicit():
    expected = {
        "unsupported_store_type": False,
        "json_store_unreadable": True,
        "sqlite_database_missing": True,
        "sqlite_database_unreadable": True,
        "trusted_store_tables_missing": True,
        "schema_version_mismatch": False,
        "receipts_unreadable": True,
        "receipt_parse_failure": True,
    }

    for failure_code, data_loss_possible in (
        expected.items()
    ):
        readiness = ExecutionEvidenceStorageReadiness(
            status="misconfigured",
            backend=(
                "json"
                if failure_code
                in {
                    "unsupported_store_type",
                    "json_store_unreadable",
                }
                else "sqlite"
            ),
            writable_store_initialized=True,
            storage_failure_code=failure_code,
            trusted_receipt_chain_valid=None,
            trusted_receipt_chain_failure_code=None,
            checks={},
        )

        assessment = assess_trusted_store_recovery(
            [],
            user_version=14,
            data_version=20,
            readiness=readiness,
        )

        assert (
            assessment.failure_code
            == failure_code
        )
        assert (
            assessment.data_loss_possible
            is data_loss_possible
        )
        assert assessment.mutation_allowed is False


def test_missing_trusted_store_tables_reports_possible_data_loss():
    readiness = ExecutionEvidenceStorageReadiness(
        status="misconfigured",
        backend="sqlite",
        writable_store_initialized=True,
        storage_failure_code=(
            "trusted_store_tables_missing"
        ),
        trusted_receipt_chain_valid=None,
        trusted_receipt_chain_failure_code=None,
        checks={
            "required_tables_present": False,
        },
    )

    assessment = assess_trusted_store_recovery(
        [],
        user_version=14,
        data_version=21,
        readiness=readiness,
    )

    assert (
        assessment.failure_code
        == "trusted_store_tables_missing"
    )
    assert assessment.data_loss_possible is True
    assert assessment.mutation_allowed is False


def test_unknown_storage_failure_defaults_to_possible_data_loss():
    root = _v2_root()
    readiness = _readiness(
        status="ready",
        chain_valid=True,
        chain_tip=root.receipt_id,
        chain_length=1,
    ).model_copy(
        update={
            "status": "misconfigured",
            "storage_failure_code": (
                "future_unknown_failure"
            ),
            "trusted_receipt_chain_valid": None,
            "trusted_receipt_chain_failure_code": None,
            "trusted_receipt_chain_tip": None,
            "trusted_receipt_chain_length": None,
        }
    )

    assessment = assess_trusted_store_recovery(
        [root],
        user_version=14,
        data_version=22,
        readiness=readiness,
    )

    assert (
        assessment.failure_code
        == "unknown_storage_failure_code"
    )
    assert assessment.data_loss_possible is True
    assert assessment.mutation_allowed is False
