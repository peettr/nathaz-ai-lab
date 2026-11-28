#!/usr/bin/env python3
"""A170② CM1 P1: frozen input setup and paired G1/G2/G2Lc CPU solver.
Only called in Colab CPU; no structural solves on the local workstation.
"""
import os,sys,json,math,hashlib,tarfile,gzip,shutil,subprocess,traceback,time,struct
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
from cm1_native_field import Field
import colab_a170_4 as old
P=Path(os.environ['A170_ROOT']); S=P/'runs';R=P/'results'
SEEDS=list(range(1301,1337));WOOD_SEEDS=SEEDS[:12]
RATIOS=np.array(old.RATIOS)
START=1860.;END=2700.;DT=.25

def checksum(f):
 h=hashlib.sha256()
 with open(f,'rb') as stream:
  for b in iter(lambda:stream.read(1048576),b''):h.update(b)
 return h.hexdigest()

def init():
 if P.exists():raise FileExistsError(P)
 old.P=P;old.setup();S.mkdir(exist_ok=True);R.mkdir(exist_ok=True)
 assert checksum(os.environ['A170_P1'])==os.environ['P1_SHA256']
 # Patch the old r2 runner's staging paths, never modify the source bundle.
 old.P=P
 os.environ.update(R2_YAW_RATE='0.004188790204786391',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')

def moving(t,x,seconds=3):
 n=round(seconds/DT);y=np.convolve(x,np.ones(n)/n,'full')[:len(x)];y[:n-1]=np.nan;return y

def write_bts(path,vel):
 a=np.asarray(vel,np.float32);assert a.shape[0]==3 and a.shape[2:]==(7,7)
 encoded=np.empty(a.shape,dtype='<i2');coef=[]
 for c in range(3):
  lo=float(a[c].min())-.01;hi=float(a[c].max())+.01
  slope=65000/(hi-lo);shift=-32500-slope*lo
  encoded[c]=np.rint(np.clip(a[c]*slope+shift,-32768,32767)).astype('<i2')
  coef.extend((slope,shift))
 label=b'CM1 D420 W3 true 4D P1 + subgrid synthetic; A170_2'
 with open(path,'wb') as f:
  f.write(struct.pack('<h4l',7,7,7,0,len(a[0])))
  f.write(struct.pack('<6f',28.,28.,DT,12.,90.,6.))
  f.write(struct.pack('<6f',*coef));f.write(struct.pack('<l',len(label)));f.write(label)
  for i in range(len(a[0])):f.write(encoded[:,i].tobytes(order='F'))
 assert path.stat().st_size==70+len(label)+294*len(a[0])
 return coef

def phase_pad(src,dst):
 blob=src.read_bytes();fid,nz,ny,ntwr,n=struct.unpack('<h4l',blob[:18]);off=70+struct.unpack('<l',blob[66:70])[0]
 assert (fid,nz,ny,ntwr)==(7,7,7,0) and len(blob)==off+294*n
 with dst.open('wb') as f:
  f.write(struct.pack('<h4l',fid,nz,ny,ntwr,n+28));f.write(blob[18:off]);f.write(blob[off:off+294]*28);f.write(blob[off:])

def make_seed(seed,profile):
 b,a,_,_,D,_=old.mods();tag=f'P1_{profile}';root=S/f'{tag}_s{seed}'
 if (root/'provenance.json').exists():return json.loads((root/'provenance.json').read_text())
 root.mkdir(exist_ok=False)
 field=Field(os.environ['A170_P1'],profile);field.set_origin(3,21)
 assert abs(field.xh[21]-60.9500046)<.0001 and abs(field.yh[3]-28.7500019)<.0001
 t=np.arange(START,END+12.01,DT);nt=len(t);src_t=np.clip(t,START,END)
 rotor=[(0.,float(y),float(z)) for y in b.Y for z in b.Z]
 # Spectral method is frozen at its native 0.5s; interpolate its residual to 0.25s.
 coords=rotor+[(-float(D),float(y),float(z)) for y in (-42,0,42) for z in (48,90,132)]
 # Frozen rule: mean of 90-m horizontal speed on [peak time - 60 s, peak time).
 # The point's 3-s peak time is 2078 s in the CRC selection record.
 peak_t=2078.0
 prepeak=np.arange(peak_t-60,peak_t,1.)
 prepeak_uv=field.sample(prepeak,0,0,90)[:2]
 mean_speed=float(np.hypot(prepeak_uv[0],prepeak_uv[1]).mean())
 assert len(prepeak)==60 and np.all(prepeak<peak_t)
 h=np.arange(START,END+12.01,.5); b.UCOH=mean_speed
 k=b.spectral_field(seed,len(h),coords)
 sigma=.1*mean_speed
 residual=np.stack([np.interp(t,h,k[c,i]) for c in range(3) for i in range(len(coords))]).reshape(3,len(coords),nt).transpose(0,2,1)
 residual*=sigma*RATIOS[:,None,None]
 wind=np.empty((3,nt,len(coords)),dtype=np.float32)
 for i,(x,y,z) in enumerate(coords):wind[:,:,i]=field.sample(src_t,x,y,z)+residual[:,:,i]
 raw=root/'raw.bts';write_bts(raw,wind[:,:,:49].reshape(3,nt,7,7));phase_pad(raw,root/'wind.bts');raw.unlink()
 disk=np.array([y*y+(z-90)**2<=63**2 for _,y,z in rotor]);vec=wind[:2,:,:49][:,:,disk].mean(axis=2)
 disk_sp=np.hypot(vec[0],vec[1]);disk_3=moving(t,disk_sp)
 active=t<=END
 hit=b.first_cross(t[active],disk_3[active],25.)
 first13=b.first_cross(t[active],disk_3[active],13.)
 last25=t[np.flatnonzero(active&np.isfinite(disk_3)&(disk_3>25))[-1]] if hit is not None else END
 up=wind[:2,:,49:].mean(axis=2);upsp=np.hypot(up[0],up[1]);fixed=moving(t,np.interp(t-1,t,a.smooth(upsp,DT,1),left=upsp[0]))
 g2=b.first_cross(t[active],fixed[active],25.)
 p=dict(case=tag,seed=seed,start_abs_s=START,end_abs_s=END,rotor_3s_first25_abs_s=hit,
        rotor_3s_first13_abs_s=first13,rotor_3s_last25_abs_s=float(last25),g2_trigger_abs_s=g2,
        prepeak60_mean_speed_mps=mean_speed,peak_time_abs_s=peak_t,
        prepeak_window_abs_s=[peak_t-60,peak_t],sigma_u_mps=sigma,profile=profile,
        cm1_sha256=os.environ['P1_SHA256'],bts_sha256=checksum(root/'wind.bts'),
        time_interpolation='linear 1s CM1 -> 0.25s BTS; 0.5s spectral residual -> 0.25s linear',
        initial_yaw_deg=float(np.rad2deg(np.arctan2(*field.sample(START,0,0,90)[1::-1]))))
 np.savez_compressed(root/'signals.npz',t=t,rotor=disk_3,rotor_raw=disk_sp,direction=np.rad2deg(np.unwrap(np.arctan2(vec[1],vec[0]))),
                     up_u=up[0],up_v=up[1],up_ideal=fixed)
 (root/'provenance.json').write_text(json.dumps(p,indent=2));return p

def row(seed,profile,group,hit):
 p=json.loads((S/f'P1_{profile}_s{seed}'/'provenance.json').read_text())
 return dict(case=p['case'],seed=seed,group=group,source=str(S/f'P1_{profile}_s{seed}'),
             start_abs_s=START,end_abs_s=END,trigger_abs_s=hit,actual_lead_s=None if hit is None or p['rotor_3s_first25_abs_s'] is None else p['rotor_3s_first25_abs_s']-hit)

def g2lc_hit(seed,profile):
 b,a,_,_,D,_=old.mods();root=S/f'P1_{profile}_s{seed}';z=np.load(root/'signals.npz');t=z['t'];f=Field(os.environ['A170_P1'],profile);f.set_origin(3,21)
 yaw=np.load(R/f'P1_{profile}_s{seed}_G1_yaw.npz');theta=np.deg2rad(np.interp(t,yaw['t'],yaw['yaw'],left=yaw['yaw'][0],right=yaw['yaw'][-1]))
 ts=np.clip(t,START,END)
 xx=-float(D)*np.cos(theta);yy=-float(D)*np.sin(theta)
 src=np.zeros((2,len(t)),float)
 for lateral in (-42,0,42):
  for height in (48,90,132):
   vec=f.sample(ts,xx-lateral*np.sin(theta),yy+lateral*np.cos(theta),height)
   src+=vec[:2]/9
 # Residual at the fixed 3x3 preview grid; deterministic CM1 reference evaluated there.
 deterministic=np.zeros_like(src)
 for lateral in (-42,0,42):
  for height in (48,90,132):deterministic+=f.sample(ts,-float(D),lateral,height)[:2]/9
 res=np.stack([z['up_u'],z['up_v']])-deterministic
 uv=src+res
 los=uv[0]*np.cos(theta)+uv[1]*np.sin(theta)
 signal=moving(t,np.interp(t-1,t,a.smooth(los,DT,1),left=los[0]))
 return b.first_cross(t[t<=END],signal[t<=END],25.)

_original_stage=old.stage_run
def stage_with_initial_yaw(row,shutdown=True):
 dest=_original_stage(row,shutdown)
 # Diagnostic output must include the first second for every group (G2/G2Lc
 # otherwise inherit a late TStart in A170_4). No physical input is changed.
 from colab_a170_4 import mods
 _,a,_,_,_,_=mods()
 p=json.loads((Path(row['source'])/'provenance.json').read_text())
 initial=f"{p['initial_yaw_deg']:.8f}"
 a.replace_key(dest/'NREL-5MW.fst','TStart','0.0')
 a.replace_key(dest/'NRELOffshrBsline5MW_Onshore_ElastoDyn.dat','NacYaw',initial)
 a.replace_key(dest/'NRELOffshrBsline5MW_Onshore_ServoDyn.dat','YawNeut',initial)
 # ROSCO Y_ControlMode=1 uses measured initial nacelle yaw as its initial
 # commanded reference; retain Y_Rate and all other DISCON inputs unchanged.
 ed=(dest/'NRELOffshrBsline5MW_Onshore_ElastoDyn.dat').read_text()
 sd=(dest/'NRELOffshrBsline5MW_Onshore_ServoDyn.dat').read_text()
 assert any('NacYaw' in line and line.split()[0]==initial for line in ed.splitlines())
 assert any('YawNeut' in line and line.split()[0]==initial for line in sd.splitlines())
 return dest
old.stage_run=stage_with_initial_yaw

def run_one(r):
 key=f"{r['case']}_s{r['seed']}_{r['group']}";dest=R/(key+'.json')
 if dest.exists():return json.loads(dest.read_text())
 if r['trigger_abs_s'] is None:
  x=old.run_one(dict(r,trigger_abs_s=END+100),shutdown=False);x['trigger_abs_s']=None;x['not_triggered']=True
  dest.write_text(json.dumps(x,indent=2))
 else:x=old.run_one(r)
 if x['returncode']!=0:raise RuntimeError(f"solver failed: {key}: {x.get('error_tail','')}")
 return x

def checkpoint():
 # Only main thread writes the archive; never race periodic archive workers.
 tmp=P/'checkpoint.new.tar.gz'
 with tarfile.open(tmp,'w:gz') as tf:
  for f in R.glob('*.json'):tf.add(f,arcname=f.name)
  for f in R.glob('*_yaw.npz'):tf.add(f,arcname=f.name)
 tmp.replace(P/'checkpoint.tar.gz')

def main():
 mode=sys.argv[1] if len(sys.argv)>1 else 'smoke'
 if mode not in ('smoke','full'):raise ValueError(mode)
 if not P.exists():init()
 else:
  old.P=P
  os.environ.update(R2_YAW_RATE='0.004188790204786391',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
  assert checksum(os.environ['A170_P1'])==os.environ['P1_SHA256']
 from concurrent.futures import ThreadPoolExecutor,as_completed
 jobs=([(SEEDS[0],'power')] if mode=='smoke' else
       [(s,'power') for s in SEEDS]+[(s,'wood') for s in WOOD_SEEDS])
 for profile in ('power','wood'):
  for seed,p in jobs:
   if p==profile:
    prov=make_seed(seed,profile)
    print('FIELD',profile,seed,prov['rotor_3s_first25_abs_s'],prov['bts_sha256'],flush=True)
  with ThreadPoolExecutor(max_workers=4) as pool:
   futs=[pool.submit(run_one,row(seed,profile,'G1',json.loads((S/f'P1_{profile}_s{seed}'/'provenance.json').read_text())['rotor_3s_first25_abs_s'])) for seed,p in jobs if p==profile]
   for fut in as_completed(futs):print('G1',fut.result()['returncode'],flush=True)
  checkpoint()
  for seed,p in jobs:
   if p==profile:
    prov=json.loads((S/f'P1_{profile}_s{seed}'/'provenance.json').read_text());hit=g2lc_hit(seed,profile)
    print('G2LC_TRIGGER',profile,seed,hit,flush=True)
    (R/f'P1_{profile}_s{seed}_triggers.json').write_text(json.dumps({'G1':prov['rotor_3s_first25_abs_s'],'G2':prov['g2_trigger_abs_s'],'G2Lc':hit}))
  with ThreadPoolExecutor(max_workers=4) as pool:
   futs=[]
   for seed,p in jobs:
    if p!=profile:continue
    hits=json.loads((R/f'P1_{profile}_s{seed}_triggers.json').read_text())
    for g in (('G2','G2Lc') if profile=='power' else ('G2Lc',)):futs.append(pool.submit(run_one,row(seed,profile,g,hits[g])))
   for fut in as_completed(futs):print('OTHER',fut.result()['returncode'],flush=True)
  checkpoint()
 print('COMPLETE',len(list(R.glob('P1_*_G1.json'))),len(list(R.glob('P1_*_G2.json'))),len(list(R.glob('P1_*_G2Lc.json'))),flush=True)
if __name__=='__main__':
 try:
  mode=sys.argv[1] if len(sys.argv)>1 else 'smoke'
  main();checkpoint();Path('/content/a170_2_'+mode+'.done').write_text('ok\n')
 except BaseException:
  traceback.print_exc();Path('/content/a170_2.failed').write_text(traceback.format_exc());sys.exit(1)
