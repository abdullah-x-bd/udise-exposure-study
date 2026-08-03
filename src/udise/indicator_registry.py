from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable


@dataclass(frozen=True)
class Indicator:
    code: str
    level: str
    domain: str
    label: str
    expression: str
    kind: str
    weight: str = "students"
    applicability: str = "all schools with reported enrolment"
    sources: tuple[str, ...] = ()
    interpretation: str = ""
    limitation: str = ""
    supported: bool = True

    @property
    def direction(self) -> str:
        if self.kind in {"binary_adverse", "continuous_adverse"}:
            return "higher_worse"
        if self.kind == "continuous_beneficial":
            return "higher_better"
        return "descriptive"

    def as_row(self) -> dict[str, object]:
        row = asdict(self)
        row["sources"] = ", ".join(self.sources)
        row["direction"] = self.direction
        return row


def ratio(numerator: str, denominator: str, scale: float = 1.0) -> str:
    return f"(({numerator}) * {scale}) / NULLIF(({denominator}), 0)"


def no_yes1(column: str) -> str:
    return f"CASE WHEN {column} = 2 THEN 1 WHEN {column} = 1 THEN 0 ELSE NULL END"


def yes1(column: str) -> str:
    return f"CASE WHEN {column} = 1 THEN 1 WHEN {column} = 2 THEN 0 ELSE NULL END"


def applicable(condition: str, expression: str) -> str:
    return f"CASE WHEN {condition} THEN ({expression}) ELSE NULL END"


def null_mean(columns: Iterable[str], scale: float = 1.0) -> str:
    cols = tuple(columns)
    numerator = " + ".join(f"COALESCE({column}, 0)" for column in cols)
    denominator = " + ".join(
        f"CASE WHEN {column} IS NOT NULL THEN 1 ELSE 0 END" for column in cols
    )
    return f"(({numerator}) * {scale}) / NULLIF(({denominator}), 0)"


def indicator(
    code: str,
    domain: str,
    label: str,
    expression: str,
    kind: str,
    *,
    level: str = "secondary",
    weight: str = "students",
    applicability_text: str = "all schools with reported enrolment",
    sources: tuple[str, ...] = (),
    interpretation: str = "",
    limitation: str = "",
) -> Indicator:
    return Indicator(
        code=code,
        level=level,
        domain=domain,
        label=label,
        expression=expression,
        kind=kind,
        weight=weight,
        applicability=applicability_text,
        sources=sources,
        interpretation=interpretation,
        limitation=limitation,
    )


