#!/usr/bin/env python3
"""File-only CRC staging of independent debug roots; refuses existing destinations."""
import shutil
from pathlib import Path
from prepare_case_v3 import main as _unused
import sys
BASE=Path('/groups/kareem/[用户]/L22_6')
SOURCE=BASE/'L22_6_T03_v12_B0_20261021_02'
PRIVATE=BASE/'L22_6_T03_private_CI_v3'
ROOT1=BASE/'L22_6_v3S0_DBG_01_20261127'
PREP=ROOT1/'prepare_case_v3.py'
JOBS=[('02',PRIVATE/'CIminus_fixed_01'),('03',BASE/'L22_6_T03_private_ref_v2/src')]
for index,src in JOBS:
    root=BASE/f'L22_6_v3S0_DBG_{index}_20261127'
    if root.exists(): raise FileExistsError(root)
    root.mkdir(mode=0o700)
    shutil.copytree(src,root/'src',ignore=shutil.ignore_patterns('linux64*','lnInclude','*.o','*.so','.git'))
    import subprocess
    subprocess.run([sys.executable,str(PREP),str(SOURCE),str(root/'case'),'--bc','Veer'],check=True)
    control=root/'case/system/controlDict'
    text=control.read_text().replace('endTime 120;', 'endTime 0.05;').replace('endTime\t120;', 'endTime 0.05;')
    if 'endTime 0.05;' not in text: raise ValueError(f'debug endTime not set {control}')
    control.write_text(text)
    template=(ROOT1/'run_debug01.sh').read_text()
    template=template.replace('L22_6_v3S0_DBG01',f'L22_6_v3S0_DBG{index}').replace(str(ROOT1),str(root))
    script=root/'run.sh'; script.write_text(template); script.chmod(0o700)
    shutil.copy2(ROOT1/'EXPERIMENT_CARD.md',root/'EXPERIMENT_CARD.md')
    print(root,src,flush=True)
