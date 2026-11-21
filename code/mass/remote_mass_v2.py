from pathlib import Path
import os,time,tarfile,subprocess,json,zipfile,traceback
name=os.environ['MASS_GROUP'];assert name in ('D','M1','M2')
R=Path('/content/mass_'+name+'_v2');R.mkdir(exist_ok=False)
def log(s):
 with (R/'progress.log').open('a',buffering=1) as f:f.write(str(s)+'\n')
 print(s,flush=True)
try:
 with tarfile.open('/content/mass_'+name+'.tar.gz') as f:f.extractall(R,filter='data')
 stage=R/'stage';src=stage/'FluidX3D';case=stage/'case';conf=case/'conf.luwpf'
 import hashlib,struct,numpy as np
 assert hashlib.sha256((case/'wind_bc/profile.dat').read_bytes()).hexdigest().startswith('4fc0eede')
 records=np.load('/content/step4_native_v2_links_sparse.npz')['records'];rec=np.sort(records[(records['owner']==1)&(records['q']!=np.float32(.5))],order=['cell','direction']);N=500*500*470
 off=np.empty(N+1,dtype='<u4');off[0]=0;off[1:]=np.cumsum(np.bincount(rec['cell'].astype(np.int64),minlength=N),dtype=np.uint32)
 csr=R/'active_building_links.csr'
 with csr.open('wb') as f:
  f.write(struct.pack('<QQ',N,len(rec)));f.write(off.tobytes());f.write(rec['direction'].tobytes());f.write(rec['q'].tobytes());f.write(rec['owner'].tobytes())
 assert len(rec)==131569
 log('building links '+str(len(rec)))
 with (R/'build.log').open('w') as f:p=subprocess.run(['make','Linux','-B','-j4'],cwd=src,stdout=f,stderr=subprocess.STDOUT,timeout=600)
 log('build '+str(p.returncode));assert p.returncode==0,(R/'build.log').read_text()[-3000:]
 env=os.environ.copy();env['LUW_IBB_CSR']=str(csr)
 t0=time.monotonic()
 with (R/'solver.log').open('w',buffering=1) as f:
  p=subprocess.Popen([str(src/'bin/FluidX3D'),str(conf)],cwd=case,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,env=env)
  while p.poll() is None:
   time.sleep(15)
   csv=case/'RESULTS/mass_extrema.csv'
   if csv.exists():
    with csv.open() as q:
     import collections
     lines=collections.deque(q,maxlen=2)
    if lines and len(lines[-1].split(','))>3:
     a=lines[-1].split(',')
     if a[0].isdigit() and int(a[0])%1000==0:log('step '+a[0]+' max '+a[6])
   if time.monotonic()-t0>1800:p.terminate();log('TIMEOUT');break
  code=p.wait(timeout=90)
 (R/'exit.txt').write_text(str(code)+'\n');log('end '+str(code)+' '+str(round(time.monotonic()-t0)))
except Exception:
 (R/'error.txt').write_text(traceback.format_exc());log(traceback.format_exc()[-3000:])
finally:
 with zipfile.ZipFile('/content/mass_'+name+'_evidence.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
  for p in R.rglob('*'):
   if p.is_file() and p.name in ('progress.log','solver.log','build.log','exit.txt','error.txt','mass_extrema.csv','city_stability.csv'):
    z.write(p,str(p.relative_to(R)))
 (R/'done').write_text('done\n')
