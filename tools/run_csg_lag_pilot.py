from __future__ import annotations

import os
from pathlib import Path

SOURCE=Path('tools/csg_first_stage_pilot.py')

def main():
    year=os.environ['ENROL_YEAR']
    code=SOURCE.read_text(encoding='utf-8')
    code=code.replace('raw/2022-23/enrolment_1.zip',f'raw/{year}/enrolment_1.zip')
    code=code.replace('outputs/csg_first_stage_pilot',f'outputs/csg_lag_pilot/{year}')
    # 2018-21 use item_desc rather than item_group/item_id and need the full harmonizer,
    # so this fast timing check is deliberately limited to vintages with the stable coding.
    if year < '2022-23':
        # For 2021-22, use the study panel builder's early social-row detection would be required.
        # Fail explicitly rather than silently constructing the wrong enrolment total.
        raise RuntimeError('Fast lag pilot supports 2022-23 onward only; older vintages are tested in the full harmonized panel.')
    exec(compile(code,str(SOURCE),'exec'),{'__name__':'__main__','__file__':str(SOURCE)})

if __name__=='__main__':main()