SECONDARY_INDICATORS: tuple[Indicator, ...] = (
    indicator("ends_before_class10", "access", "School ends before Class 10",
              "CASE WHEN highclass < 10 THEN 1 ELSE 0 END", "binary_adverse",
              sources=("profile_1.highclass",)),
    indicator("ends_before_class12", "access", "School ends before Class 12",
              "CASE WHEN highclass < 12 THEN 1 ELSE 0 END", "binary_adverse",
              sources=("profile_1.highclass",)),
    indicator("primary_only_school", "access", "School ends at or before Class 5",
              "CASE WHEN highclass <= 5 THEN 1 ELSE 0 END", "binary_adverse",
              sources=("profile_1.highclass",)),
    indicator("elementary_only_school", "access", "School ends at or before Class 8",
              "CASE WHEN highclass <= 8 THEN 1 ELSE 0 END", "binary_adverse",
              sources=("profile_1.highclass",)),
    indicator("no_all_weather_road", "access", "No all-weather road access",
              no_yes1("approachable_road"), "binary_adverse",
              sources=("profile_1.approachable_road",)),
    indicator("no_pre_primary", "access", "No attached pre-primary section",
              applicable("lowclass <= 1 AND highclass >= 1", no_yes1("pre_primary")),
              "binary_adverse", applicability_text="schools offering Class 1",
              sources=("profile_1.lowclass", "profile_1.highclass", "profile_1.pre_primary")),
    indicator("no_anganwadi", "access", "No Anganwadi inside school premises",
              applicable("lowclass <= 1 AND highclass >= 1", no_yes1("anganwadi_yn")),
              "binary_adverse", applicability_text="schools offering Class 1",
              sources=("profile_1.anganwadi_yn",)),
    indicator("no_balavatika", "access", "No Balavatika",
              applicable("lowclass <= 1 AND highclass >= 1", no_yes1("balavatika_located_yn")),
              "binary_adverse", applicability_text="schools offering Class 1",
              sources=("profile_2.balavatika_located_yn",)),
    indicator("shift_school_flag", "access", "Shift school",
              yes1("shift_school"), "binary_adverse",
              sources=("profile_1.shift_school",),
              limitation="Shift operation is treated as a pressure indicator, not automatically as poor quality."),
    indicator("no_special_training", "access", "No special training for out-of-school children",
              no_yes1("special_training"), "binary_adverse",
              sources=("profile_2.special_training",)),
    indicator("no_supplementary_material", "access", "No graded supplementary material",
              no_yes1("material_training"), "binary_adverse",
              sources=("profile_2.material_training",)),
    indicator("instructional_days", "access", "Average instructional days",
              "CAST(avg_instr_days AS DOUBLE)", "continuous_beneficial",
              sources=("profile_1.avg_instr_days",)),
    indicator("classrooms_per_100", "infrastructure", "Classrooms per 100 students",
              ratio("total_class_rooms", "total_students", 100.0), "continuous_beneficial",
              sources=("facility.total_class_rooms", "enrolment_1 social-category total")),
    indicator("students_per_classroom", "infrastructure", "Students per instructional classroom",
              ratio("total_students", "total_class_rooms"), "continuous_adverse",
              sources=("facility.total_class_rooms", "enrolment_1 social-category total")),
    indicator("good_classroom_share", "infrastructure", "Share of classrooms in good condition",
              ratio("classrooms_in_good_condition", "total_class_rooms"), "continuous_beneficial",
              sources=("facility.classrooms_in_good_condition", "facility.total_class_rooms")),
    indicator("minor_repair_classroom_share", "infrastructure", "Share of classrooms needing minor repair",
              ratio("classrooms_needs_minor_repair", "total_class_rooms"), "continuous_adverse",
              sources=("facility.classrooms_needs_minor_repair", "facility.total_class_rooms")),
    indicator("major_repair_classroom_share", "infrastructure", "Share of classrooms needing major repair",
              ratio("classrooms_needs_major_repair", "total_class_rooms"), "continuous_adverse",
              sources=("facility.classrooms_needs_major_repair", "facility.total_class_rooms")),
    indicator("any_major_repair", "infrastructure", "At least one classroom needs major repair",
              "CASE WHEN classrooms_needs_major_repair > 0 THEN 1 ELSE 0 END", "binary_adverse",
              sources=("facility.classrooms_needs_major_repair",)),
    indicator("no_head_teacher_room", "infrastructure", "No separate head-teacher room",
              no_yes1("separate_room_for_hm"), "binary_adverse",
              sources=("facility.separate_room_for_hm",)),
    indicator("incomplete_furniture", "infrastructure", "Furniture unavailable for all students",
              "CASE WHEN furniture_availability IN (2, 3) THEN 1 WHEN furniture_availability = 1 THEN 0 ELSE NULL END",
              "binary_adverse", sources=("facility.furniture_availability",)),
    indicator("no_furniture", "infrastructure", "No student furniture",
              "CASE WHEN furniture_availability = 3 THEN 1 WHEN furniture_availability IN (1, 2) THEN 0 ELSE NULL END",
              "binary_adverse", sources=("facility.furniture_availability",)),
    indicator("pucca_block_share", "infrastructure", "Share of building blocks that are pucca",
              ratio("pucca_building_blocks", "no_building_blocks"), "continuous_beneficial",
              sources=("facility.pucca_building_blocks", "facility.no_building_blocks")),
    indicator("no_functional_boys_toilet", "wash", "No functional boys' toilet",
              "CASE WHEN total_boys_func_toilet = 0 THEN 1 WHEN total_boys_func_toilet > 0 THEN 0 ELSE NULL END",
              "binary_adverse", sources=("facility.total_boys_func_toilet",)),
    indicator("no_functional_girls_toilet", "wash", "No functional girls' toilet",
              "CASE WHEN total_girls_func_toilet = 0 THEN 1 WHEN total_girls_func_toilet > 0 THEN 0 ELSE NULL END",
              "binary_adverse", weight="girls",
              sources=("facility.total_girls_func_toilet",)),
    indicator("functional_boys_toilet_rate", "wash", "Functional share of boys' toilet seats",
              ratio("total_boys_func_toilet", "total_boys_toilet"), "continuous_beneficial",
              sources=("facility.total_boys_func_toilet", "facility.total_boys_toilet")),
    indicator("functional_girls_toilet_rate", "wash", "Functional share of girls' toilet seats",
              ratio("total_girls_func_toilet", "total_girls_toilet"), "continuous_beneficial",
              weight="girls", sources=("facility.total_girls_func_toilet", "facility.total_girls_toilet")),
    indicator("boys_toilets_per_100_boys", "wash", "Functional boys' toilet seats per 100 boys",
              ratio("total_boys_func_toilet", "total_boys", 100.0), "continuous_beneficial",
              sources=("facility.total_boys_func_toilet", "enrolment_1 boys total")),
    indicator("girls_toilets_per_100_girls", "wash", "Functional girls' toilet seats per 100 girls",
              ratio("total_girls_func_toilet", "total_girls", 100.0), "continuous_beneficial",
              weight="girls", sources=("facility.total_girls_func_toilet", "enrolment_1 girls total")),
    indicator("no_functional_cwsn_toilet", "wash", "No functional CWSN-friendly toilet",
              "CASE WHEN COALESCE(func_boys_cwsn_friendly, 0) + COALESCE(func_girls_cwsn_friendly, 0) = 0 THEN 1 ELSE 0 END",
              "binary_adverse", sources=("facility.func_boys_cwsn_friendly", "facility.func_girls_cwsn_friendly")),
    indicator("no_handwash_near_toilet", "wash", "No handwashing with soap near toilets",
              no_yes1("handwash_near_toilet"), "binary_adverse",
              sources=("facility.handwash_near_toilet",)),
    indicator("no_handwash_for_meals", "wash", "No handwashing with soap for meals",
              no_yes1("handwash_facility_for_meal"), "binary_adverse",
              sources=("facility.handwash_facility_for_meal",)),
    indicator("no_functional_water_source", "wash", "No functional drinking-water source",
              """CASE WHEN
                    COALESCE(hand_pump_fun_yn, 2) <> 1
                AND COALESCE(well_prot_fun_yn, 2) <> 1
                AND COALESCE(tap_fun_yn, 2) <> 1
                AND COALESCE(othsrc_fun_yn, 2) <> 1
                AND COALESCE(well_unprot_fun_yn, 2) <> 1
                AND COALESCE(pack_water_fun_yn, 2) <> 1
                THEN 1 ELSE 0 END""", "binary_adverse",
              sources=("facility.hand_pump_fun_yn", "facility.well_prot_fun_yn",
                       "facility.tap_fun_yn", "facility.othsrc_fun_yn",
                       "facility.well_unprot_fun_yn", "facility.pack_water_fun_yn")),
    indicator("no_functional_tap_water", "wash", "No functional tap-water source",
              no_yes1("tap_fun_yn"), "binary_adverse",
              sources=("facility.tap_fun_yn",)),
    indicator("water_source_present_but_none_functional", "wash",
              "A water source is reported but none is functional",
              """CASE WHEN
                  (hand_pump_yn = 1 OR well_prot_yn = 1 OR tap_yn = 1 OR othsrc_yn = 1
                   OR well_unprot_yn = 1 OR pack_water_yn = 1)
                  AND
                  (COALESCE(hand_pump_fun_yn, 2) <> 1
                   AND COALESCE(well_prot_fun_yn, 2) <> 1
                   AND COALESCE(tap_fun_yn, 2) <> 1
                   AND COALESCE(othsrc_fun_yn, 2) <> 1
                   AND COALESCE(well_unprot_fun_yn, 2) <> 1
                   AND COALESCE(pack_water_fun_yn, 2) <> 1)
                  THEN 1 ELSE 0 END""", "binary_adverse",
              sources=("facility water-source availability and functionality fields",)),
    indicator("functional_unprotected_well", "wash", "Functional unprotected well reported",
              yes1("well_unprot_fun_yn"), "binary_adverse",
              sources=("facility.well_unprot_fun_yn",),
              limitation="This indicates exposure to an unprotected source but does not establish that it is the school's only source."),
    indicator("no_rainwater_harvesting", "wash", "No rainwater-harvesting provision",
              no_yes1("rain_water_harvesting"), "binary_adverse",
              sources=("facility.rain_water_harvesting",)),
    indicator("no_functional_electricity", "learning_environment", "No functional electricity connection",
              "CASE WHEN electricity_availability IN (2, 3) THEN 1 WHEN electricity_availability = 1 THEN 0 ELSE NULL END",
              "binary_adverse", sources=("facility.electricity_availability",)),
    indicator("no_electricity_connection", "learning_environment", "No electricity connection",
              "CASE WHEN electricity_availability = 2 THEN 1 WHEN electricity_availability IN (1, 3) THEN 0 ELSE NULL END",
              "binary_adverse", sources=("facility.electricity_availability",)),
    indicator("electricity_connection_nonfunctional", "learning_environment",
              "Electricity connection exists but is non-functional",
              "CASE WHEN electricity_availability = 3 THEN 1 WHEN electricity_availability IN (1, 2) THEN 0 ELSE NULL END",
              "binary_adverse", sources=("facility.electricity_availability",)),
    indicator("no_solar_panel", "learning_environment", "No solar panel",
              no_yes1("solar_panel"), "binary_adverse",
              sources=("facility.solar_panel",)),
    indicator("no_library", "learning_environment", "No library",
              no_yes1("library_availability"), "binary_adverse",
              sources=("facility.library_availability",)),
    indicator("no_book_bank", "learning_environment", "No book bank",
              no_yes1("book_bank"), "binary_adverse",
              sources=("facility.book_bank",)),
    indicator("no_reading_corner", "learning_environment", "No reading corner",
              no_yes1("reading_corner"), "binary_adverse",
              sources=("facility.reading_corner",)),
    indicator("no_play_access", "learning_environment", "No playground or alternative play arrangement",
              "CASE WHEN playground_available = 2 AND playground_alt_yn = 2 THEN 1 "
              "WHEN playground_available = 1 OR playground_alt_yn = 1 THEN 0 ELSE NULL END",
              "binary_adverse", sources=("facility.playground_available", "facility.playground_alt_yn")),
    indicator("no_medical_checkup", "learning_environment", "No student medical check-up in the previous year",
              no_yes1("medical_checkups"), "binary_adverse",
              sources=("facility.medical_checkups",)),
    indicator("no_internet", "digital", "No internet access",
              no_yes1("internet"), "binary_adverse",
              sources=("facility.internet",)),
    indicator("no_core_digital_device", "digital", "No laptop, tablet or desktop",
              "CASE WHEN COALESCE(laptop, 0) + COALESCE(tablet, 0) + COALESCE(desktop, 0) = 0 THEN 1 ELSE 0 END",
              "binary_adverse", sources=("facility.laptop", "facility.tablet", "facility.desktop")),
    indicator("core_devices_per_100", "digital", "Laptops, tablets and desktops per 100 students",
              ratio("COALESCE(laptop, 0) + COALESCE(tablet, 0) + COALESCE(desktop, 0)",
                    "total_students", 100.0), "continuous_beneficial",
              sources=("facility.laptop", "facility.tablet", "facility.desktop", "enrolment total")),
    indicator("no_digital_board", "digital", "No digital board",
              "CASE WHEN COALESCE(digiboard, 0) = 0 THEN 1 ELSE 0 END", "binary_adverse",
              sources=("facility.digiboard",)),
    indicator("no_smart_classroom", "digital", "No smart classroom",
              "CASE WHEN COALESCE(smart_class_tv_tot, 0) = 0 THEN 1 ELSE 0 END", "binary_adverse",
              sources=("facility.smart_class_tv_tot",)),
    indicator("no_projector", "digital", "No projector",
              "CASE WHEN COALESCE(projector, 0) = 0 THEN 1 ELSE 0 END", "binary_adverse",
              sources=("facility.projector",)),
    indicator("no_printer", "digital", "No printer",
              "CASE WHEN COALESCE(printer, 0) = 0 THEN 1 ELSE 0 END", "binary_adverse",
              sources=("facility.printer",)),
    indicator("no_server", "digital", "No server",
              "CASE WHEN COALESCE(server_tot, 0) = 0 THEN 1 ELSE 0 END", "binary_adverse",
              sources=("facility.server_tot",)),
    indicator("no_dth", "digital", "No DTH or television-channel access",
              no_yes1("dth"), "binary_adverse",
              sources=("facility.dth",)),
    indicator("student_teacher_ratio", "teachers", "Students per teacher",
              ratio("total_students", "total_tch"), "continuous_adverse",
              sources=("teacher.total_tch", "enrolment total")),
    indicator("teachers_per_100", "teachers", "Teachers per 100 students",
              ratio("total_tch", "total_students", 100.0), "continuous_beneficial",
              sources=("teacher.total_tch", "enrolment total")),
    indicator("single_teacher_school", "teachers", "Single-teacher school",
              "CASE WHEN total_tch = 1 THEN 1 ELSE 0 END", "binary_adverse",
              sources=("teacher.total_tch",)),
    indicator("two_or_fewer_teachers", "teachers", "School with two or fewer teachers",
              "CASE WHEN total_tch <= 2 THEN 1 ELSE 0 END", "binary_adverse",
              sources=("teacher.total_tch",)),
    indicator("str_above_30", "teachers", "Student-teacher ratio above 30",
              "CASE WHEN total_tch > 0 AND total_students * 1.0 / total_tch > 30 THEN 1 ELSE 0 END",
              "binary_adverse", sources=("teacher.total_tch", "enrolment total")),
    indicator("str_above_40", "teachers", "Student-teacher ratio above 40",
              "CASE WHEN total_tch > 0 AND total_students * 1.0 / total_tch > 40 THEN 1 ELSE 0 END",
              "binary_adverse", sources=("teacher.total_tch", "enrolment total")),
    indicator("str_above_50", "teachers", "Student-teacher ratio above 50",
              "CASE WHEN total_tch > 0 AND total_students * 1.0 / total_tch > 50 THEN 1 ELSE 0 END",
              "binary_adverse", sources=("teacher.total_tch", "enrolment total")),
    indicator("no_female_teacher", "teachers", "No female teacher",
              "CASE WHEN total_tch > 0 AND COALESCE(female, 0) = 0 THEN 1 "
              "WHEN total_tch > 0 THEN 0 ELSE NULL END", "binary_adverse",
              weight="girls", sources=("teacher.total_tch", "teacher.female")),
    indicator("female_teacher_share", "teachers", "Female share of teachers",
              ratio("female", "total_tch"), "continuous_beneficial",
              weight="girls", sources=("teacher.female", "teacher.total_tch")),
    indicator("no_regular_teacher", "teachers", "No regular teacher",
              "CASE WHEN total_tch > 0 AND COALESCE(regular, 0) = 0 THEN 1 "
              "WHEN total_tch > 0 THEN 0 ELSE NULL END", "binary_adverse",
              sources=("teacher.regular", "teacher.total_tch")),
    indicator("contract_teacher_share", "teachers", "Contract-teacher share",
              ratio("contract", "total_tch"), "continuous_adverse",
              sources=("teacher.contract", "teacher.total_tch")),
    indicator("part_time_teacher_share", "teachers", "Part-time-teacher share",
              ratio("part_time", "total_tch"), "continuous_adverse",
              sources=("teacher.part_time", "teacher.total_tch")),
    indicator("below_graduate_teacher_share", "teachers", "Below-graduate teacher share",
              ratio("below_graduate", "total_tch"), "continuous_adverse",
              sources=("teacher.below_graduate", "teacher.total_tch")),
    indicator("postgraduate_teacher_share", "teachers", "Postgraduate-and-above teacher share",
              ratio("post_graduate_and_above", "total_tch"), "continuous_beneficial",
              sources=("teacher.post_graduate_and_above", "teacher.total_tch")),
    indicator("no_computer_trained_teacher", "teachers", "No computer-trained teacher",
              "CASE WHEN total_tch > 0 AND COALESCE(trained_comp, 0) = 0 THEN 1 "
              "WHEN total_tch > 0 THEN 0 ELSE NULL END", "binary_adverse",
              sources=("teacher.trained_comp", "teacher.total_tch")),
    indicator("computer_trained_teacher_share", "teachers", "Computer-trained teacher share",
              ratio("trained_comp", "total_tch"), "continuous_beneficial",
              sources=("teacher.trained_comp", "teacher.total_tch")),
    indicator("no_cwsn_trained_teacher", "teachers", "No CWSN-trained teacher",
              "CASE WHEN total_tch > 0 AND COALESCE(trained_cwsn, 0) = 0 THEN 1 "
              "WHEN total_tch > 0 THEN 0 ELSE NULL END", "binary_adverse",
              sources=("teacher.trained_cwsn", "teacher.total_tch")),
    indicator("cwsn_trained_teacher_share", "teachers", "CWSN-trained teacher share",
              ratio("trained_cwsn", "total_tch"), "continuous_beneficial",
              sources=("teacher.trained_cwsn", "teacher.total_tch")),
    indicator("no_special_educator", "teachers", "No dedicated or cluster-level special educator",
              "CASE WHEN spl_educator_yn = 3 THEN 1 WHEN spl_educator_yn IN (1, 2) THEN 0 ELSE NULL END",
              "binary_adverse", sources=("facility.spl_educator_yn",)),
    indicator("professionally_unqualified_teacher_share", "teachers",
              "Teacher share with no professional qualification",
              ratio('"none"', "total_tch"), "continuous_adverse",
              sources=("teacher.none", "teacher.total_tch")),
    indicator("non_training_assignment_teacher_share", "teachers",
              "Teacher share involved in non-training assignments",
              ratio("teacher_involve_non_training_assignment", "total_tch"), "continuous_adverse",
              sources=("teacher.teacher_involve_non_training_assignment", "teacher.total_tch")),
    indicator("no_primary_teacher", "teachers", "No teacher covering primary grades",
              applicable("lowclass <= 5 AND highclass >= 1",
                         "CASE WHEN COALESCE(class_taught_pr, 0) + COALESCE(class_taught_pr_upr, 0) "
                         "+ COALESCE(class_taught_pr_and_pre_pri, 0) = 0 THEN 1 ELSE 0 END"),
              "binary_adverse", applicability_text="schools offering primary grades",
              sources=("teacher class-taught fields", "profile class span")),
    indicator("no_upper_primary_teacher", "teachers", "No teacher covering upper-primary grades",
              applicable("lowclass <= 8 AND highclass >= 6",
                         "CASE WHEN COALESCE(class_taught_upr, 0) + COALESCE(class_taught_pr_upr, 0) "
                         "+ COALESCE(class_taught_upr_sec, 0) = 0 THEN 1 ELSE 0 END"),
              "binary_adverse", applicability_text="schools offering upper-primary grades",
              sources=("teacher class-taught fields", "profile class span")),
    indicator("no_secondary_teacher", "teachers", "No teacher covering secondary grades",
              applicable("lowclass <= 10 AND highclass >= 9",
                         "CASE WHEN COALESCE(class_taught_sec_only, 0) + COALESCE(class_taught_upr_sec, 0) "
                         "+ COALESCE(class_taught_sec_hsec, 0) = 0 THEN 1 ELSE 0 END"),
              "binary_adverse", applicability_text="schools offering secondary grades",
              sources=("teacher class-taught fields", "profile class span")),
    indicator("no_higher_secondary_teacher", "teachers", "No teacher covering higher-secondary grades",
              applicable("lowclass <= 12 AND highclass >= 11",
                         "CASE WHEN COALESCE(class_taught_hsec_only, 0) + COALESCE(class_taught_sec_hsec, 0) = 0 "
                         "THEN 1 ELSE 0 END"),
              "binary_adverse", applicability_text="schools offering higher-secondary grades",
              sources=("teacher class-taught fields", "profile class span")),
    indicator("no_academic_inspection", "governance", "No academic inspection",
              "CASE WHEN COALESCE(acad_inspections, 0) = 0 THEN 1 ELSE 0 END", "binary_adverse",
              sources=("profile_2.acad_inspections",)),
    indicator("no_crc_visit", "governance", "No CRC coordinator visit",
              "CASE WHEN COALESCE(crc_coordinator, 0) = 0 THEN 1 ELSE 0 END", "binary_adverse",
              sources=("profile_2.crc_coordinator",)),
    indicator("no_block_officer_visit", "governance", "No block-level officer visit",
              "CASE WHEN COALESCE(block_level_officers, 0) = 0 THEN 1 ELSE 0 END", "binary_adverse",
              sources=("profile_2.block_level_officers",)),
    indicator("no_district_state_officer_visit", "governance", "No district or state officer visit",
              "CASE WHEN COALESCE(district_officers, 0) = 0 THEN 1 ELSE 0 END", "binary_adverse",
              sources=("profile_2.district_officers",)),
    indicator("administrative_contacts", "governance", "Total inspections and administrative visits",
              "COALESCE(acad_inspections, 0) + COALESCE(crc_coordinator, 0) "
              "+ COALESCE(block_level_officers, 0) + COALESCE(district_officers, 0)",
              "continuous_beneficial", sources=("profile_2 inspection and visit fields",)),
    indicator("no_smc", "governance", "No School Management Committee",
              no_yes1("smc_exists"), "binary_adverse",
              sources=("profile_2.smc_exists",)),
    indicator("no_smc_meeting", "governance", "No SMC or SMDC meeting",
              "CASE WHEN COALESCE(smc_smdc_meetings, 0) = 0 THEN 1 ELSE 0 END", "binary_adverse",
              sources=("profile_2.smc_smdc_meetings",)),
    indicator("grant_per_student", "governance", "Grant received per student",
              ratio("grants_receipt", "total_students"), "continuous_beneficial",
              sources=("profile_2.grants_receipt", "enrolment total")),
    indicator("expenditure_per_student", "governance", "Grant expenditure per student",
              ratio("grants_expenditure", "total_students"), "continuous_beneficial",
              sources=("profile_2.grants_expenditure", "enrolment total")),
    indicator("grant_utilisation_rate", "governance", "Grant expenditure divided by grant receipt",
              ratio("grants_expenditure", "grants_receipt"), "continuous_beneficial",
              sources=("profile_2.grants_expenditure", "profile_2.grants_receipt"),
              limitation="Values can exceed one when expenditure includes balances or accounting timing differences."),
    indicator("no_grant_received", "governance", "No grant received",
              "CASE WHEN COALESCE(grants_receipt, 0) = 0 THEN 1 ELSE 0 END", "binary_adverse",
              sources=("profile_2.grants_receipt",)),
    indicator("grant_received_no_expenditure", "governance", "Grant received but no expenditure reported",
              "CASE WHEN grants_receipt > 0 AND COALESCE(grants_expenditure, 0) = 0 THEN 1 ELSE 0 END",
              "binary_adverse", sources=("profile_2.grants_receipt", "profile_2.grants_expenditure")),
    indicator("no_free_textbooks_primary", "welfare", "No free textbooks in primary grades",
              applicable("lowclass <= 5 AND highclass >= 1", no_yes1("free_text_books_pr")),
              "binary_adverse", applicability_text="schools offering primary grades",
              sources=("profile_2.free_text_books_pr",)),
    indicator("no_free_uniform_primary", "welfare", "No free uniforms in primary grades",
              applicable("lowclass <= 5 AND highclass >= 1", no_yes1("free_uniform_pr")),
              "binary_adverse", applicability_text="schools offering primary grades",
              sources=("profile_2.free_uniform_pr",)),
    indicator("no_free_textbooks_upper_primary", "welfare", "No free textbooks in upper-primary grades",
              applicable("lowclass <= 8 AND highclass >= 6", no_yes1("free_text_books_up")),
              "binary_adverse", applicability_text="schools offering upper-primary grades",
              sources=("profile_2.free_text_books_up",)),
    indicator("no_free_uniform_upper_primary", "welfare", "No free uniforms in upper-primary grades",
              applicable("lowclass <= 8 AND highclass >= 6", no_yes1("free_uniform_up")),
              "binary_adverse", applicability_text="schools offering upper-primary grades",
              sources=("profile_2.free_uniform_up",)),
    indicator("no_ramp", "inclusion", "No ramp",
              no_yes1("availability_ramps"), "binary_adverse",
              sources=("facility.availability_ramps",)),
    indicator("ramp_without_handrail", "inclusion", "Ramp present without handrail",
              "CASE WHEN availability_ramps = 1 AND availability_of_handrails = 2 THEN 1 "
              "WHEN availability_ramps = 1 AND availability_of_handrails = 1 THEN 0 ELSE NULL END",
              "binary_adverse", applicability_text="schools reporting a ramp",
              sources=("facility.availability_ramps", "facility.availability_of_handrails")),
    indicator("cwsn_no_ramp", "inclusion", "CWSN students enrolled but no ramp",
              applicable("cwsn_students > 0", no_yes1("availability_ramps")),
              "binary_adverse", applicability_text="schools reporting CWSN enrolment",
              sources=("enrolment_1 CWSN count", "facility.availability_ramps")),
    indicator("cwsn_no_accessible_toilet", "inclusion",
              "CWSN students enrolled but no functional CWSN-friendly toilet",
              applicable("cwsn_students > 0",
                         "CASE WHEN COALESCE(func_boys_cwsn_friendly, 0) + "
                         "COALESCE(func_girls_cwsn_friendly, 0) = 0 THEN 1 ELSE 0 END"),
              "binary_adverse", applicability_text="schools reporting CWSN enrolment",
              sources=("enrolment_1 CWSN count", "facility CWSN toilet fields")),
    indicator("cwsn_no_special_educator", "inclusion",
              "CWSN students enrolled but no special educator",
              applicable("cwsn_students > 0",
                         "CASE WHEN spl_educator_yn = 3 THEN 1 WHEN spl_educator_yn IN (1, 2) THEN 0 ELSE NULL END"),
              "binary_adverse", applicability_text="schools reporting CWSN enrolment",
              sources=("enrolment_1 CWSN count", "facility.spl_educator_yn")),
    indicator("cwsn_no_trained_teacher", "inclusion",
              "CWSN students enrolled but no CWSN-trained teacher",
              applicable("cwsn_students > 0", "CASE WHEN COALESCE(trained_cwsn, 0) = 0 THEN 1 ELSE 0 END"),
              "binary_adverse", applicability_text="schools reporting CWSN enrolment",
              sources=("enrolment_1 CWSN count", "teacher.trained_cwsn")),
    indicator("bpl_share", "vulnerability", "BPL enrolment share in the school",
              ratio("bpl_students", "total_students"), "continuous_adverse",
              sources=("enrolment_1 BPL item", "enrolment total"),
              limitation="This is a school-level marginal share, not the BPL share among Muslims."),
    indicator("ews_share", "vulnerability", "EWS enrolment share in the school",
              ratio("ews_students", "total_students"), "continuous_adverse",
              sources=("enrolment_1 EWS item", "enrolment total"),
              limitation="This is a school-level marginal share, not the EWS share among Muslims."),
    indicator("repeater_share", "vulnerability", "Repeater enrolment share in the school",
              ratio("repeater_students", "total_students"), "continuous_adverse",
              sources=("enrolment_1 repeater item", "enrolment total"),
              limitation="This is a school-level marginal share, not the repeater share among Muslims."),
    indicator("cwsn_share", "vulnerability", "CWSN enrolment share in the school",
              ratio("cwsn_students", "total_students"), "continuous_adverse",
              sources=("enrolment_1 disability items", "enrolment total"),
              limitation="This is a school-level marginal share, not the CWSN share among Muslims."),
    indicator("over_age_share", "age_grade", "Over-age enrolment share",
              ratio("over_age_students", "age_class_students"), "continuous_adverse",
              sources=("enrolment_2 age-by-class records",),
              limitation="Age is not cross-tabulated with religion or social category."),
    indicator("under_age_share", "age_grade", "Under-age enrolment share",
              ratio("under_age_students", "age_class_students"), "continuous_adverse",
              sources=("enrolment_2 age-by-class records",),
              limitation="Age is not cross-tabulated with religion or social category."),
    indicator("on_age_share", "age_grade", "Enrolment within the configured age-grade band",
              ratio("on_age_students", "age_class_students"), "continuous_beneficial",
              sources=("enrolment_2 age-by-class records",),
              limitation="Uses a one-year tolerance around the nominal class age."),
)

