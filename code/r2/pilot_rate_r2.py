import os,sys,json,time,hashlib
from pathlib import Path
import numpy as np
sys.path.insert(0,'/content')
import colab_d_run_r2 as d
P=d.P
b,a,cases,field,D,read_out=d.mods()
os.environ['R2_YAW_RATE']='0.004188790204786391' # 0.24 deg/s in rad/s
os.environ.pop('R2_YAW_DAMP',None)
for tag in ('I_near','III_kzm05'):
 root=P/'runs'/f'{tag}_s112';p=json.loads((root/'provenance.json').read_text());z=np.load(root/'signals.npz');t=z['t']
 for grp in ('G1','G2L'):
  if grp=='G2L':
   yy=np.load(P/'results'/f'{tag}_s112_G1_rate24_yaw.npz');yaw=np.interp(t,yy['t'],yy['yaw'],left=yy['yaw'][0],right=yy['yaw'][-1]);theta=np.deg2rad(yaw)
   c=next(x for x,name in d.case_list(cases) if name==tag)
   mu,mv,_=field(c,-D*np.cos(theta),-D*np.sin(theta),np.full(len(t),90.),t)
   fixed=np.array([field(c,-D,float(y),float(h),t)[:2] for y in (-42.,0.,42.) for h in (48.,90.,132.)]);ru=z['up_u']-fixed[:,0,:].mean(axis=0);rv=z['up_v']-fixed[:,1,:].mean(axis=0)
   los=(mu+ru)*np.cos(theta)+(mv+rv)*np.sin(theta);signal=d.moving(t,np.interp(t-1,t,a.smooth(los,b.DT,1),left=los[0]),3);hit=b.first_cross(t[t<=p['end_abs_s']],signal[t<=p['end_abs_s']],25)
  else:hit=p['rotor_3s_first25_abs_s']
  row=dict(case=tag,seed=112,group=grp+'_rate24',source=str(root),start_abs_s=p['start_abs_s'],end_abs_s=p['end_abs_s'],trigger_abs_s=hit)
  v=d.run_one(row); dest=P/'runs'/f'run_{tag}_s112_{grp}_rate24'
  rec=dict(tag=tag,group=grp,rate_command=.24,trigger_abs_s=hit,secant=v.get('yaw_rate_max_deg_s'),hp_pp=v.get('yaw_highpass_gt_0p5hz_pp_deg'),yaw_start_end=[float(read_out(dest/'NREL-5MW.out',['NacYaw'])['NacYaw'][k]) for k in (0,-1)],wall_s=v['wall_s'],hashes={f:hashlib.sha256((dest/f).read_bytes()).hexdigest() for f in ('DISCON.IN','NRELOffshrBsline5MW_Onshore_ServoDyn.dat','NRELOffshrBsline5MW_Onshore_ElastoDyn.dat')})
  with (P/'pilot_rate_r2.jsonl').open('a') as f:f.write(json.dumps(rec)+'\n')
  print('PILOT_RATE',json.dumps(rec),flush=True)
(P/'pilot_rate_r2.done').write_text('success\n')
