from pathlib import Path
import tarfile, subprocess,time,traceback,shutil,json,hashlib,os
R=Path('/content/b2s_case');R.mkdir(exist_ok=False)
def log(s):
 with (R/'progress.log').open('a',buffering=1) as f:f.write(str(s)+'\n')
 print(s,flush=True)
def trace_last(path):
 if not path.exists():return None
 with path.open() as f:
  h=f.readline().strip().split(',');last=''
  for line in f:last=line
 return dict(zip(h,last.strip().split(','))) if last else None
try:
 with tarfile.open('/content/B2u_inputs.tar.gz') as t:t.extractall(R,filter='data')
 defs=R/'FluidX3D/src/defines.hpp';s=defs.read_text();assert s.count('//#define CITY_STABILITY_MONITOR')==1
 defs.write_text(s.replace('//#define CITY_STABILITY_MONITOR','#define CITY_STABILITY_MONITOR'))
 with (R/'build.log').open('w') as f:p=subprocess.run(['make','Linux','-j4'],cwd=R/'FluidX3D',stdout=f,stderr=subprocess.STDOUT,timeout=900)
 log('BUILD '+str(p.returncode));assert p.returncode==0,(R/'build.log').read_text()[-3000:]
 case=R/'case';trace=case/'RESULTS/city_stability.csv';start=time.monotonic();reason=None
 with (R/'solver.log').open('w',buffering=1) as f:
  proc=subprocess.Popen([str(R/'FluidX3D/bin/FluidX3D'),str(case/'conf.luwpf')],cwd=case,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT)
  seen=-1
  while proc.poll() is None:
   time.sleep(5);q=trace_last(trace)
   if q and int(q['step'])!=seen:
    seen=int(q['step'])
    if seen%1000==0:log(f'STEP {seen}')
    if q['first_nonfinite_xyz_component'] or float(q['max_u_lattice'])>.3 or (seen>=3000 and (float(q['min_rho'])<.9 or float(q['max_rho'])>1.1)):
     reason='v3 exceeded '+str(q);proc.terminate();break
   if time.monotonic()-start>2100:reason='walltime budget';proc.terminate();break
  code=proc.wait(timeout=90)
 (R/'case.exit').write_text(f'{code} {reason}\n');log(f'EXIT {code} {reason} {int(time.monotonic()-start)}s')
 assert code==0 and reason is None
 shutil.copy2('/content/points_w_r7.json',R/'points_w_r7.json')
 shutil.copy2('/content/geometry.json',R/'geometry.json')
 shutil.copy2('/content/b2u_reference.json',R/'b2u_reference.json')
 with (R/'extract.log').open('w') as f:p=subprocess.run(['python3','/content/extract_B2s.py'],cwd=R,stdout=f,stderr=subprocess.STDOUT,timeout=500)
 log('EXTRACT '+str(p.returncode));assert p.returncode==0,(R/'extract.log').read_text()[-4000:]
 paths=[R/'nearwall_80.json',R/'extract_manifest.json',trace,*R.glob('local_*.npz'),*R.glob('plane_z*.npz')]
 assert len(paths)==16,len(paths)
 hashes={str(q.relative_to(R)): {'sha256':hashlib.sha256(q.read_bytes()).hexdigest(),'bytes':q.stat().st_size} for q in paths}
 (R/'hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
 log('RESULT VERIFIED '+str(len(paths)))
except Exception:
 (R/'error.txt').write_text(traceback.format_exc());log(traceback.format_exc()[-5000:])
finally:(R/'all.done').write_text('done\n')
