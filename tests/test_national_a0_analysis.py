import duckdb

from udise.national_a0_analysis import BANDS, GROUPS, band_case


def test_a0_is_the_substantive_group_and_baselines_follow() -> None:
    assert GROUPS[0] == ("A0", "Muslim")
    assert [code for code, _ in GROUPS[1:]] == ["B0", "C0", "D0", "E0"]
    assert all("baseline" in label.lower() for _, label in GROUPS[1:])


def test_concentration_bands_cover_boundary_values() -> None:
    connection = duckdb.connect()
    values = [0, 0.0001, 0.05, 0.0501, 0.10, 0.20, 0.30, 0.40, 0.50, 0.75, 1.0]
    expected = [0, 1, 1, 2, 2, 3, 4, 5, 6, 7, 8]
    rows = ", ".join(f"({value})" for value in values)
    observed = [
        row[0]
        for row in connection.execute(
            f"SELECT {band_case('share')} AS band_order FROM (VALUES {rows}) AS t(share)"
        ).fetchall()
    ]
    connection.close()
    assert observed == expected


def test_band_order_is_complete_and_stable() -> None:
    assert [order for order, _ in BANDS] == list(range(9))
    assert BANDS[0][1] == "0%"
    assert BANDS[-1][1] == ">75-100%"
