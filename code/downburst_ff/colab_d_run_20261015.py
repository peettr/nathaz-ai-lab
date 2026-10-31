"""A3-D Colab-only preregistered rule comparison; no 工作站 solves.
Nguyen 2012 chapter 4.4 translation-speed turbulence, spectrum-component ratios.
Checkpoints in /content/a3_d_1015/results; never overwrite earlier A/B/C outputs.
"""
import os,sys,json,time,gzip,tarfile,shutil,subprocess,concurrent.futures,traceback,hashlib,math
from pathlib import Path
from dataclasses import replace
import numpy as np
P=Path('/content/a3_d_1015')
SEEDS=[112,203,317,419,523,631,733,827,941,1051,1163,1277]
RULES=['G1','G2L','G2','S1','S2_23','S2_24','S3_30','S3_20','S4_05','S4_1']
RATIOS=(1.,.737388498467752,.33376882226228216) # PSD integral 0-1 Hz, PDF 74-75 eqs 3.17-19

def setup():
 P.mkdir(exist_ok=False)
 with tarfile.open('/content/a3_b_colab_bundle_1014.tar.gz') as tf:tf.extractall(P,filter='data')
 (P/'bin').mkdir()
 with gzip.open('/content/openfast_5_linux_1014.gz','rb') as src,(P/'bin/openfast').open('wb') as dst:shutil.copyfileobj(src,dst)
 (P/'bin/openfast').chmod(0o755)
 (P/'runs').mkdir();(P/'results').mkdir()
 print('VERSION',subprocess.run([str(P/'bin/openfast'),'-v'],capture_output=True,text=True).stdout[-250:],'CPUS',os.cpu_count(),flush=True)

def mods():
 sys.path.insert(0,str(P/'code'))
 import segment_b_run as b,segment_a_run as a
 from wind_field_probe import CASES,field,D
 from analyze_segment_b import read_out
 b.BASE=P/'base';b.ROOT=P/'runs';b.SRC=P/'base/ff_smoke_feedback';b.FAST=P/'bin/openfast';b.LIB=P/'base/rosco210_ff_build_guo_v2/libdiscon.so';a.CURVE=P/'base/segment_a_v4_curve.txt'
 return b,a,CASES,field,D,read_out

def moving(t,x,sec,dt=.5):
 n=int(round(sec/dt));v=np.convolve(x,np.ones(n)/n,mode='full')[:len(t)];v[:n-1]=np.nan;return v

def starts(t,x,threshold):
 h=np.isfinite(x)&(x>threshold);return t[np.flatnonzero(h&~np.r_[False,h[:-1]])].tolist()

def case_list(cases):
 return [(cases[0],'I_near'),(replace(cases[1],kzm=.05),'III_kzm05'),(replace(cases[1],kzm=0.),'III_kzm00')]

def make_storm(c,tag,seed):
 b,a,_,field,D,_=mods();root=P/'runs'/f'{tag}_s{seed}';root.mkdir(exist_ok=False)
 old=json.loads((P/'base/segment_a_v10'/c.name/'provenance.json').read_text())
 start,end=old['window_abs'];t=np.arange(start,end+25+b.DT*.5,b.DT);nt=len(t)
 rotor=[(0.,float(y),float(z)) for y in b.Y for z in b.Z]
 preview=[(-float(D),float(y),float(z)) for y in (-42.,0.,42.) for z in (48.,90.,132.)]
 coords=rotor+preview
 k=b.spectral_field(seed,nt,coords)
 wind=np.empty((3,nt,len(coords)),np.float32)
 for i,(x,y,z) in enumerate(coords):
  vec=field(c,x,y,z,t)
  wind[:,:,i]=np.stack(vec)+np.asarray(RATIOS)[:,None]*(.1*c.trans)*k[:,i,:]
 disk=np.array([y*y+(z-90)**2<=63**2 for x,y,z in rotor]);u=wind[0,:,:49][:,disk].mean(axis=1);v=wind[1,:,:49][:,disk].mean(axis=1)
 rotor_sp=np.hypot(u,v);rotor_avg=moving(t,rotor_sp,3);direction=np.rad2deg(np.unwrap(np.arctan2(v,u)))
 upu=wind[0,:,49:].mean(axis=1);upv=wind[1,:,49:].mean(axis=1)
 upideal=moving(t,np.interp(t-1,t,a.smooth(np.hypot(upu,upv),b.DT,1),left=np.hypot(upu[0],upv[0])),3)
 active=t<=end;hit=b.first_cross(t[active],rotor_avg[active],25)
 assert hit is not None,(tag,seed)
 p=dict(case=tag,seed=seed,start_abs_s=start,end_abs_s=end,rotor_3s_first25_abs_s=hit,
        rotor_3s_first13_abs_s=b.first_cross(t[active],rotor_avg[active],13),
        rotor_3s_last25_abs_s=float(t[np.flatnonzero(active&np.isfinite(rotor_avg)&(rotor_avg>25))[-1]]),
        kzm_mps=c.kzm,turbulence='chapter 4.4 translation speed; normalized Kaimal spectra, std ratios '+str(RATIOS),
        bts_phase_correction='14 x 0.5 s initial frames inserted; OpenFAST t+7s lookup')
 b.write_bts(root/'raw.bts',wind[:,:,:49].reshape(3,nt,b.NY,b.NZ))
 b.phase_correct_bts(root/'raw.bts',root/'wind.bts');(root/'raw.bts').unlink()
 np.savez_compressed(root/'signals.npz',t=t,rotor=rotor_avg,rotor_raw=rotor_sp,direction=direction,up_u=upu,up_v=upv,up_ideal=upideal)
 (root/'provenance.json').write_text(json.dumps(p,indent=2));print('STORM_FIELD',tag,seed,hit,flush=True)
 return p

