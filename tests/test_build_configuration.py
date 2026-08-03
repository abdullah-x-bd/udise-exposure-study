from pathlib import Path

from udise.build_data import TABLE_ORDER, load_yaml, table_type_map


def test_every_source_has_a_type_configuration() -> None:
    schemas = load_yaml(Path("config/expected_schema.yml"))
    types = load_yaml(Path("config/data_types.yml"))

    assert set(TABLE_ORDER) == set(schemas) == set(types)


def test_type_maps_cover_expected_columns() -> None:
    schemas = load_yaml(Path("config/expected_schema.yml"))
    types = load_yaml(Path("config/data_types.yml"))

    for table_name in TABLE_ORDER:
        mapping = table_type_map(table_name, schemas, types)
        assert list(mapping) == schemas[table_name]["expected"]
        assert mapping["pseudocode"] == "BIGINT"


def test_text_and_grant_types_are_explicit() -> None:
    schemas = load_yaml(Path("config/expected_schema.yml"))
    types = load_yaml(Path("config/data_types.yml"))

    profile_types = table_type_map("profile_1", schemas, types)
    assert profile_types["state"] == "VARCHAR"
    assert profile_types["district"] == "VARCHAR"
    assert profile_types["pincode"] == "BIGINT"

    profile_2_types = table_type_map("profile_2", schemas, types)
    assert profile_2_types["grants_receipt"] == "DOUBLE"
    assert profile_2_types["grants_expenditure"] == "DOUBLE"
