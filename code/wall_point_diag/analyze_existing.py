"""Read-only diagnostics for the four Case E wall points; stdlib only."""
import json
from pathlib import Path
ROOT=Path('./')
M=ROOT/'24_Urban_Wind_LBM/06_Logs/wp1b_ibm/phaseC3_caseE_gate2/m1_city'
B=ROOT/'24_Urban_Wind_LBM/06_Logs/wp1_nearwall/city_stab'
G=ROOT/'22_Lab/06_Logs/luw/CaseE_geometry_r11v2.json'
ids=(50,51,52,54)
geom={r['id']:r for r in json.loads(G.read_text())['rows']}
print('id,wall_m,gap_m,obs,base_S,base_Sstar,base_k,H1_S,H1_Sstar,H1_k,H2_S,H2_Sstar,H2_k')
sets=[json.loads((B/'stage6noT_offset_samples_a_r10.json').read_text()),json.loads((M/'H1_offset_samples_a_r10.json').read_text()),json.loads((M/'H2_offset_samples_a_r10.json').read_text())]
rows=[{r['id']:r for r in d['rows']} for d in sets]
for i in ids:
 vals=[]
 for table in rows:
  s=table[i]['sample']['plus_dx']; vals.extend([s['sim_ratio'],s['exp_ratio'],s['tke_m2s2']])
 print(i,geom[i]['stl_wall_m'],geom[i]['stl_crosswind_gap_m'],rows[0][i]['after'],*vals,sep=',')
print('mean K wall',*[sum(t[i]['sample']['plus_dx']['tke_m2s2'] for i in ids)/len(ids) for t in rows])
