"""Postprocess only: trigger yaw error, using preserved high-precision G2L out."""
import json,numpy as np
from pathlib import Path
from colab_d_full_r2 import mods
p=Path('/content/a3_d_yawfix_r2_full');r=p/'results';out={};read_out=mods()[-1]
for case in ('I_near','III_kzm05','III_kzm00'):
 out[case]={}
 for group in ('G1','G2L'):
  vals={}
  for seed in (112,203,317,419,523,631,733,827,941,1051,1163,1277):
   name=f'{case}_s{seed}_{group}';x=json.loads((r/(name+'.json')).read_text());trigger=x['trigger_abs_s']
   if trigger is None:continue
   with np.load(p/'runs'/f'{case}_s{seed}'/'signals.npz') as sig:
    t=sig['t'];assert t[0]<=trigger<=t[-1];angle=float(np.interp(trigger,t,sig['direction']))
   if group=='G1':
    with np.load(r/(name+'_yaw.npz')) as y:yaw=float(np.interp(trigger,y['t'],y['yaw']))
   else:
    d=read_out(p/'runs'/('run_'+name)/'NREL-5MW.out',['Time','NacYaw'])
    tt=d['Time']+x['start_abs_s'];assert tt[0]<=trigger<=tt[-1],(name,tt[0],trigger,tt[-1]);yaw=float(np.interp(trigger,tt,d['NacYaw']))
   vals[str(seed)]=float(abs((angle-yaw+180)%360-180))
  out[case][group]=vals;print(case,group,len(vals),flush=True)
assert sum(len(x[g]) for x in out.values() for g in ('G1','G2L'))==72
q=r/'trigger_yaw_error_r2.json';assert not q.exists();q.write_text(json.dumps(out,indent=2));print('TRIGGER_YAW_ERROR',q)
