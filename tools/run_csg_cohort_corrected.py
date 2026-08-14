from __future__ import annotations

from pathlib import Path

SOURCE = Path("studies/composite_school_grant/scripts/06_cohort_rd.py")


def main() -> None:
    code = SOURCE.read_text(encoding="utf-8")
    old_state = "{nref(apc,'state','p')} state,"
    new_state = "CAST({ref(apc,'state','p')} AS VARCHAR) state_key,"
    if old_state not in code:
        raise RuntimeError("Could not patch assignment-year state field")
    code = code.replace(old_state, new_state, 1)
    old_sample = "SELECT e.pseudocode,e.enrol,b.state,b.district,b.management management_base,"
    new_sample = "SELECT e.pseudocode,e.enrol,DENSE_RANK() OVER (ORDER BY b.state_key) state,b.district,b.management management_base,"
    if old_sample not in code:
        raise RuntimeError("Could not patch cohort sample state encoding")
    code = code.replace(old_sample, new_sample, 1)
    code = code.replace("outputs/cohorts/", "outputs/cohorts_corrected/")
    exec(compile(code, str(SOURCE), "exec"), {"__name__": "__main__", "__file__": str(SOURCE)})


if __name__ == "__main__":
    main()