ACCESS_SCORE_COLUMNS = ("ends_before_class10", "ends_before_class12", "no_all_weather_road", "no_pre_primary", "no_anganwadi", "no_balavatika")
INFRASTRUCTURE_SCORE_COLUMNS = ("any_major_repair", "no_head_teacher_room", "incomplete_furniture", "no_functional_electricity", "no_library", "no_play_access")
WASH_SCORE_COLUMNS = ("no_functional_boys_toilet", "no_functional_girls_toilet", "no_functional_water_source", "no_handwash_near_toilet", "no_handwash_for_meals")
DIGITAL_SCORE_COLUMNS = ("no_internet", "no_core_digital_device", "no_digital_board", "no_smart_classroom", "no_projector", "no_computer_trained_teacher", "no_functional_electricity")
TEACHER_SCORE_COLUMNS = ("two_or_fewer_teachers", "str_above_30", "no_female_teacher", "no_regular_teacher", "no_computer_trained_teacher", "no_cwsn_trained_teacher", "no_primary_teacher", "no_upper_primary_teacher", "no_secondary_teacher", "no_higher_secondary_teacher")
GOVERNANCE_SCORE_COLUMNS = ("no_academic_inspection", "no_crc_visit", "no_block_officer_visit", "no_district_state_officer_visit", "no_smc", "no_smc_meeting", "no_grant_received")
WELFARE_SCORE_COLUMNS = ("no_free_textbooks_primary", "no_free_uniform_primary", "no_free_textbooks_upper_primary", "no_free_uniform_upper_primary", "no_special_training", "no_supplementary_material")
INCLUSION_SCORE_COLUMNS = ("cwsn_no_ramp", "cwsn_no_accessible_toilet", "cwsn_no_special_educator", "cwsn_no_trained_teacher")

