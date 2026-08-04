from __future__ import annotations

from udise import state_accountability_a0_analysis as base

EXTRA_BUNDLES = (
    (
        "repair_no_internet",
        "Classroom major repair and no internet",
        ("any_major_repair", "no_internet"),
        "students",
        "physical deterioration plus digital exclusion",
    ),
    (
        "repair_no_core_device",
        "Classroom major repair and no laptop, tablet or desktop",
        ("any_major_repair", "no_core_digital_device"),
        "students",
        "physical deterioration plus digital exclusion",
    ),
    (
        "repair_digital_void",
        "Classroom major repair, no internet and no laptop, tablet or desktop",
        ("any_major_repair", "no_internet", "no_core_digital_device"),
        "students",
        "physical deterioration plus digital exclusion",
    ),
    (
        "furniture_digital_void",
        "Incomplete furniture, no internet and no laptop, tablet or desktop",
        ("incomplete_furniture", "no_internet", "no_core_digital_device"),
        "students",
        "capital under-provision plus digital exclusion",
    ),
    (
        "repair_library_digital_void",
        "Classroom major repair, no library, internet or core digital device",
        ("any_major_repair", "no_library", "no_internet", "no_core_digital_device"),
        "students",
        "physical and learning-technology underinvestment",
    ),
    (
        "repair_power_digital_void",
        "Classroom major repair, no functional electricity, internet or core device",
        (
            "any_major_repair",
            "no_functional_electricity",
            "no_internet",
            "no_core_digital_device",
        ),
        "students",
        "infrastructure-rooted digital exclusion",
    ),
    (
        "repair_digital_no_grant",
        "Classroom major repair, no internet or core device, and no grant",
        (
            "any_major_repair",
            "no_internet",
            "no_core_digital_device",
            "no_grant_received",
        ),
        "students",
        "physical and digital need without finance",
    ),
    (
        "repair_digital_no_inspection",
        "Classroom major repair, no internet or core device, and no inspection",
        (
            "any_major_repair",
            "no_internet",
            "no_core_digital_device",
            "no_academic_inspection",
        ),
        "students",
        "physical and digital need without oversight",
    ),
    (
        "repair_girls_toilet",
        "Classroom major repair and no functional girls' toilet",
        ("any_major_repair", "no_functional_girls_toilet"),
        "girls",
        "physical deterioration plus WASH under-provision",
    ),
    (
        "repair_water",
        "Classroom major repair and no functional drinking-water source",
        ("any_major_repair", "no_functional_water_source"),
        "students",
        "physical deterioration plus WASH under-provision",
    ),
    (
        "repair_handwash",
        "Classroom major repair and no toilet handwashing facility",
        ("any_major_repair", "no_handwash_near_toilet"),
        "students",
        "physical deterioration plus hygiene under-provision",
    ),
    (
        "repair_wash_failure",
        "Classroom major repair, no girls' toilet and no functional water",
        (
            "any_major_repair",
            "no_functional_girls_toilet",
            "no_functional_water_source",
        ),
        "girls",
        "physical deterioration plus WASH system failure",
    ),
    (
        "furniture_wash_failure",
        "Incomplete furniture, no girls' toilet and no functional water",
        (
            "incomplete_furniture",
            "no_functional_girls_toilet",
            "no_functional_water_source",
        ),
        "girls",
        "capital under-provision plus WASH system failure",
    ),
    (
        "repair_wash_no_response",
        "Classroom major repair, no girls' toilet and no grant or senior visit",
        (
            "any_major_repair",
            "no_functional_girls_toilet",
            "no_grant_received",
            "no_district_state_officer_visit",
        ),
        "girls",
        "physical and WASH need without response",
    ),
)

base.BUNDLES = base.BUNDLES + EXTRA_BUNDLES


def main() -> int:
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
