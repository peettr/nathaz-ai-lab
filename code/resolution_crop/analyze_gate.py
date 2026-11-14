"""Prespecified crop-consistency gate: physical point subset, wall, upwind and street."""
from pathlib import Path
import json,statistics,math
R=Path(__file__).resolve().parent
B=json.loads((R.parent/'inflow_ti/B2_offset_samples.json').read_text())
C=json.loads((R/'C1_offset_samples.json').read_text())
ids={r['id'] for r in C['rows']}; br=[r for r in B['rows'] if r['id'] in ids];cr=C['rows'];assert len(br)==len(cr) and set(r['id'] for r in br)==ids
wall={50,51,52,54};assert wall<=ids

def mae(rows,which):return statistics.mean(abs(r['sample'][which]['exp_ratio']-r['after']) for r in rows)
subset_b=mae(br,'plus_dx');subset_c=mae(cr,'plus_dx');wall_b=mae([r for r in br if r['id'] in wall],'plus_dx');wall_c=mae([r for r in cr if r['id'] in wall],'plus_dx')
def upwind(d,x):return next(r['fraction_input'] for r in d['upstream'] if r['x_local_m']==x and r['z_m']==2.)
up={str(x):{'B2':upwind(B,x),'C1':upwind(C,x),'relative_difference':abs(upwind(B,x)-upwind(C,x))/abs(upwind(B,x))} for x in (25.,42.)}
def segments(d):
 line=d['street50'];out=[];start=None
 for j,v in enumerate(line):
  neg=v['ux']<0 and v['fluid_corners']==8
  if neg and start is None:start=v['x']
  if not neg and start is not None:out.append([start,line[j-1]['x']]);start=None
 if start is not None:out.append([start,line[-1]['x']])
 return out
seg_b=segments(B);seg_c=segments(C)
# Same x=205..237m, particularly 50 at x~205 and long segment x=226..237.
sign_b={v['x']: (v['ux']<0 and v['fluid_corners']==8) for v in B['street50']};sign_c={v['x']: (v['ux']<0 and v['fluid_corners']==8) for v in C['street50']}
sign_agree=all(sign_b[x]==sign_c[x] for x in range(205,238))
gates={'subset_mae_delta_le_0p010':abs(subset_c-subset_b)<=.010,'wall_mae_delta_le_0p020':abs(wall_c-wall_b)<=.020,'upwind_relative_both_le_0p05':all(v['relative_difference']<=.05 for v in up.values()),'street_reversal_same_sign':sign_agree}
out={'C1_point_count':len(ids),'point_ids':sorted(ids),'B2_subset_mae':subset_b,'C1_subset_mae':subset_c,'B2_wall_mae':wall_b,'C1_wall_mae':wall_c,'upwind':up,'street50_segments_B2':seg_b,'street50_segments_C1':seg_c,'street50_sign_disagree_x':[x for x in range(205,238) if sign_b[x]!=sign_c[x]],'gates':gates,'passed':all(gates.values()),'origin':C['origin'],'dimensions':C['dimensions']}
(R/'C1_gate.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
