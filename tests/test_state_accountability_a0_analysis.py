from udise.state_accountability_a0_analysis import BUNDLES, SCOPES, flag


def test_direct_state_scope_excludes_aided_private_and_central_codes():
    scope = SCOPES["state_local_government"]
    assert "1,2,3,6,89,90" in scope
    for code in (4, 5, 7, 92, 93, 97, 99, 101):
        assert f",{code}," not in f",{scope},"


def test_accountability_bundles_cover_core_mechanisms():
    mechanisms = {item[4] for item in BUNDLES}
    assert "deferred maintenance" in mechanisms
    assert "compound public-investment failure" in mechanisms
    assert "digital system failure without response" in mechanisms
    assert "WASH need without oversight" in mechanisms


def test_combination_flag_requires_all_components_observed_and_adverse():
    expression = flag(("any_major_repair", "no_grant_received"))
    assert "any_major_repair IS NOT NULL" in expression
    assert "no_grant_received IS NOT NULL" in expression
    assert "any_major_repair=1" in expression
    assert "no_grant_received=1" in expression
