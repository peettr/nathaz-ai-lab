from pathlib import Path
import os, time, tarfile, subprocess, shutil, json, struct, traceback
import numpy as np
R=Path('/content/luw_c3_linear_1016');R.mkdir(exist_ok=False)
def log(x):
 with (R/'progress.log').open('a',buffering=1) as f:f.write(str(x)+'\n')
 print(x,flush=True)
def csr(rec,p):
 rec=np.sort(rec,order=['cell','direction']); N=500*500*470
 off=np.empty(N+1,dtype='<u4');off[0]=0;off[1:]=np.cumsum(np.bincount(rec['cell'].astype(np.int64),minlength=N),dtype=np.uint32)
 with p.open('wb') as f:
  f.write(struct.pack('<QQ',N,len(rec)));f.write(off.tobytes());f.write(rec['direction'].tobytes());f.write(rec['q'].tobytes());f.write(rec['owner'].tobytes())
 return len(rec)
try:
 with tarfile.open('/content/bisect_stage.tar.gz') as t:t.extractall(R,filter='data')
 records=np.load('/content/bisect_links.npz')['records'];base=records[(records['owner']==1)&(records['q']!=np.float32(.5))]
 src=R/'stage/FluidX3D/src';d=src/'defines.hpp';defs=d.read_text();log('active '+str(len(base)))
 for name,mode in [('Lhigh','all')]:
  run=R/name;run.mkdir();case=run/'case';shutil.copytree(R/'stage/case',case)
  conf=case/'conf.luwpf';ct=conf.read_text();assert 'run_nstep = 31000' in ct and 'purge_avg = 20000' in ct
  conf.write_text(ct.replace('run_nstep = 31000','run_nstep = 2000').replace('purge_avg = 20000','purge_avg = 0'))
  if mode=='none': rr=base[:0]
  elif mode=='high': rr=base[base['q']>=.5]
  elif mode=='low': rr=base[base['q']<.5]
  elif mode=='middle': rr=base[(base['q']>=.1)&(base['q']<=.9)]
  else: rr=base
  count=csr(rr,run/'links.csr');log(name+' links '+str(count))
  if mode=='no_sgs': d.write_text(defs.replace('#define SUBGRID','#undef SUBGRID',1))
  with (run/'build.log').open('w') as f: b=subprocess.run(['make','Linux']+(['-B'] if mode=='no_sgs' else [])+['-j4'],cwd=R/'stage/FluidX3D',stdout=f,stderr=subprocess.STDOUT,timeout=500)
  log(name+' build '+str(b.returncode));
  if b.returncode: log((run/'build.log').read_text()[-2500:]);break
  d.write_text(defs)
  env=os.environ.copy();env['LUW_IBB_CSR']=str(run/'links.csr');env['LUW_GROUND_MIX_A']='0'
  t0=time.monotonic()
  with (run/'solver.log').open('w',buffering=1) as f:
   p=subprocess.run([str(R/'stage/FluidX3D/bin/FluidX3D'),str(case/'conf.luwpf')],cwd=case,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,env=env,timeout=600)
  event=case/'RESULTS/bisect_event.csv';rows=event.read_text() if event.exists() else ''
  trace=case/'RESULTS/city_stability.csv'
  (run/'event.csv').write_text(rows)
  (run/'solver.exit').write_text(str(p.returncode))
  log(name+' result '+str(p.returncode)+' seconds '+str(round(time.monotonic()-t0,2))+' event '+repr(rows[-400:])+' trace '+(trace.read_text()[-200:] if trace.exists() else 'none'))
  # Stop early only if timeout, no hardware or build failure. Experimental early threshold is expected.
except Exception:
 (R/'error.txt').write_text(traceback.format_exc());log(traceback.format_exc()[-3000:])
finally:(R/'all.done').write_text('done\n')
