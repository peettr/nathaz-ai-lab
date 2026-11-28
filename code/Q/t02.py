import sys, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
CASES=('small','medium','large','X')
import sl_calibration as sl
frozen=json.loads((ROOT/'sl_results.json').read_text())['cases']
rows={c:sl.solve('Q',float(frozen[c]['F_c']),float(frozen[c]['delta']),.9783145940392678,7276.0250356865) for c in CASES}
print(json.dumps({c:{'sigma_q':rows[c]['sigma_q'],'sigma_stroke':rows[c]['sigma_stroke']} for c in CASES}))
