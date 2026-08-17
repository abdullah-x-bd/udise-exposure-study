from __future__ import annotations

import csv
import math
import os
import re
import runpy
import tempfile
from pathlib import Path

import duckdb
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

C = runpy.run_path(
    "studies/muslim_government_school_equity/common.py",
    run_name="muslim_density_common",
)

extract_archive = C["extract_archive"]
csv_source = C["csv_source"]
source_columns = C["source_columns"]
enrolment_filters = C["enrolment_filters"]
class_sum = C["class_sum"]
first_str = C["first_str"]
first_num = C["first_num"]
ident = C["ident"]
qid = C["qid"]
lit = C["lit"]
MAIN_GOV_CODES = set(C["MAIN_GOV_CODES"])


def safe_slug(value: str) -> str:
    x = re.sub(r"[^A-Za-z0-9]+", "_", str(value).strip()).strip("_")
    return x[:100] or "unknown_state"


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def build_school_frame(year: str) -> tuple[pd.DataFrame, dict]:
    repo = os.environ["HF_DATASET_REPO"]
    token = os.environ["HF_TOKEN"]
    con = duckdb.connect()
    with tempfile.TemporaryDirectory(prefix=f"muslim_density_{year}_") as td:
        root = Path(td)
        e_src = csv_source(extract_archive(repo, token, year, "enrolment_1", root))
        p_src = csv_source(extract_archive(repo, token, year, "profile_1", root))
        ec = source_columns(con, e_src)
        pc = source_columns(con, p_src)
        eid = ident(ec)
        pid = ident(pc)
        filters, early_labels = enrolment_filters(con, e_src, ec)
        total_expr = class_sum(ec, 1, 12)
        social = ("general", "sc", "st", "obc")
        social_filter = " OR ".join(f"({filters[x]})" for x in social)
        muslim_filter = filters["muslim"]

        con.execute(
            f"""
            CREATE TEMP TABLE enr AS
            SELECT
                CAST({qid(eid)} AS VARCHAR) AS pseudocode,
                SUM(CASE WHEN {social_filter} THEN ({total_expr}) ELSE 0 END) AS total_enrolment,
                SUM(CASE WHEN {muslim_filter} THEN ({total_expr}) ELSE 0 END) AS muslim_enrolment
            FROM {e_src}
            GROUP BY 1
            """
        )

        state_expr = first_str(pc, ("state_name", "statename", "state", "state_id", "state_code", "state_cd"), "p")
        district_expr = first_str(pc, ("district_name", "district", "district_id", "district_code", "district_cd"), "p")
        management_expr = first_num(pc, ("managment", "management"), "p")
        if state_expr == "NULL":
            raise RuntimeError(f"{year}: no state field in profile_1")

        df = con.execute(
            f"""
            SELECT
                e.pseudocode,
                {state_expr} AS state,
                {district_expr} AS district,
                {management_expr} AS management,
                e.total_enrolment,
                e.muslim_enrolment
            FROM enr e
            INNER JOIN {p_src} p
              ON e.pseudocode = CAST(p.{qid(pid)} AS VARCHAR)
            WHERE e.total_enrolment > 0
            """
        ).df()
        con.close()

    for col in ("total_enrolment", "muslim_enrolment", "management"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df[df.total_enrolment > 0].copy()
    df["muslim_share"] = (df.muslim_enrolment / df.total_enrolment).clip(0, 1)
    df["muslim_share_pct"] = 100.0 * df.muslim_share
    # One percentage-point bins. x=1 means [1,2), while 100 means exactly 100 percent.
    df["share_bin_pct"] = np.minimum(np.floor(df.muslim_share_pct + 1e-12), 100).astype(int)
    df["state"] = df.state.astype(str).str.strip()
    df = df[df.state.notna() & ~df.state.str.lower().isin({"", "nan", "none"})].copy()
    df["is_government"] = df.management.isin(MAIN_GOV_CODES)

    meta = {
        "academic_year": year,
        "n_schools": int(len(df)),
        "n_government_schools": int(df.is_government.sum()),
        "early_religion_labels": early_labels.get("muslim", []),
    }
    return df, meta


def count_curve(z: pd.DataFrame) -> pd.DataFrame:
    g = z.groupby("share_bin_pct", observed=True).size().reindex(range(101), fill_value=0)
    out = g.rename("school_count").reset_index()
    out["state_school_percent"] = 100.0 * out.school_count / max(int(out.school_count.sum()), 1)
    return out


def summary_row(z: pd.DataFrame, year: str, state: str, sample: str) -> dict:
    share = pd.to_numeric(z.muslim_share, errors="coerce")
    positive = share[share > 0]
    total = len(z)
    muslim_students = float(pd.to_numeric(z.muslim_enrolment, errors="coerce").fillna(0).sum())
    all_students = float(pd.to_numeric(z.total_enrolment, errors="coerce").fillna(0).sum())

    def q(series: pd.Series, p: float) -> float:
        return float(series.quantile(p)) if len(series) else float("nan")

    row = {
        "academic_year": year,
        "state": state,
        "sample": sample,
        "schools": int(total),
        "muslim_students": int(round(muslim_students)),
        "total_students": int(round(all_students)),
        "student_weighted_muslim_share_pct": 100.0 * muslim_students / all_students if all_students > 0 else float("nan"),
        "schools_zero_muslim": int((share == 0).sum()),
        "schools_positive_muslim": int((share > 0).sum()),
        "schools_zero_muslim_pct": 100.0 * float((share == 0).mean()) if total else float("nan"),
        "median_share_positive_pct": 100.0 * q(positive, 0.50),
        "p75_share_pct": 100.0 * q(share, 0.75),
        "p90_share_pct": 100.0 * q(share, 0.90),
        "p95_share_pct": 100.0 * q(share, 0.95),
    }
    for threshold in (10, 25, 50, 75, 90):
        n = int((share >= threshold / 100).sum())
        row[f"schools_ge_{threshold}pct"] = n
        row[f"schools_ge_{threshold}pct_share"] = 100.0 * n / total if total else float("nan")
    return row


def draw_state(z: pd.DataFrame, year: str, state: str, sample: str, path: Path) -> None:
    g = count_curve(z)
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(g.share_bin_pct, g.school_count, linewidth=1.15)
    ax.set_xlim(0, 100)
    ax.set_xlabel("Muslim share of school enrolment, 1 percentage-point bins")
    ax.set_ylabel("Number of schools")
    ax.set_title(f"{state} | {year} | {sample}")
    ax.axvline(50, linestyle="--", linewidth=0.8)
    ax.axvline(75, linestyle=":", linewidth=0.8)
    fig.tight_layout()
    fig.savefig(path, dpi=170)
    plt.close(fig)


def draw_contact_sheet(df: pd.DataFrame, year: str, sample: str, path: Path) -> None:
    states = sorted(df.state.unique().tolist())
    ncols = 4
    nrows = math.ceil(len(states) / ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(18, max(5, 2.8 * nrows)), squeeze=False)
    for ax, state in zip(axes.ravel(), states):
        z = df[df.state == state]
        g = count_curve(z)
        ax.plot(g.share_bin_pct, g.state_school_percent, linewidth=0.85)
        ax.axvline(50, linestyle="--", linewidth=0.55)
        ax.set_xlim(0, 100)
        ax.set_title(str(state), fontsize=9)
        ax.tick_params(labelsize=7)
    for ax in axes.ravel()[len(states):]:
        ax.axis("off")
    fig.suptitle(
        f"{year}: distribution of schools by Muslim enrolment share | {sample}\n"
        "Each panel is normalized within State/UT so shapes are comparable",
        fontsize=13,
    )
    fig.supxlabel("Muslim share of school enrolment, 1 percentage-point bins")
    fig.supylabel("Percent of schools in State/UT")
    fig.tight_layout(rect=(0.02, 0.02, 1, 0.96))
    fig.savefig(path, dpi=160)
    plt.close(fig)


def main() -> None:
    year = os.environ["YEAR"]
    out = Path(f"studies/muslim_educational_disenfranchisement/outputs/preliminary_density/{year}")
    out.mkdir(parents=True, exist_ok=True)
    df, meta = build_school_frame(year)

    count_rows: list[dict] = []
    summary_rows: list[dict] = []
    graph_rows: list[dict] = []

    samples = {
        "all_schools": df,
        "state_local_government": df[df.is_government].copy(),
    }
    for sample, sdf in samples.items():
        graph_dir = out / sample / "states"
        graph_dir.mkdir(parents=True, exist_ok=True)
        states = sorted(sdf.state.unique().tolist())
        for state in states:
            z = sdf[sdf.state == state].copy()
            slug = safe_slug(state)
            filename = f"{slug}.png"
            draw_state(z, year, state, sample, graph_dir / filename)
            summary_rows.append(summary_row(z, year, state, sample))
            graph_rows.append({
                "academic_year": year,
                "state": state,
                "sample": sample,
                "graph_file": f"{sample}/states/{filename}",
            })
            g = count_curve(z)
            for row in g.itertuples(index=False):
                count_rows.append({
                    "academic_year": year,
                    "state": state,
                    "sample": sample,
                    "share_bin_pct": int(row.share_bin_pct),
                    "school_count": int(row.school_count),
                    "state_school_percent": float(row.state_school_percent),
                })
        draw_contact_sheet(sdf, year, sample, out / f"CONTACT_SHEET_{sample}_{year}.png")

    write_csv(out / "state_muslim_share_density_1pp.csv", count_rows)
    write_csv(out / "state_distribution_summary.csv", summary_rows)
    write_csv(out / "state_graph_index.csv", graph_rows)

    lines = [
        f"# Preliminary Muslim enrolment-share density | {year}",
        "",
        f"Schools with reconciled Classes I-XII enrolment: {meta['n_schools']:,}",
        f"State/UT/local-government schools: {meta['n_government_schools']:,}",
        "",
        "The x-axis uses one percentage-point bins from 0 through 100. Bin 1 means Muslim share in [1%, 2%); bin 100 is exactly 100%.",
        "",
        "Two universes are reported: all schools, and State/UT/local-government schools using management codes 1, 2, 3, 6, 89 and 90.",
        "",
        "The individual State/UT graphs use raw school counts. Contact sheets normalize the y-axis within State/UT only to make distribution shapes visually comparable.",
        "",
        "No causal interpretation is attached to these density plots. They are the descriptive map used to choose subsequent within-state and longitudinal identification strategies.",
    ]
    (out / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(meta, flush=True)
    print(f"Wrote {len(count_rows)} density rows and {len(summary_rows)} state summaries", flush=True)


if __name__ == "__main__":
    main()
