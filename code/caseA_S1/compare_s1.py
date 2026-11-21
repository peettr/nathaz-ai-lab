#!/usr/bin/env python3
"""Read S1 compact result, compare only valid same-geometry legacy metrics."""
import json,math
from pathlib import Path
R=Path(__file__).parent; L=R.parent
s=json.loads((R/'s1_results.json').read_text())
old2=json.loads((L/'caseA_r9_2m_tacc_v2/metrics_caseA_r9_2m.json').read_text())
old4=json.loads((L/'caseA_r216_0b/metrics_caseA_r216_0b.json').read_text())['r9_dx4']
old10=json.loads((L/'caseA_dx10_v2/post/out_3710432/metrics_r9_dx10_v2.json').read_text())
lookup={'4m':('z8','z4_actual','z8'),'40m':('z80','z40_actual','z80'),'vertical':('vertical','vertical_actual','vertical')}
metrics=('FAC2','q_abs025','q_rel025','r','NRMSE_range','NRMSE_mean','TKE_FAC2','TKE_r','mean_ratio')
out={'comparison_rule':'new minus archived; old rows are diagnostic only, not wall-matched. 2m plus_xyz is round-nine/C38.2; plus_xy shown separately. Old 10m is repaired-v2 only; never original missing-ground 0b. S1 excludes solid and reports clamp.','rows':[]}
for label,(new_key,k2,k4) in lookup.items():
 for g in ('dx2','dx4','dx10'):
  group=s['grids'][g]['groups'][new_key]; new=group['metrics_excluding_mixed']
  if g=='dx2':olds={'round9_C38_2_plus_xyz':old2['main'][k2]['plus_xyz'],'archived_plus_xy':old2['main'][k2]['plus_xy']}
  elif g=='dx4':olds={'archived_0b_selected':old4['primary'][k4]['selected']}
  else:olds={'repaired_v2_pre_S1':old10['primary'][k4]['selected']}
  row={'plane':label,'grid':g,'new_S1':{k:new[k] if new else None for k in metrics},'n':group['total'],'clamped':group['clamped'],'mixed_solid':group['mixed_solid'],'unclamped_unmixed':group['unclamped_unmixed'],'verdict':s['comparison'][label]['grid_verdict'][g],'archived':{}}
  for name,old in olds.items():
   row['archived'][name]={'metrics':{k:old.get(k) for k in metrics},'delta_new_minus_old':{k:(new[k]-old[k] if new and new[k] is not None and old.get(k) is not None else None) for k in metrics}}
  out['rows'].append(row)
(R/'s1_comparison.json').write_text(json.dumps(out,indent=2,ensure_ascii=False,allow_nan=False))
for r in out['rows']:
 print(r['grid'],r['plane'],r['n'],r['clamped'],r['mixed_solid'],r['verdict'],'FAC2',r['new_S1']['FAC2'],[(k,v['delta_new_minus_old']['FAC2']) for k,v in r['archived'].items()])
