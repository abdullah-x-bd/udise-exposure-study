from __future__ import annotations

import duckdb

from udise.comprehensive_a0_analysis import (
    GROUPS,
    create_age_grade_table,
    create_social_composition,
    sql_identifier,
    sql_string,
)
from udise.indicator_registry import (
    ALL_INDICATORS,
    SECONDARY_INDICATORS,
    TERTIARY_INDICATORS,
)


def create_indicator_tables_low_memory(
    connection: duckdb.DuckDBPyConnection,
) -> None:
    """Build the school indicator relation with projection-prunable views.

    The original implementation materialised several very wide intermediate
    tables at the same time. On a GitHub-hosted runner this filled the DuckDB
    temporary directory. This implementation keeps only the expensive
    enrolment aggregates materialised, drops their raw intermediate tables,
    and expresses every subsequent transformation as a view. DuckDB can then
    prune unused source columns before the final Parquet COPY.
    """

    create_social_composition(connection)
    connection.execute("DROP TABLE IF EXISTS enrolment_components")
    connection.execute("DROP TABLE IF EXISTS social_composition_raw")

    create_age_grade_table(connection)

    secondary_select = ",\n".join(
        f"({item.expression}) AS {sql_identifier(item.code)}"
        for item in SECONDARY_INDICATORS
    )
    connection.execute(
        f"""
        CREATE OR REPLACE TEMP VIEW school_secondary AS
        SELECT
            m.*,
            s.* EXCLUDE (pseudocode),
            a.age_class_students,
            a.over_age_students,
            a.under_age_students,
            a.on_age_students,
            {secondary_select}
        FROM school_master_base AS m
        INNER JOIN social_composition AS s USING (pseudocode)
        LEFT JOIN age_grade_environment AS a USING (pseudocode)
        WHERE s.total_students > 0
        """
    )

    initial_codes = {
        "access_deprivation_index",
        "infrastructure_deprivation_index",
        "wash_deprivation_index",
        "digital_deprivation_index",
        "teacher_capacity_deprivation_index",
        "governance_response_deficit_index",
        "welfare_support_deficit_index",
        "inclusion_failure_index",
        "gendered_school_disadvantage_index",
    }
    initial = [
        item for item in TERTIARY_INDICATORS if item.code in initial_codes
    ]
    connection.execute(
        f"""
        CREATE OR REPLACE TEMP VIEW school_domains AS
        SELECT *,
               {", ".join(
                   f"({item.expression}) AS {sql_identifier(item.code)}"
                   for item in initial
               )}
        FROM school_secondary
        """
    )

    middle_codes = {
        "educational_resource_deficit_index",
        "institutional_need_index",
        "overall_multidimensional_deprivation_index",
    }
    middle = [
        item for item in TERTIARY_INDICATORS if item.code in middle_codes
    ]
    connection.execute(
        f"""
        CREATE OR REPLACE TEMP VIEW school_tertiary_middle AS
        SELECT *,
               {", ".join(
                   f"({item.expression}) AS {sql_identifier(item.code)}"
                   for item in middle
               )}
        FROM school_domains
        """
    )

    connection.execute(
        """
        CREATE OR REPLACE TEMP VIEW school_vulnerability_ranks AS
        SELECT *,
            CASE WHEN bpl_share IS NOT NULL
                THEN PERCENT_RANK() OVER (PARTITION BY state ORDER BY bpl_share)
            END AS bpl_percentile,
            CASE WHEN ews_share IS NOT NULL
                THEN PERCENT_RANK() OVER (PARTITION BY state ORDER BY ews_share)
            END AS ews_percentile,
            CASE WHEN repeater_share IS NOT NULL
                THEN PERCENT_RANK() OVER (PARTITION BY state ORDER BY repeater_share)
            END AS repeater_percentile,
            CASE WHEN cwsn_share IS NOT NULL
                THEN PERCENT_RANK() OVER (PARTITION BY state ORDER BY cwsn_share)
            END AS cwsn_percentile
        FROM school_tertiary_middle
        """
    )

    remaining_codes = {
        "institutional_neglect_index",
        "vulnerability_context_index",
    }
    remaining = [
        item for item in TERTIARY_INDICATORS if item.code in remaining_codes
    ]
    connection.execute(
        f"""
        CREATE OR REPLACE TEMP VIEW school_tertiary_pre_final AS
        SELECT *,
               {", ".join(
                   f"({item.expression}) AS {sql_identifier(item.code)}"
                   for item in remaining
               )}
        FROM school_vulnerability_ranks
        """
    )

    compound = next(
        item
        for item in TERTIARY_INDICATORS
        if item.code == "compound_vulnerability_deprivation_index"
    )
    connection.execute(
        f"""
        CREATE OR REPLACE TEMP VIEW school_tertiary_final AS
        SELECT *,
               ({compound.expression}) AS {sql_identifier(compound.code)}
        FROM school_tertiary_pre_final
        """
    )

    selected_columns = [
        "pseudocode",
        "state",
        "district",
        "block",
        "rural_urban",
        "school_category",
        "school_type",
        "managment",
        "lowclass",
        "highclass",
        "minority_school",
        "shift_school",
        "resi_school",
        "total_students",
        "total_boys",
        "total_girls",
    ]
    for code, _ in GROUPS:
        prefix = code.lower()
        selected_columns.extend(
            [
                f"{prefix}_students",
                f"{prefix}_boys",
                f"{prefix}_girls",
                f"{prefix}_share",
            ]
        )
    selected_columns.extend(item.code for item in ALL_INDICATORS)
    selected = ", ".join(
        sql_identifier(column) for column in selected_columns
    )

    connection.execute(
        f"""
        CREATE OR REPLACE TEMP VIEW school_indicator_base AS
        SELECT {selected}
        FROM school_tertiary_final
        """
    )


def export_school_indicator_direct(
    connection: duckdb.DuckDBPyConnection,
    output_path: str,
) -> None:
    """Stream the final projected relation directly to compressed Parquet."""

    connection.execute(
        f"""
        COPY (
            SELECT * FROM school_indicator_base
        ) TO {sql_string(output_path)}
        (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 50000)
        """
    )
