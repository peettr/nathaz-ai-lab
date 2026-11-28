"""At storm shutdown trigger, compare inflow direction with actual G1/G2L yaw."""
import json,numpy as np
from pathlib import Path
p=Path('/content/a3_d_yawfix_r2_full');r=p/'results';out={}
for case in ('I_near','III_kzm05','III_kzm00'):
 out[case]={}
 for group in ('G1','G2L'):
  vals={}
  for seed in (112,203,317,419,523,631,733,827,941,1051,1163,1277):
   name=f'{case}_s{seed}_{group}';x=json.loads((r/(name+'.json')).read_text());trigger=x['trigger_abs_s']
   if trigger is None:continue
   with np.load(r/(name+'_yaw.npz')) as y, np.load(p/'runs'/f'{case}_s{seed}'/'signals.npz') as sig:
    assert y['t'][0]<=trigger<=y['t'][-1]
    t=sig['t']; direction=sig['direction']
    source_time=trigger-x['start_abs_s']
    assert t[0]<=source_time<=t[-1],(name,trigger,t[0],t[-1])
    angle=float(np.interp(source_time,t,direction));yaw=float(np.interp(trigger,y['t'],y['yaw']))
    vals[str(seed)]=float(abs((angle-yaw+180)%360-180))
  out[case][group]=vals
assert sum(len(x[g]) for x in out.values() for g in ('G1','G2L'))==72
q=r/'trigger_yaw_error_r2.json';assert not q.exists();q.write_text(json.dumps(out,indent=2));print('TRIGGER_YAW_ERROR',q)
