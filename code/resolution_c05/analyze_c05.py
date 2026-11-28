"""Analyze paired cropped 1 m / 0.5 m wind-point diagnostics."""
from pathlib import Path
import json,math,statistics
R=Path(__file__).resolve().parent
P=R.parent
B=json.loads((P/'inflow_ti/B2_offset_samples.json').read_text())
C=json.loads((P/'resolution_crop_v2/C1v2_offset_samples.json').read_text())
F=json.loads((R/'C05_offset_samples_a_r10.json').read_text())
ids=(50,51,52,54); cr={r['id']:r for r in C['rows']}; fr={r['id']:r for r in F['rows']};br={r['id']:r for r in B['rows']}
def per(row):
 q=row['sample']['plus_dx'];v=q['mean_velocity_mps'];return dict(Sstar=q['exp_ratio'],k=q['tke_m2s2'],uv=v,azimuth_deg=(math.degrees(math.atan2(v[1],v[0]))+360)%360,fluid_corners=q['fluid_corners'],observed=row['after'])
wall={str(i):{'B2':per(br[i]),'C1':per(cr[i]),'C05':per(fr[i])} for i in ids}
for a in wall.values():
 a['C05_minus_C1_Sstar']=a['C05']['Sstar']-a['C1']['Sstar'];a['C05_minus_C1_k']=a['C05']['k']-a['C1']['k']
def stats(rr):
 return {'MAE':statistics.mean(abs(x['Sstar']-x['observed']) for x in rr),'mean_ratio':statistics.mean(x['Sstar'] for x in rr)/statistics.mean(x['observed'] for x in rr)}
sub={key:stats([per(q[i]) for i in ids]) for key,q in [('B2',br),('C1',cr),('C05',fr)]}
common=sorted(set(cr)&set(fr));op={23,25,37,17}&set(common)
subsets={key:stats([per(q[i]) for i in common]) for key,q in [('C1',cr),('C05',fr)]}
open_stats={key:stats([per(q[i]) for i in sorted(op)]) for key,q in [('C1',cr),('C05',fr)]} if op else {}
def segments(d):
 a=d['street50'];out=[];start=None
 for j,v in enumerate(a):
  neg=v['ux']<0 and v['fluid_corners']==8
  if neg and start is None:start=v['x']
  if not neg and start is not None:out.append([start,a[j-1]['x']]);start=None
 if start is not None:out.append([start,a[-1]['x']])
 return out
streets={k:segments(v) for k,v in [('B2',B),('C1',C),('C05',F)]}
profiles={str(z):{k:next(x['k_m2s2'] for x in v['profiles'] if x['x']==5 and x['z_agl']==z) for k,v in [('C1',C),('C05',F)]} for z in (1,2,5,10,15,20,30)}
out=dict(wall=wall,wall_stats=sub,subset_stats=subsets,common_n=len(common),open_ids=sorted(op),open_stats=open_stats,street50=streets,k_x5=profiles,mask_fit=F['mask_fit'],C05_dimensions=F['dimensions'],C05_origin=F['origin'])
(R/'C05_analysis.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:out[k] for k in ('wall','wall_stats','subset_stats','open_stats','street50','k_x5')},indent=2))
