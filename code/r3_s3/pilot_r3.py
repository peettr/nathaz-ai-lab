import os,sys,json,time,hashlib
from pathlib import Path
import numpy as np
sys.path.insert(0,'/content')
import colab_d_run_r3 as m
P=m.P

def one(group):
 root=P/'runs/III_kzm00_s1051'; p=json.loads((root/'provenance.json').read_text())
 if group=='G1': hit=p['rotor_3s_first25_abs_s']
 else:
  z=np.load(root/'signals.npz'); t=z['t']; yy=np.load(P/'results/III_kzm00_s1051_G1_yaw.npz'); yaw=np.interp(t,yy['t'],yy['yaw'],left=yy['yaw'][0],right=yy['yaw'][-1]); err=np.abs((z['direction']-yaw+180)%360-180); sig=m.moving(t,((err>30)&(z['rotor_raw']>15)).astype(float),3); hit=m.mods()[0].first_cross(t[t<=p['end_abs_s']],sig[t<=p['end_abs_s']],.999)
 row=dict(case='III_kzm00',seed=1051,group=group,source=str(root),start_abs_s=p['start_abs_s'],end_abs_s=p['end_abs_s'],trigger_abs_s=hit,actual_lead_s=None if hit is None else p['rotor_3s_first25_abs_s']-hit)
 result=m.run_one(row,shutdown=hit is not None)
 dest=P/'runs'/f'run_III_kzm00_s1051_{group}'
 if not dest.exists(): dest=P/'runs'/f'run_III_kzm00_s1051_{group}_attempt2'
 d=m.mods()[-1](dest/'NREL-5MW.out',['Time','NacYaw']);t=d['Time'];yaw=np.rad2deg(np.unwrap(np.deg2rad(d['NacYaw'])));i=np.searchsorted(t,t+1);v=i<len(t); rates=np.abs((yaw[i[v]]-yaw[v])/(t[i[v]]-t[v]));j=int(np.argmax(rates)); k=np.flatnonzero(v)[j]
 info=dict(group=group,trigger_abs_s=hit,trigger_rel_s=None if hit is None else hit-p['start_abs_s'],max_secant=float(rates[j]),worst_window_rel_s=[float(t[k]),float(t[i[k]])],worst_window_abs_s=[float(t[k]+p['start_abs_s']),float(t[i[k]]+p['start_abs_s'])],angle_delta_deg=float(yaw[i[k]]-yaw[k]),max_before_trigger=float(np.max(rates[t[v]<hit-p['start_abs_s']])) if hit is not None else None, max_after_trigger=float(np.max(rates[t[v]>=hit-p['start_abs_s']])) if hit is not None and np.any(t[v]>=hit-p['start_abs_s']) else None, yaw_dof_true='True' in next(x for x in (dest/'NRELOffshrBsline5MW_Onshore_ElastoDyn.dat').read_text().splitlines() if 'YawDOF' in x), returncode=result['returncode'], hashes={name:hashlib.sha256((dest/name).read_bytes()).hexdigest() for name in ['DISCON.IN','NRELOffshrBsline5MW_Onshore_ServoDyn.dat']})
 print(json.dumps(info),flush=True);return info
if __name__=='__main__':
 if not P.exists():m.setup()
 root=P/'runs/III_kzm00_s1051'
 if not root.exists():
  c=next(c for c,tag in m.case_list(m.mods()[2]) if tag=='III_kzm00');m.make_storm(c,'III_kzm00',1051)
 os.environ['R3_YAW_RATE']=str(np.deg2rad(.24))
 rows=[]
 for group in ['G1','S3_30']: rows.append(one(group))
 (P/'pilot_r3.json').write_text(json.dumps(rows,indent=2))
