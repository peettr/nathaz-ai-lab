#!/usr/bin/env python3
"""Format already-computed CRC v1.2 JSON into per-height score tables; no solver."""
import csv, json
from pathlib import Path
HERE=Path(__file__).resolve().parent
v=json.loads((HERE/'metrics_v12.json').read_text())
assert v['schema']=='L22_6_T03_v1_2'
with (HERE/'B0_B0prime_noise_v12.csv').open('x',newline='') as f:
 w=csv.writer(f); w.writerow(['source','z_m','metric','B0prime_minus_B0_abs','B1_vs_B0_abs','REF_vs_B0_abs','definition'])
 for z in v['B0']['heights']:
  for group,keys,unit in [('direction_abs_error_deg',['direction_abs_error_deg'],'degree'),('R_diagonal_relative_delta',['xx','yy','zz'],'fraction'),('rho_offdiagonal_abs_delta',['xy','xz','yz'],'dimensionless')]:
   for key in keys:
    def get(tag):
     entry=v[tag][z]
     val=entry[group] if group=='direction_abs_error_deg' else entry[group][key]
     return abs(val) if val is not None else ''
    w.writerow(['E7 TInF 8737a0d5; CRC jobs 1600620/1600622/1600623/1600630',z,key if group!='direction_abs_error_deg' else 'direction',get('noise_floor_B0prime_vs_B0'),get('B1_vs_B0'),get('candidate_vs_B0'),unit])
print(HERE/'B0_B0prime_noise_v12.csv')
