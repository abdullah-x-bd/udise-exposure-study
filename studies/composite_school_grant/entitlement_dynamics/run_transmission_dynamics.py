from __future__ import annotations

import math
import os
import runpy
import shutil
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

T = runpy.run_path(
    "studies/composite_school_grant/timing_core/run_timing_core.py",
    run_name="csg_dynamic_transmission_lib",
)
YEARS = T["YEARS"]
build = T["build"]
lit = T["lit"]

BROAD = {1, 2, 3, 6, 89, 90}
OUT = Path("studies/composite_school_grant/outputs/entitlement_dynamics/transmission")
SPECS = [
    {"label":"30_31","end":30,"upper":25000,"bw":20,"state_bw":25},
    {"label":"100_101","end":100,"upper":50000,"bw":35,"state_bw":45},
    {"label":"250_251","end":250,"upper":75000,"bw":40,"state_bw":55},
    {"label":"1000_1001","end":1000,"upper":100000,"bw":100,"state_bw":150},
]


def save(df: pd.DataFrame, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / name, index=False)


def local_linear(y: np.ndarray, x: np.ndarray, cutoff: float, bw: float, min_n: int, min_side: int):
    m = np.isfinite(y) & np.isfinite(x) & (np.abs(x-cutoff) <= bw)
    y, x = y[m], x[m]
    left = int((x < cutoff).sum())
    right = int((x >= cutoff).sum())
    if len(y) < min_n or min(left, right) < min_side:
        return None
    z = x-cutoff
    t = (x >= cutoff).astype(float)
    w = np.maximum(0.0, 1.0 - np.abs(z)/bw)
    keep = w > 0
    y, z, t, w = y[keep], z[keep], t[keep], w[keep]
    X = np.column_stack([np.ones(len(y)), t, z, t*z])
    A = X.T @ (w[:,None]*X)
    try:
        B = np.linalg.inv(A)
    except np.linalg.LinAlgError:
        B = np.linalg.pinv(A)
    beta = B @ (X.T @ (w*y))
    resid = y - X@beta
    M = X.T @ (((w*resid)**2)[:,None]*X)
    V = B @ M @ B
    dof = max(1, len(y)-4)
    V *= len(y)/dof
    se = float(np.sqrt(max(V[1,1],0)))
    tau = float(beta[1])
    p = math.erfc(abs(tau/se)/math.sqrt(2)) if se > 0 else np.nan
    return {
        "tau":tau, "se":se, "p":p, "ci_low":tau-1.96*se, "ci_high":tau+1.96*se,
        "n":len(y), "n_left":left, "n_right":right, "bw":bw,
    }


def ivw(g: pd.DataFrame) -> dict:
    z = g[["tau","se"]].replace([np.inf,-np.inf],np.nan).dropna()
    z = z[z["se"]>0]
    if z.empty:
        return {"k":0,"tau":np.nan,"se":np.nan,"ci_low":np.nan,"ci_high":np.nan}
    w = 1.0/z["se"].to_numpy(float)**2
    t = float(np.sum(w*z["tau"].to_numpy(float))/np.sum(w))
    s = float(np.sqrt(1.0/np.sum(w)))
    return {"k":len(z),"tau":t,"se":s,"ci_low":t-1.96*s,"ci_high":t+1.96*s}


def latency_from_curve(g: pd.DataFrame) -> dict:
    if g.empty:
        return {"peak_lag":np.nan,"peak_pp":np.nan,"n50":np.nan,"n80":np.nan,"auc_pp":np.nan}
    q = g.sort_values("lag").dropna(subset=["tau"])
    if q.empty:
        return {"peak_lag":np.nan,"peak_pp":np.nan,"n50":np.nan,"n80":np.nan,"auc_pp":np.nan}
    peak_idx = q["tau"].idxmax()
    peak = float(q.loc[peak_idx,"tau"])
    peak_lag = int(q.loc[peak_idx,"lag"])
    if peak <= 0:
        n50 = n80 = np.nan
    else:
        c50 = q[q["tau"] >= 0.5*peak]
        c80 = q[q["tau"] >= 0.8*peak]
        n50 = int(c50["lag"].min()) if not c50.empty else np.nan
        n80 = int(c80["lag"].min()) if not c80.empty else np.nan
    auc = float(np.trapezoid(q["tau"].to_numpy(float), q["lag"].to_numpy(float))) if len(q)>=2 else np.nan
    return {"peak_lag":peak_lag,"peak_pp":100*peak,"n50":n50,"n80":n80,"auc_pp":100*auc}


