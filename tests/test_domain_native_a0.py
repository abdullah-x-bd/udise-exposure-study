from udise.adjusted_a0_models import PRINCIPAL_OUTCOMES
from udise.domain_native_a0 import (
    DOMAIN_SOURCES,
    FOUNDATION_ESSENTIAL,
    SECONDARY_DOMAINS,
    expression_tokens,
    indicators_for_domain,
)
from udise.domain_native_adjusted import OUTCOME_DOMAIN
from udise.indicator_registry import SECONDARY_INDICATORS, TERTIARY_INDICATORS


def test_every_secondary_indicator_has_exactly_one_domain_job() -> None:
    collected = [
        item.code
        for domain in SECONDARY_DOMAINS
        for item in indicators_for_domain(domain)
    ]
    expected = [item.code for item in SECONDARY_INDICATORS]
    assert sorted(collected) == sorted(expected)
    assert len(collected) == len(set(collected))


def test_domain_source_map_is_complete() -> None:
    assert set(DOMAIN_SOURCES) == set(SECONDARY_DOMAINS)
    assert DOMAIN_SOURCES["vulnerability"] == ()
    assert DOMAIN_SOURCES["age_grade"] == ()
    assert "facility" in DOMAIN_SOURCES["wash"]
    assert "teacher" in DOMAIN_SOURCES["teachers"]


def test_foundation_has_all_group_weights_and_controls() -> None:
    required = {
        "pseudocode",
        "state",
        "district",
        "rural_urban",
        "managment",
        "lowclass",
        "highclass",
        "total_students",
        "a0_students",
        "a0_share",
        "b0_students",
        "b0_share",
        "c0_students",
        "c0_share",
        "d0_students",
        "d0_share",
        "e0_students",
        "e0_share",
    }
    assert required.issubset(FOUNDATION_ESSENTIAL)


def test_expression_tokeniser_preserves_quoted_source_columns() -> None:
    tokens = expression_tokens(
        'COALESCE("none", 0) / NULLIF(total_tch, 0)'
    )
    assert "none" in tokens
    assert "total_tch" in tokens
    assert "COALESCE" in tokens


def test_every_principal_model_outcome_has_a_compact_domain() -> None:
    assert set(PRINCIPAL_OUTCOMES).issubset(OUTCOME_DOMAIN)
    assert set(OUTCOME_DOMAIN.values()).issubset(set(SECONDARY_DOMAINS) | {"tertiary"})


def test_all_tertiary_indicators_are_retained() -> None:
    assert len(TERTIARY_INDICATORS) == 15
    assert "institutional_neglect_index" in {
        item.code for item in TERTIARY_INDICATORS
    }
