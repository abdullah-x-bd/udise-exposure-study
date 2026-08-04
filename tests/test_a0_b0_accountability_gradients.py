from udise.a0_b0_accountability_gradients import (
    BANDS,
    GEOGRAPHIES,
    GROUPS,
    SCOPES,
    calculate_contrasts,
    calculate_summaries,
    flag,
)


def test_run_contains_national_and_requested_top_five_states():
    codes = [item[0] for item in GEOGRAPHIES]
    assert codes == [
        "NATIONAL",
        "BIHAR",
        "UTTAR PRADESH",
        "JHARKHAND",
        "UTTARAKHAND",
        "ASSAM",
    ]


def test_main_comparison_is_a0_versus_b0():
    assert [item[0] for item in GROUPS] == ["A0", "B0"]
    assert "state_local_government" in SCOPES
    assert BANDS[0] == "0%"
    assert BANDS[8] == ">75-100%"


def test_compound_flag_requires_all_conditions_observed_and_adverse():
    expression = flag(("any_major_repair", "no_internet"))
    assert "any_major_repair IS NOT NULL" in expression
    assert "no_internet IS NOT NULL" in expression
    assert "any_major_repair=1" in expression
    assert "no_internet=1" in expression


def test_summary_uses_band_zero_for_equal_school_and_positive_band_for_weighted():
    gradients = []
    for estimand, low_order in (
        ("equal-school prevalence", 0),
        ("group-student-weighted exposure", 1),
    ):
        for group, low, high in (("A0", 10.0, 30.0), ("B0", 8.0, 12.0)):
            for order, value in ((low_order, low), (8, high)):
                gradients.append(
                    {
                        "management_scope": "state_local_government",
                        "geography_code": "NATIONAL",
                        "geography_label": "National",
                        "group_code": group,
                        "group_label": group,
                        "band_order": order,
                        "band": BANDS[order],
                        "schools": 100,
                        "group_students": 10000,
                        "estimand": estimand,
                        "bundle_code": "major_repair",
                        "bundle_label": "Classroom major repair",
                        "mechanism": "capital deterioration",
                        "components": "any_major_repair",
                        "weight_type": "students",
                        "exposure_percent": value,
                        "eligible_weight": 10000,
                        "affected_weight": value * 100,
                        "eligible_schools": 100,
                    }
                )
    contrasts = calculate_contrasts(gradients)
    summaries = calculate_summaries(contrasts)
    selected = [
        row
        for row in summaries
        if row["management_scope"] == "state_local_government"
        and row["geography_code"] == "NATIONAL"
        and row["bundle_code"] == "major_repair"
    ]
    equal = next(row for row in selected if row["estimand"] == "equal-school prevalence")
    weighted = next(
        row
        for row in selected
        if row["estimand"] == "group-student-weighted exposure"
    )
    assert equal["low_band"] == "0%"
    assert weighted["low_band"] == ">0-5%"
    assert equal["high_concentration_gap_pp"] == 18.0
    assert equal["gradient_difference_pp"] == 16.0
