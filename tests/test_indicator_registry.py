from udise.indicator_registry import (
    ALL_INDICATORS,
    CODEBOOK_REQUIRED_COLUMNS,
    SECONDARY_INDICATORS,
    TERTIARY_INDICATORS,
    validate_registry,
)


def test_registry_is_unique_and_valid() -> None:
    validate_registry()
    codes = [item.code for item in ALL_INDICATORS]
    assert len(codes) == len(set(codes))
    assert len(SECONDARY_INDICATORS) >= 90
    assert len(TERTIARY_INDICATORS) >= 15


def test_a0_core_domains_are_covered() -> None:
    domains = {item.domain for item in ALL_INDICATORS}
    assert {
        "access",
        "infrastructure",
        "wash",
        "learning_environment",
        "digital",
        "teachers",
        "governance",
        "welfare",
        "inclusion",
        "vulnerability",
        "age_grade",
        "tertiary_overall",
        "tertiary_neglect",
    }.issubset(domains)


def test_every_indicator_has_interpretive_metadata() -> None:
    for item in ALL_INDICATORS:
        assert item.code
        assert item.label
        assert item.expression
        assert item.kind in {
            "binary_adverse",
            "continuous_adverse",
            "continuous_beneficial",
            "descriptive",
        }
        assert item.direction in {"higher_worse", "higher_better", "descriptive"}


def test_dcf_fields_are_explicitly_quarantined() -> None:
    qualified = {column for column, _ in CODEBOOK_REQUIRED_COLUMNS}
    assert "profile_1.managment" in qualified
    assert "profile_1.school_category" in qualified
    assert "facility.building_status" in qualified
    assert "facility.comp_ict_lab_yn" in qualified
