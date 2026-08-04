from udise.refined_state_accountability_a0_analysis import EXTRA_BUNDLES


def test_refined_bundles_include_user_requested_physical_digital_interactions():
    codes = {item[0] for item in EXTRA_BUNDLES}
    assert "repair_digital_void" in codes
    assert "repair_library_digital_void" in codes
    assert "repair_power_digital_void" in codes


def test_refined_bundles_include_physical_wash_interactions():
    codes = {item[0] for item in EXTRA_BUNDLES}
    assert "repair_girls_toilet" in codes
    assert "repair_water" in codes
    assert "repair_wash_failure" in codes


def test_girls_toilet_interactions_use_girls_weights():
    for code, _, components, weight, _ in EXTRA_BUNDLES:
        if "no_functional_girls_toilet" in components:
            assert weight == "girls", code
