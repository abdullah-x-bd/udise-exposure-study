from udise.compound_state_a0_analysis import combinations


def test_compound_combinations_are_unique_and_deep():
    items = combinations()
    assert len(items) >= 286
    assert len({item.code for item in items}) == len(items)
    assert all(len(item.members) >= 2 for item in items)
    assert any(len(item.members) >= 4 for item in items)


def test_gendered_combinations_use_girls_weighting():
    items = combinations()
    gendered = [item for item in items if "no_female_teacher" in item.code]
    assert gendered
    assert all(item.girls_weighted for item in gendered)


def test_non_gendered_combination_uses_student_weighting():
    items = {item.code: item for item in combinations()}
    item = items["ends_before_class12__and__no_library"]
    assert not item.girls_weighted
