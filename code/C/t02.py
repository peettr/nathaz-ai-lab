import sys, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
CASES=('small','medium','large','X')
import sl_independent_C as sl
frozen=json.loads((ROOT/'sl_results.json').read_text())['cases']
pf=json.loads((ROOT/'filter_params.json').read_text())
rows={c:sl.fixed_point(sl.NU0,float(frozen[c]['F_c']),float(frozen[c]['delta']),pf) for c in CASES}
print(json.dumps({c:{'sigma_q':rows[c]['sigma_q'],'sigma_stroke':rows[c]['sigma_stroke']} for c in CASES}))
