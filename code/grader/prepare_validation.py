#!/usr/bin/env python3
"""Stage private A/C/Q validation wrappers; no scientific computation locally."""
import json
import shutil
from pathlib import Path

SRC=Path(__file__).resolve().parents[1]
OUT=Path(__file__).resolve().parent/'validation_package'
if OUT.exists():
    raise SystemExit('validation package exists: do not overwrite')
OUT.mkdir()
for file in ('sl_calibration.py','sl_independent_C.py','tmdi_powerlaw_sl.py','filter_params.json','sl_results.json'):
    shutil.copy2(SRC/file, OUT/file)
for method in ('A','C','Q'):
    folder=OUT/method
    folder.mkdir()
    if method == 'C':
        body="""import sl_independent_C as sl
frozen=json.loads((ROOT/'sl_results.json').read_text())['cases']
pf=json.loads((ROOT/'filter_params.json').read_text())
rows={c:sl.fixed_point(sl.NU0,float(frozen[c]['F_c']),float(frozen[c]['delta']),pf) for c in CASES}
"""
    else:
        body=f"""import sl_calibration as sl
frozen=json.loads((ROOT/'sl_results.json').read_text())['cases']
rows={{c:sl.solve('{method}',float(frozen[c]['F_c']),float(frozen[c]['delta']),.9783145940392678,7276.0250356865) for c in CASES}}
"""
    (folder/'t02.py').write_text("import sys, json\nfrom pathlib import Path\nROOT=Path(__file__).resolve().parents[1]\nsys.path.insert(0,str(ROOT))\nCASES=('small','medium','large','X')\n"+body+"print(json.dumps({c:{'sigma_q':rows[c]['sigma_q'],'sigma_stroke':rows[c]['sigma_stroke']} for c in CASES}))\n")
folder=OUT/'template'
folder.mkdir()
shutil.copy2(SRC/'tmdi_powerlaw_sl.py',folder/'t02.py')
print(json.dumps({'validation_dirs':[str(OUT/k) for k in ('A','C','Q','template')]}))
