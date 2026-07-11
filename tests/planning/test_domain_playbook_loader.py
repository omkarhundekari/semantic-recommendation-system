import pytest

from planning.domain_playbook_loader import (
    DomainPlaybook,
    load_domain_playbook,
    load_playbook_or_generic,
)


def test_load_generic_playbook():
    playbook = load_domain_playbook("generic")

    assert isinstance(playbook, DomainPlaybook)
    assert playbook.domain == "generic"
    assert playbook.playbook_version == "v1"
    assert playbook.typical_file_structure
    assert playbook.setup_commands
    assert playbook.validation_checks
    assert playbook.common_errors
    assert playbook.typical_portfolio_artifacts


def test_unknown_playbook_raises_clear_error():
    with pytest.raises(ValueError, match="No mission playbook found"):
        load_domain_playbook("not_a_real_domain")


def test_load_playbook_or_generic_falls_back_to_generic():
    playbook = load_playbook_or_generic("not_a_real_domain")

    assert playbook.domain == "generic"


def test_load_core_domain_playbooks():
    for domain in ["rag_llm", "frontend", "education_tech"]:
        playbook = load_domain_playbook(domain)

        assert playbook.domain == domain
        assert playbook.core_concepts
        assert playbook.typical_file_structure
        assert playbook.setup_commands
        assert playbook.validation_checks
        assert playbook.common_errors
        assert playbook.metrics_to_track
        assert playbook.test_strategy