TERTIARY_INDICATORS: tuple[Indicator, ...] = (
    indicator("access_deprivation_index", "tertiary_access", "Access deprivation index", null_mean(ACCESS_SCORE_COLUMNS, 100.0), "continuous_adverse", level="tertiary", sources=tuple(ACCESS_SCORE_COLUMNS), interpretation="Equal-weight mean of available adverse access indicators."),
    indicator("infrastructure_deprivation_index", "tertiary_infrastructure", "Infrastructure deprivation index", null_mean(INFRASTRUCTURE_SCORE_COLUMNS, 100.0), "continuous_adverse", level="tertiary", sources=tuple(INFRASTRUCTURE_SCORE_COLUMNS)),
    indicator("wash_deprivation_index", "tertiary_wash", "Water, sanitation and hygiene deprivation index", null_mean(WASH_SCORE_COLUMNS, 100.0), "continuous_adverse", level="tertiary", sources=tuple(WASH_SCORE_COLUMNS)),
    indicator("digital_deprivation_index", "tertiary_digital", "Digital deprivation index", null_mean(DIGITAL_SCORE_COLUMNS, 100.0), "continuous_adverse", level="tertiary", sources=tuple(DIGITAL_SCORE_COLUMNS)),
    indicator("teacher_capacity_deprivation_index", "tertiary_teachers", "Teacher-capacity deprivation index", null_mean(TEACHER_SCORE_COLUMNS, 100.0), "continuous_adverse", level="tertiary", sources=tuple(TEACHER_SCORE_COLUMNS)),
    indicator("governance_response_deficit_index", "tertiary_governance", "Governance and response deficit index", null_mean(GOVERNANCE_SCORE_COLUMNS, 100.0), "continuous_adverse", level="tertiary", sources=tuple(GOVERNANCE_SCORE_COLUMNS)),
    indicator("welfare_support_deficit_index", "tertiary_welfare", "Welfare-support deficit index", null_mean(WELFARE_SCORE_COLUMNS, 100.0), "continuous_adverse", level="tertiary", sources=tuple(WELFARE_SCORE_COLUMNS)),
    indicator("inclusion_failure_index", "tertiary_inclusion", "CWSN inclusion-failure index", null_mean(INCLUSION_SCORE_COLUMNS, 100.0), "continuous_adverse", level="tertiary", applicability_text="schools reporting CWSN enrolment", sources=tuple(INCLUSION_SCORE_COLUMNS)),
    indicator("gendered_school_disadvantage_index", "tertiary_gender", "Gendered school-environment disadvantage index", null_mean(("no_functional_girls_toilet", "no_female_teacher", "ends_before_class12", "no_functional_water_source"), 100.0), "continuous_adverse", level="tertiary", weight="girls", sources=("no_functional_girls_toilet", "no_female_teacher", "ends_before_class12", "no_functional_water_source"), interpretation="School-environment index weighted by girls for exposure estimates."),
    indicator("educational_resource_deficit_index", "tertiary_resources", "Educational-resource deficit index", null_mean(("infrastructure_deprivation_index", "digital_deprivation_index", "teacher_capacity_deprivation_index"), 1.0), "continuous_adverse", level="tertiary", sources=("infrastructure_deprivation_index", "digital_deprivation_index", "teacher_capacity_deprivation_index")),
    indicator("institutional_need_index", "tertiary_need", "Documented institutional need index", null_mean(("access_deprivation_index", "infrastructure_deprivation_index", "wash_deprivation_index", "teacher_capacity_deprivation_index"), 1.0), "continuous_adverse", level="tertiary", sources=("access_deprivation_index", "infrastructure_deprivation_index", "wash_deprivation_index", "teacher_capacity_deprivation_index")),
    indicator("institutional_neglect_index", "tertiary_neglect", "Institutional neglect interaction index", "(institutional_need_index * governance_response_deficit_index) / 100.0", "continuous_adverse", level="tertiary", sources=("institutional_need_index", "governance_response_deficit_index"), interpretation="High only when documented need and weak institutional response coexist.", limitation="This is an analytical interaction, not direct evidence of intent."),
    indicator("overall_multidimensional_deprivation_index", "tertiary_overall", "Overall multidimensional school deprivation index", null_mean(("access_deprivation_index", "infrastructure_deprivation_index", "wash_deprivation_index", "digital_deprivation_index", "teacher_capacity_deprivation_index", "governance_response_deficit_index", "welfare_support_deficit_index"), 1.0), "continuous_adverse", level="tertiary", sources=("all domain deprivation indices",), interpretation="Equal-weight summary. Domain and individual results remain primary."),
    indicator("vulnerability_context_index", "tertiary_vulnerability", "Within-state vulnerability-context percentile index", null_mean(("bpl_percentile", "ews_percentile", "repeater_percentile", "cwsn_percentile"), 100.0), "continuous_adverse", level="tertiary", sources=("bpl_share", "ews_share", "repeater_share", "cwsn_share"), interpretation="Mean within-state percentile rank of four school-level vulnerability shares.", limitation="The underlying categories can overlap and are not cross-tabulated with Muslim identity."),
    indicator("compound_vulnerability_deprivation_index", "tertiary_compound", "Compound vulnerability and school-deprivation interaction", "(vulnerability_context_index * overall_multidimensional_deprivation_index) / 100.0", "continuous_adverse", level="tertiary", sources=("vulnerability_context_index", "overall_multidimensional_deprivation_index"), interpretation="High only where a relatively vulnerable school population and multidimensional deprivation coexist."),
)

