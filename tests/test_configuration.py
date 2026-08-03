from pathlib import Path

from udise.inspect_data import load_yaml, resolve_archives


UPLOADED_FILES = [
    ".gitattributes",
    "enrolment_data_1_All State_2024-25 (1).zip",
    "enrolment_data_2_All State_2024-25 (1).zip",
    "facility_data_All State_2024-25 (1).zip",
    "profile_data_1_All State_2024-25 (1).zip",
    "profile_data_2_All State_2024-25 (1).zip",
    "teacher_data_All State_2024-25 (1).zip",
]


def test_dataset_config_resolves_all_uploaded_archives() -> None:
    config = load_yaml(Path("config/dataset.yml"))
    resolved = resolve_archives(UPLOADED_FILES, config["archives"])

    assert set(resolved) == {
        "profile_1",
        "profile_2",
        "facility",
        "enrolment_1",
        "enrolment_2",
        "teacher",
    }
    assert len(set(resolved.values())) == 6


def test_each_schema_requires_pseudocode() -> None:
    schemas = load_yaml(Path("config/expected_schema.yml"))

    assert set(schemas) == {
        "profile_1",
        "profile_2",
        "facility",
        "enrolment_1",
        "enrolment_2",
        "teacher",
    }
    for schema in schemas.values():
        assert "pseudocode" in schema["required"]
        assert set(schema["required"]).issubset(schema["expected"])
