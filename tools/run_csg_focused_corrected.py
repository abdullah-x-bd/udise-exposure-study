from __future__ import annotations

from pathlib import Path


SOURCE = Path("tools/csg_focused_2022_2024.py")


def main() -> None:
    code = SOURCE.read_text(encoding="utf-8")

    old_base = "CREATE TEMP TABLE base AS SELECT CAST(p.{pid} AS VARCHAR) pseudocode,{nref(pc,'managment','p')} management,{','.join(expr+' b_'+name for name,expr in base_out.items())} FROM {p1} p LEFT JOIN {fac} f ON CAST(p.{pid} AS VARCHAR)=CAST(f.{fid} AS VARCHAR)"
    new_base = "CREATE TEMP TABLE base AS SELECT CAST(p.{pid} AS VARCHAR) pseudocode,{nref(pc,'managment','p')} management,CAST({ref(pc,'state','p')} AS VARCHAR) state_key,{','.join(expr+' b_'+name for name,expr in base_out.items())} FROM {p1} p LEFT JOIN {fac} f ON CAST(p.{pid} AS VARCHAR)=CAST(f.{fid} AS VARCHAR)"
    if old_base not in code:
        raise RuntimeError("Could not locate baseline table construction")
    code = code.replace(old_base, new_base, 1)

    old_sample = "CREATE TEMP TABLE sample AS SELECT e.pseudocode,e.enrol,{num('m.'+qid(state))} state,{num('m.'+qid(mgmt))} management_current,b.management management_base"
    new_sample = "CREATE TEMP TABLE sample AS SELECT e.pseudocode,e.enrol,DENSE_RANK() OVER (ORDER BY b.state_key) state,{num('m.'+qid(mgmt))} management_current,b.management management_base"
    if old_sample not in code:
        raise RuntimeError("Could not locate focused sample construction")
    code = code.replace(old_sample, new_sample, 1)

    # Keep every inferential correction in a separate output path so invalid prior runs remain auditable.
    code = code.replace("outputs/csg_focused_2022_2024", "outputs/csg_focused_2022_2024_corrected_v2")
    compiled = compile(code, str(SOURCE), "exec")
    ns = {"__name__": "__main__", "__file__": str(SOURCE)}
    exec(compiled, ns, ns)


if __name__ == "__main__":
    main()