ALL_INDICATORS: tuple[Indicator, ...] = SECONDARY_INDICATORS + TERTIARY_INDICATORS

CODEBOOK_REQUIRED_COLUMNS: tuple[tuple[str, str], ...] = (
    ("profile_1.rural_urban", "School-location code"),
    ("profile_1.school_category", "School-category code"),
    ("profile_1.school_type", "School-type code"),
    ("profile_1.managment", "Management code"),
    ("profile_1.resi_type", "Residential-school type"),
    ("profile_1.medium_instr1", "Medium of instruction 1"),
    ("profile_1.medium_of_instr2", "Medium of instruction 2"),
    ("profile_1.medium_of_instr3", "Medium of instruction 3"),
    ("profile_1.medium_of_instr4", "Medium of instruction 4"),
    ("profile_1.aff_board_sec", "Secondary affiliation board"),
    ("profile_1.aff_board_hsec", "Higher-secondary affiliation board"),
    ("facility.building_status", "Building-status code"),
    ("facility.boundary_wall", "Boundary-wall code"),
    ("facility.phy_lab_cond", "Physics-laboratory condition"),
    ("facility.chem_lab_cond", "Chemistry-laboratory condition"),
    ("facility.bio_lab_cond", "Biology-laboratory condition"),
    ("facility.math_lab_cond", "Mathematics-laboratory condition"),
    ("facility.lang_lab_cond", "Language-laboratory condition"),
    ("facility.geo_lab_cond", "Geography-laboratory condition"),
    ("facility.home_sc_lab_cond", "Home-science laboratory condition"),
    ("facility.psycho_lab_cond", "Psychology-laboratory condition"),
    ("facility.comp_lab_cond", "Computer-science laboratory condition"),
    ("facility.comp_ict_lab_yn", "Computer or ICT laboratory code"),
    ("facility.ict_lab_yn", "Samagra Shiksha ICT-laboratory code"),
)


def validate_registry() -> None:
    codes = [item.code for item in ALL_INDICATORS]
    duplicates = sorted({code for code in codes if codes.count(code) > 1})
    if duplicates:
        raise ValueError(f"Duplicate indicator codes: {duplicates}")
    valid_kinds = {"binary_adverse", "continuous_adverse", "continuous_beneficial", "descriptive"}
    invalid = [item.code for item in ALL_INDICATORS if item.kind not in valid_kinds]
    if invalid:
        raise ValueError(f"Invalid indicator kinds: {invalid}")
