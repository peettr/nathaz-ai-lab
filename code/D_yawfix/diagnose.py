import sys,os,json,time,subprocess,hashlib,traceback
from pathlib import Path
import numpy as np
sys.path.insert(0,'/content')
import colab_d_run as d
P=d.P
log=P/'diagnostic.jsonl'
def record(x):
 with log.open('a') as f:f.write(json.dumps(x)+'\n')
 print(x,flush=True)
def one(tag,seed,fix):
 b,a,cases,field,D,read_out=d.mods()
 root=P/'runs'/f'{tag}_s{seed}'
 p=json.loads((root/'provenance.json').read_text())
 row=dict(case=tag,seed=seed,group='G1_fix' if fix else 'G1',source=str(root),start_abs_s=p['start_abs_s'],end_abs_s=p['end_abs_s'],trigger_abs_s=p['rotor_3s_first25_abs_s'])
 dest=d.stage_run(row)
 a.replace_key(dest/'NREL-5MW.fst','TStart','0.0')
 a.replace_key(dest/'NREL-5MW.fst','OutFmt','"ES20.12E3"')
 ed=dest/'NRELOffshrBsline5MW_Onshore_ElastoDyn.dat'
 if fix:a.replace_key(ed,'YawDOF','False')
 env={**os.environ,'ROSCO_FF_FILE':str(dest/'preview.txt'),'ROSCO_FF_CURVE':str(a.CURVE),'ROSCO_FF_GAIN_DEG_PER_MS':'0','OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1'}
 t0=time.monotonic()
 with (dest/'openfast.log').open('w') as f:rc=subprocess.run([str(b.FAST),'NREL-5MW.fst'],cwd=dest,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=1100).returncode
 if rc:raise RuntimeError(str(dest)+' '+str(rc)+' '+(dest/'openfast.log').read_text()[-1500:])
 cols=['Time','NacYaw','TwrBsMyt','YawBrMzp']
 out=read_out(dest/'NREL-5MW.out',cols)
 t=out['Time']; yaw=np.rad2deg(np.unwrap(np.deg2rad(out['NacYaw']))); delta=np.diff(t)
 assert delta.max()<=.1,(delta.min(),delta.max())
 rate=np.abs(np.diff(yaw)/delta); i=int(rate.argmax())
 result=dict(tag=tag,seed=seed,fix=fix,max_rate_deg_s=float(rate[i]),max_interval=[float(t[i]),float(t[i+1])],yaw_at_max=[float(yaw[i]),float(yaw[i+1])],dt_max=float(delta.max()),wall_s=round(time.monotonic()-t0,2),input_hashes={name:hashlib.sha256((dest/name).read_bytes()).hexdigest() for name in ['DISCON.IN','NRELOffshrBsline5MW_Onshore_ServoDyn.dat','NRELOffshrBsline5MW_Onshore_ElastoDyn.dat']})
 record(result)
 return result
try:
 d.setup()
 for tag in ['III_kzm05','I_near']:
  c=next(c for c,n in d.case_list(d.mods()[2]) if n==tag)
  d.make_storm(c,tag,112)
  for fix in [False,True]:one(tag,112,fix)
 (P/'diagnostic.done').write_text('success\n')
except Exception:
 (P/'diagnostic.failed').write_text(traceback.format_exc());traceback.print_exc();raise
