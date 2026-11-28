import os,sys,json,time,hashlib,traceback
from pathlib import Path
import numpy as np
sys.path.insert(0,'/content')
import colab_d_run_r2 as d
P=d.P
b,a,cases,field,D,read_out=d.mods()
for tag in ('I_near','III_kzm05'):
 c=next(c for c,n in d.case_list(cases) if n==tag)
 d.make_storm(c,tag,112)
 p=json.loads((P/'runs'/f'{tag}_s112'/'provenance.json').read_text())
 for damp in ('1.916E+07','1.916E+08'):
  os.environ['R2_YAW_DAMP']=damp
  row=dict(case=tag,seed=112,group='G1' if damp=='1.916E+07' else 'G1_damp10',source=str(P/'runs'/f'{tag}_s112'),start_abs_s=p['start_abs_s'],end_abs_s=p['end_abs_s'],trigger_abs_s=p['rotor_3s_first25_abs_s'])
  t0=time.monotonic()
  x=d.run_one(row)
  dest=P/'runs'/f'run_{tag}_s112_{row["group"]}'
  z=read_out(dest/'NREL-5MW.out',['Time','NacYaw'])
  t=z['Time'];y=np.rad2deg(np.unwrap(np.deg2rad(z['NacYaw'])))
  idx=np.searchsorted(t,t+1,side='left');v=idx<len(t);rates=np.abs((y[idx[v]]-y[v])/(t[idx[v]]-t[v]));j=np.flatnonzero(v)[rates.argmax()]
  rec=dict(tag=tag,damp=damp,secant=x.get('yaw_rate_max_deg_s'),highpass_pp=x.get('yaw_highpass_gt_0p5hz_pp_deg'),max_window=[float(t[j]),float(t[idx[j]])],max_angles=[float(y[j]),float(y[idx[j]])],yaw_range=[float(y.min()),float(y.max())],start_abs_s=p['start_abs_s'],wall_s=time.monotonic()-t0,hashes={f:hashlib.sha256((dest/f).read_bytes()).hexdigest() for f in ('DISCON.IN','NRELOffshrBsline5MW_Onshore_ServoDyn.dat','NRELOffshrBsline5MW_Onshore_ElastoDyn.dat')},old_ascii_case_I_s112_G1=.8129032258118514 if tag=='I_near' else None)
  with (P/'pilot_r2.jsonl').open('a') as f:f.write(json.dumps(rec)+'\n')
  print('PILOT',json.dumps(rec),flush=True)
(P/'pilot_r2.done').write_text('success\n')