def stage_run(row,shutdown=True):
 b,a,_,_,_,_=mods();root=Path(row['source']);dest=b.stage(row)
 cfg=dest/'DISCON.IN'
 if not shutdown:
  a.replace_discon(cfg,'SD_EnableTime','0');a.replace_discon(cfg,'SD_Time','9999.0')
 a.replace_key(dest/'NREL-5MW.fst','OutFileFmt','1')
 p=json.loads((root/'provenance.json').read_text())
 # Baseline yaw must be recorded from the beginning; output size stays remote.
 a.replace_key(dest/'NREL-5MW.fst','TStart','0.0' if row['group']=='G1' or not shutdown else f"{max(0.,p['rotor_3s_first13_abs_s']-row['start_abs_s']-5):.3f}")
 ed=dest/'NRELOffshrBsline5MW_Onshore_ElastoDyn.dat'
 s=ed.read_text();needle='END of input file (the word "END" must appear in the first 3 columns of this last OutList line)'
 if '"RootMyb2"' not in s:s=s.replace(needle,'"RootMyb2"\n"RootMyb3"\n'+needle);ed.write_text(s)
 return dest

def run_one(row,shutdown=True):
 b,a,_,_,_,read_out=mods();key=f"{row['case']}_s{row['seed']}_{row['group']}";out=P/'results'/(key+'.json')
 if out.exists():return json.loads(out.read_text())
 dest=stage_run(row,shutdown)
 env=os.environ.copy();env.update(ROSCO_FF_FILE=str(dest/'preview.txt'),ROSCO_FF_CURVE=str(a.CURVE),ROSCO_FF_GAIN_DEG_PER_MS='0',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
 now=time.monotonic()
 with (dest/'openfast.log').open('w') as log:
  try:rc=subprocess.run([str(b.FAST),'NREL-5MW.fst'],cwd=dest,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=1100).returncode
  except subprocess.TimeoutExpired:rc=-999
 entry=dict(row,returncode=rc,wall_s=round(time.monotonic()-now,2))
 if rc==0:
  cols=['Time','NacYaw','Wind1VelX','Wind1VelY','TwrBsMxt','TwrBsMyt','YawBrMzp','RootMyb1','RootMyb2','RootMyb3','RotSpeed']
  d=read_out(dest/'NREL-5MW.out',cols)
  t=d['Time'];start=row['start_abs_s'];p=json.loads((Path(row['source'])/'provenance.json').read_text())
  mask=(t+start>=p['rotor_3s_first13_abs_s'])&(t+start<=p['rotor_3s_last25_abs_s']+60)
  x,y=d['TwrBsMxt'][mask],d['TwrBsMyt'][mask]
  blades=np.stack([d[f'RootMyb{i}'][mask] for i in (1,2,3)])
  entry['metrics']=dict(tower_resultant_max_kNm=float(np.hypot(x,y).max()),tower_fore_aft_positive_max_kNm=float(y.max()),tower_fore_aft_negative_magnitude_kNm=float(max(0.,-y.min())),tower_top_yaw_absmax_kNm=float(np.abs(d['YawBrMzp'][mask]).max()),blade_root_positive_max_kNm=float(blades.max()),blade_root_negative_magnitude_kNm=float(max(0.,-blades.min())),rotor_speed_overshoot_vs_12p1_pct=float(100*(d['RotSpeed'][mask].max()/12.1-1)))
  yaw=np.rad2deg(np.unwrap(np.deg2rad(d['NacYaw'])))
  # ASCII .out rounds NacYaw to 0.01 deg at ~0.006 s; instant differences spuriously exceed 0.3 deg/s.
  # Report max finite 1 s secant (and note 0.01 deg output quantization).
  i=np.searchsorted(t,t+1.0,side='left');valid=i<len(t)
  entry['yaw_rate_max_deg_s']=float(np.max(np.abs((yaw[i[valid]]-yaw[valid])/(t[i[valid]]-t[valid]))))
  if row['group']=='G1' or not shutdown:np.savez_compressed(P/'results'/(key+'_yaw.npz'),t=t+start,yaw=yaw)
 else:entry['error_tail']=(dest/'openfast.log').read_text(errors='replace')[-1500:]
 out.write_text(json.dumps(entry,indent=2));print('DONE',key,rc,entry['wall_s'],flush=True)
 return entry

def storm_prep():
 b,a,cases,_,_,_=mods()
 for c,tag in case_list(cases):
  for seed in SEEDS:
   if (P/'runs'/f'{tag}_s{seed}'/'provenance.json').exists():continue
   make_storm(c,tag,seed)
 print('STORM_PREP_COMPLETE',flush=True)

def storm_base():
 rows=[]
 for tag in ('I_near','III_kzm05','III_kzm00'):
  for seed in SEEDS:
   root=P/'runs'/f'{tag}_s{seed}';p=json.loads((root/'provenance.json').read_text())
   rows.append(dict(case=tag,seed=seed,group='G1',source=str(root),start_abs_s=p['start_abs_s'],end_abs_s=p['end_abs_s'],trigger_abs_s=p['rotor_3s_first25_abs_s']))
 batch(rows,shutdown=True);print('STORM_BASE_COMPLETE',flush=True)

def build_rules():
 b,a,_,_,_,_=mods();rows=[]
 for tag in ('I_near','III_kzm05','III_kzm00'):
  for seed in SEEDS:
   root=P/'runs'/f'{tag}_s{seed}';p=json.loads((root/'provenance.json').read_text());z=np.load(root/'signals.npz');t=z['t'];valid=t<=p['end_abs_s']
   yawfile=P/'results'/f'{tag}_s{seed}_G1_yaw.npz';yy=np.load(yawfile)
   yaw=np.interp(t,yy['t'],yy['yaw'],left=yy['yaw'][0],right=yy['yaw'][-1]);direction=z['direction']
   # Moving beam point at one rotor diameter ahead of the actual baseline nacelle yaw.
   # Analytic 4D mean evaluated at that point independently. Turbulent residual is
   # inherited from the fixed 3x3 upstream samples (approximation: not a true
   # moving-point, frequency-dependent cross-spectral interpolation).
   c=next(x for x,name in case_list(mods()[2]) if name==tag)
   theta=np.deg2rad(yaw);from wind_field_probe import field,D
   xm=-D*np.cos(theta);ym=-D*np.sin(theta)
   mu,mv,_=field(c,xm,ym,np.full(len(t),90.),t)
   fixed=np.array([field(c,-D,float(yy),float(zz),t)[:2] for yy in (-42.,0.,42.) for zz in (48.,90.,132.)])
   residual_u=z['up_u']-fixed[:,0,:].mean(axis=0);residual_v=z['up_v']-fixed[:,1,:].mean(axis=0)
   # Moving deterministic 4D point on nacelle axis; turbulent residual inherited
   # from the original 3x3 fixed upstream samples. Approximate moving LOS only.
   los=(mu+residual_u)*np.cos(theta)+(mv+residual_v)*np.sin(theta)
   los3=moving(t,np.interp(t-1,t,a.smooth(los,b.DT,1),left=los[0]),3)
   rotor=z['rotor'];filtered=moving(t,a.smooth(z['rotor_raw'],b.DT,1),3)
   slow23=moving(t,z['rotor_raw'],10);slow24=slow23
   yawerr=np.abs((direction-yaw+180)%360-180)
   directional_rate=np.abs(np.gradient(direction,b.DT));rate3=moving(t,directional_rate,3)
   sp=z['rotor_raw']
   sig={'G2L':(los3,25.),'G2':(z['up_ideal'],25.),'S1':(filtered,25.),'S2_23':(slow23,23.),'S2_24':(slow24,24.),
        'S3_30':(moving(t,((yawerr>30)&(sp>15)).astype(float),3),.999),'S3_20':(moving(t,((yawerr>20)&(sp>15)).astype(float),3),.999),
        'S4_05':(np.where(sp>15,rate3,np.nan),.5),'S4_1':(np.where(sp>15,rate3,np.nan),1.)}
   for group,(signal,threshold) in sig.items():
    hit=b.first_cross(t[valid],signal[valid],threshold)
    rows.append(dict(case=tag,seed=seed,group=group,source=str(root),start_abs_s=p['start_abs_s'],end_abs_s=p['end_abs_s'],trigger_abs_s=hit,actual_lead_s=None if hit is None else p['rotor_3s_first25_abs_s']-hit))
 (P/'results/rules_manifest.json').write_text(json.dumps(rows,indent=2))
 print('RULES_READY',len(rows),'missing triggers',sum(x['trigger_abs_s'] is None for x in rows),flush=True)

def batch(rows,shutdown=True):
 n=min(6,max(1,(os.cpu_count() or 2)//2))
 def one(row):
  if row['trigger_abs_s'] is None:
   f=P/'results'/f"{row['case']}_s{row['seed']}_{row['group']}.json";entry=dict(row,returncode=0,not_triggered=True)
   # No stop means identical to no-shutdown baseline, but requires an independent run for load metrics.
   q=dict(row,trigger_abs_s=row['end_abs_s']+100)
   x=run_one(q,shutdown=False);x['trigger_abs_s']=None;x['not_triggered']=True;f.write_text(json.dumps(x,indent=2));return x
  return run_one(row,shutdown)
 with concurrent.futures.ThreadPoolExecutor(max_workers=n) as pool:
  futs=[pool.submit(one,row) for row in rows]
  for fut in concurrent.futures.as_completed(futs):
   try:
    x=fut.result();print('PROGRESS',x['case'],x['seed'],x['group'],x['returncode'],flush=True)
   except BaseException:print('ERROR',traceback.format_exc(),flush=True)

def storm_rules():
 rows=json.loads((P/'results/rules_manifest.json').read_text());batch(rows)
 files=[P/'results'/f"{r['case']}_s{r['seed']}_{r['group']}.json" for r in rows]
 status=dict(expected=len(rows),found=sum(f.exists() for f in files),successful=sum(f.exists() and json.loads(f.read_text())['returncode']==0 for f in files))
 (P/'results/storm_status.json').write_text(json.dumps(status));print('STORM_RULES_COMPLETE',status,flush=True)

def stationary_prep():
 b,a,_,_,D,_=mods();rotor=[(0.,float(y),float(z)) for y in b.Y for z in b.Z]
 preview=[(-float(D),float(y),float(z)) for y in (-42.,0.,42.) for z in (48.,90.,132.)]
 coords=rotor+preview;disk=np.array([y*y+(z-90)**2<=63**2 for x,y,z in rotor]);dt=b.DT
 for mean in (18,20,22):
  for seed in SEEDS:
   root=P/'runs'/f'NTM_U{mean}_s{seed}';root.mkdir(exist_ok=False)
   t=np.arange(0,600+25+dt/2,dt);b.UCOH=float(mean)
   k=b.spectral_field(seed+10000+mean*100,len(t),coords)
   sigma=.14*(.75*mean+5.6)
   u=np.array([mean*(z/90)**.2 for x,y,z in coords])[:,None]+sigma*k[0]
   v=.8*sigma*k[1];w=.5*sigma*k[2]
   rotor_u=u[:49][disk].mean(axis=0);rotor_v=v[:49][disk].mean(axis=0)
   up_u=u[49:].mean(axis=0);up_v=v[49:].mean(axis=0)
   sp=np.hypot(rotor_u,rotor_v);direction=np.rad2deg(np.unwrap(np.arctan2(rotor_v,rotor_u)))
   b.write_bts(root/'raw.bts',np.stack((u[:49].reshape(b.NY,b.NZ,len(t)).transpose(2,0,1),v[:49].reshape(b.NY,b.NZ,len(t)).transpose(2,0,1),w[:49].reshape(b.NY,b.NZ,len(t)).transpose(2,0,1))))
   b.phase_correct_bts(root/'raw.bts',root/'wind.bts');(root/'raw.bts').unlink()
   np.savez_compressed(root/'signals.npz',t=t,rotor_raw=sp,rotor=moving(t,sp,3),direction=direction,up_u=up_u,up_v=up_v)
   p=dict(start_abs_s=0.,end_abs_s=600.,rotor_3s_first13_abs_s=0.,rotor_3s_last25_abs_s=540.,method='approx IEC NTM B Kaimal: sigma=.14(.75U+5.6), coherence reference actual mean speed',mean_mps=mean,seed=seed)
   (root/'provenance.json').write_text(json.dumps(p));print('STATIONARY_FIELD',mean,seed,flush=True)
 print('STATIONARY_PREP_COMPLETE',flush=True)

def stationary_yaw():
 rows=[]
 for mean in (18,20,22):
  for seed in SEEDS:
   root=P/'runs'/f'NTM_U{mean}_s{seed}'
   rows.append(dict(case=f'NTM_U{mean}',seed=seed,group='NoStop',source=str(root),start_abs_s=0.,end_abs_s=600.,trigger_abs_s=700.))
 batch(rows,shutdown=False)
 print('STATIONARY_YAW_COMPLETE',flush=True)

def stationary_rules():
 b,a,_,_,_,_=mods();rows=[]
 for mean in (18,20,22):
  for seed in SEEDS:
   root=P/'runs'/f'NTM_U{mean}_s{seed}';z=np.load(root/'signals.npz');t=z['t'];active=t<=600
   yy=np.load(P/'results'/f'NTM_U{mean}_s{seed}_NoStop_yaw.npz')
   yaw=np.interp(t,yy['t'],yy['yaw'],left=yy['yaw'][0],right=yy['yaw'][-1]);theta=np.deg2rad(yaw)
   # Stationary field is horizontally homogeneous; use same fixed-grid residual
   # along the yaw-following LOS, preserving the storm-arm approximation.
   los=z['up_u']*np.cos(theta)+z['up_v']*np.sin(theta)
   los3=moving(t,np.interp(t-1,t,a.smooth(los,b.DT,1),left=los[0]),3)
   ideal=moving(t,np.interp(t-1,t,a.smooth(np.hypot(z['up_u'],z['up_v']),b.DT,1),left=np.hypot(z['up_u'][0],z['up_v'][0])),3)
   sp=z['rotor_raw'];direction=z['direction'];err=np.abs((direction-yaw+180)%360-180)
   filtered=moving(t,a.smooth(sp,b.DT,1),3);slow=moving(t,sp,10);r3=moving(t,np.abs(np.gradient(direction,b.DT)),3)
   sig={'G1':(z['rotor'],25),'G2L':(los3,25),'G2':(ideal,25),'S1':(filtered,25),'S2_23':(slow,23),'S2_24':(slow,24),
        'S3_30':(moving(t,((err>30)&(sp>15)).astype(float),3),.999),'S3_20':(moving(t,((err>20)&(sp>15)).astype(float),3),.999),
        'S4_05':(np.where(sp>15,r3,np.nan),.5),'S4_1':(np.where(sp>15,r3,np.nan),1.)}
   rules={name:dict(episodes=starts(t[active],s[active],threshold),false_stop=bool(starts(t[active],s[active],threshold))) for name,(s,threshold) in sig.items()}
   entry=dict(mean_mps=mean,seed=seed,rules=rules,yaw_max_rate_deg_s=float(np.max(np.abs(np.gradient(yy['yaw'],yy['t'])))))
   f=P/'results'/f'NTM_U{mean}_s{seed}_rules.json';f.write_text(json.dumps(entry));rows.append(entry)
   print('STATIONARY_RULES',mean,seed,{g:int(r['false_stop']) for g,r in rules.items()},flush=True)
 (P/'results/stationary_rules_all.json').write_text(json.dumps(rows))
 print('STATIONARY_RULES_COMPLETE',len(rows),flush=True)

if __name__=='__main__':globals()[sys.argv[1]]()
