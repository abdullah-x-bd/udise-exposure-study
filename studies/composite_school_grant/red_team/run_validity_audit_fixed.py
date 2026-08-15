from __future__ import annotations

from pathlib import Path

SOURCE = Path("studies/composite_school_grant/red_team/run_validity_audit.py")


def main() -> None:
    code = SOURCE.read_text(encoding="utf-8")
    code = code.replace("e.enrol BETWEEN 175 AND 325", "e.enrol BETWEEN 100 AND 400")
    code = code.replace("{ex} stable FROM base b JOIN", "{ex} AS stable_flag FROM base b JOIN")
    code = code.replace("),'stable')", "),'stable_flag')")
    if "e.enrol BETWEEN 175 AND 325" in code or "{ex} stable FROM base b JOIN" in code:
        raise RuntimeError("Expected red-team patches were not fully applied")
    ns = {"__name__": "__main__", "__file__": str(SOURCE)}
    exec(compile(code, str(SOURCE), "exec"), ns, ns)


if __name__ == "__main__":
    main()
