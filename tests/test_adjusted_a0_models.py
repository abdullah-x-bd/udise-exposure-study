from udise.adjusted_a0_models import (
    BASELINE_PAIR_OUTCOMES,
    INTERACTION_OUTCOMES,
    PRINCIPAL_OUTCOMES,
    Regressor,
)
from udise.indicator_registry import ALL_INDICATORS


def test_every_model_outcome_exists_in_indicator_registry() -> None:
    available = {item.code for item in ALL_INDICATORS}
    requested = set(PRINCIPAL_OUTCOMES) | set(INTERACTION_OUTCOMES) | set(BASELINE_PAIR_OUTCOMES)
    assert requested.issubset(available)


def test_model_families_cover_core_structural_domains() -> None:
    assert "ends_before_class12" in PRINCIPAL_OUTCOMES
    assert "str_above_30" in PRINCIPAL_OUTCOMES
    assert "no_internet" in PRINCIPAL_OUTCOMES
    assert "institutional_neglect_index" in PRINCIPAL_OUTCOMES
    assert "overall_multidimensional_deprivation_index" in PRINCIPAL_OUTCOMES
    assert "overall_multidimensional_deprivation_index" in INTERACTION_OUTCOMES


def test_regressor_is_explicitly_named() -> None:
    regressor = Regressor("a0_share", "CAST(a0_share AS DOUBLE)", "Muslim share")
    assert regressor.name == "a0_share"
    assert "a0_share" in regressor.expression
    assert regressor.label == "Muslim share"