def pairwise_corr(df: pd.DataFrame, metric: str, min_pairs: int = 8) -> pd.DataFrame:
    w = df.pivot_table(index="state", columns="threshold_label", values=metric, aggfunc="mean")
    cols = list(w.columns)
    rows = []
    for i,a in enumerate(cols):
        for b in cols[i+1:]:
            z = w[[a,b]].dropna()
            if len(z) < min_pairs:
                continue
            rows.append({
                "metric":metric,"threshold_a":a,"threshold_b":b,"n_states":len(z),
                "pearson":float(z[a].corr(z[b],method="pearson")),
                "spearman":float(z[a].corr(z[b],method="spearman")),
            })
    return pd.DataFrame(rows)


def main() -> None:
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("PRAGMA threads=4")
    con.execute("PRAGMA memory_limit='10GB'")
    work = OUT / "_work"
    work.mkdir(parents=True, exist_ok=True)
    panel = build(con, os.environ["HF_DATASET_REPO"], os.environ["HF_TOKEN"], work)
    yi = {y:i for i,y in enumerate(YEARS)}

    national, state_rows = [], []
    for spec in SPECS:
        cutoff = spec["end"] + 0.5
        for ay in YEARS:
            ia = yi[ay]
            for oy in YEARS:
                lag = yi[oy]-ia
                if lag < 0 or lag > 4:
                    continue
                bwq = spec["state_bw"]
                d = con.execute(f"""
                    SELECT a.enrol x, CAST(a.state AS VARCHAR) state, f.receipt
                    FROM read_parquet({lit(str(panel))}) a
                    LEFT JOIN read_parquet({lit(str(panel))}) f
                      ON a.pseudocode=f.pseudocode AND f.academic_year={lit(oy)}
                    WHERE a.academic_year={lit(ay)}
                      AND a.management IN ({",".join(map(str,sorted(BROAD)))})
                      AND a.enrol BETWEEN {spec["end"]-bwq} AND {spec["end"]+1+bwq}
                """).df()
                if d.empty:
                    continue
                rr = pd.to_numeric(d["receipt"], errors="coerce").to_numpy(float)
                x = pd.to_numeric(d["x"], errors="coerce").to_numpy(float)
                y = np.where(np.isfinite(rr),(rr>=spec["upper"]).astype(float),np.nan)
                r = local_linear(y,x,cutoff,spec["bw"],300,80)
                if r:
                    national.append({
                        "threshold_label":spec["label"],"assignment_year":ay,
                        "outcome_year":oy,"lag":lag,"outcome":"receipt_atleast_upper",**r
                    })
                d2 = d.assign(_y=y)
                for st,g in d2.groupby("state"):
                    yy = g["_y"].to_numpy(float)
                    xx = pd.to_numeric(g["x"],errors="coerce").to_numpy(float)
                    s = local_linear(yy,xx,cutoff,spec["state_bw"],120,30)
                    if s:
                        state_rows.append({
                            "threshold_label":spec["label"],"assignment_year":ay,
                            "outcome_year":oy,"lag":lag,"state":st,**s
                        })
                print("DYNAMIC",spec["label"],ay,oy,"lag",lag,flush=True)

    nat = pd.DataFrame(national)
    st = pd.DataFrame(state_rows)
    save(nat,"dynamic_local_linear_national.csv")
    save(st,"dynamic_local_linear_state.csv")

    pool_nat = []
    for (th,lag),g in nat.groupby(["threshold_label","lag"]):
        r = ivw(g)
        pool_nat.append({"threshold_label":th,"lag":lag,**r})
    pool_nat = pd.DataFrame(pool_nat)
    save(pool_nat,"dynamic_pooled_curve_national.csv")

    pool_state = []
    for (state,th,lag),g in st.groupby(["state","threshold_label","lag"]):
        r = ivw(g)
        if r["k"] >= 2:
            pool_state.append({"state":state,"threshold_label":th,"lag":lag,**r})
    pool_state = pd.DataFrame(pool_state)
    save(pool_state,"dynamic_pooled_curve_state.csv")

    nat_summary = []
    for th,g in pool_nat.groupby("threshold_label"):
        nat_summary.append({"threshold_label":th,**latency_from_curve(g)})
    nat_summary = pd.DataFrame(nat_summary)
    save(nat_summary,"transmission_latency_summary_national.csv")

    state_summary = []
    for (state,th),g in pool_state.groupby(["state","threshold_label"]):
        r = latency_from_curve(g)
        r.update({
            "state":state,"threshold_label":th,
            "cohort_lag_cells":int(g["k"].sum()),
            "t3_pp":100*float(g.loc[g["lag"]==3,"tau"].iloc[0]) if (g["lag"]==3).any() else np.nan,
            "t2_pp":100*float(g.loc[g["lag"]==2,"tau"].iloc[0]) if (g["lag"]==2).any() else np.nan,
            "t4_pp":100*float(g.loc[g["lag"]==4,"tau"].iloc[0]) if (g["lag"]==4).any() else np.nan,
        })
        state_summary.append(r)
    state_summary = pd.DataFrame(state_summary)
    save(state_summary,"transmission_latency_summary_state.csv")

    corr_parts = []
    for metric in ["peak_pp","t3_pp","n80","n50","auc_pp"]:
        q = pairwise_corr(state_summary,metric)
        if not q.empty:
            corr_parts.append(q)
    corrs = pd.concat(corr_parts,ignore_index=True) if corr_parts else pd.DataFrame()
    save(corrs,"cross_threshold_state_replication_transmission.csv")

    cohort_corr = []
    q3 = st[st["lag"]==3].copy()
    for th,g in q3.groupby("threshold_label"):
        w = g.pivot_table(index="state",columns="assignment_year",values="tau",aggfunc="mean")
        cols = list(w.columns)
        for i,a in enumerate(cols):
            for b in cols[i+1:]:
                z = w[[a,b]].dropna()
                if len(z)>=8:
                    cohort_corr.append({
                        "threshold_label":th,"cohort_a":a,"cohort_b":b,"n_states":len(z),
                        "pearson":float(z[a].corr(z[b])),
                        "spearman":float(z[a].corr(z[b],method="spearman")),
                    })
    save(pd.DataFrame(cohort_corr),"state_strength_cohort_stability.csv")

    if not pool_nat.empty:
        fig,ax=plt.subplots(figsize=(9,5))
        for th,g in pool_nat.groupby("threshold_label"):
            g=g.sort_values("lag")
            ax.plot(g["lag"],100*g["tau"],marker="o",label=th)
        ax.axhline(0,linewidth=.8)
        ax.set_xlabel("UDISE rounds after assignment enrolment")
        ax.set_ylabel("Pooled local-linear formula response, pp")
        ax.set_title("Dynamic recorded formula transmission")
        ax.legend()
        fig.tight_layout()
        fig.savefig(OUT/"figure_dynamic_transmission_national.png",dpi=180)
        plt.close(fig)

    s250 = state_summary[state_summary["threshold_label"]=="250_251"].dropna(subset=["n80","peak_pp"])
    if not s250.empty:
        fig,ax=plt.subplots(figsize=(10,7))
        ax.scatter(s250["n80"],s250["peak_pp"],s=30)
        for _,r in s250.iterrows():
            if r["peak_pp"]>=35 or r["n80"]>=3:
                ax.annotate(str(r["state"]),(r["n80"],r["peak_pp"]),fontsize=7,xytext=(3,3),textcoords="offset points")
        ax.set_xlabel("Transmission N80, UDISE rounds")
        ax.set_ylabel("Peak formula response, pp")
        ax.set_title("State transmission latency and strength at 250/251")
        fig.tight_layout()
        fig.savefig(OUT/"figure_state_transmission_250.png",dpi=180)
        plt.close(fig)

    lines=["# Dynamic causal-transmission diagnostic","",
           "These local-linear curves estimate the timing of the recorded formula discontinuity without conditioning on future enrolment.",
           "They are kept separate from the descriptive entitlement-spell analysis to avoid conditioning a causal RD on post-assignment survival.",
           "","## National transmission latency"]
    for _,r in nat_summary.sort_values("threshold_label").iterrows():
        lines.append(
            f"- {r.threshold_label}: peak {r.peak_pp:+.1f} pp at lag +{int(r.peak_lag)}; "
            f"N50={r.n50 if pd.notna(r.n50) else 'NA'}, N80={r.n80 if pd.notna(r.n80) else 'NA'}."
        )
    lines += ["","## Guardrails",
              "- State estimates are diagnostic local-linear estimates and require adequate support on both sides.",
              "- Publication-grade national rdrobust estimates from the four-threshold audit remain the primary causal first-stage estimates.",
              "- The 100/101 and 1000/1001 boundaries overlap other enrolment-linked rules, so the threshold response there is a formula fingerprint rather than a clean CSG-only outcome experiment.",
              "- The <=30 band retains the historical-validity caveat."]
    (OUT/"RESULTS.md").write_text("\n".join(lines),encoding="utf-8")
    print("\n".join(lines),flush=True)
    shutil.rmtree(work,ignore_errors=True)
    con.close()


if __name__=="__main__":
    main()
