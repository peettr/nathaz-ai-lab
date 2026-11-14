from pathlib import Path
import subprocess,tarfile,time,os,csv,shutil,json,statistics,traceback
TAGS=[('FG0z','0.0'),('FG0zA70','0.70')]
def lastrow(p):
 if not p.exists():return None
 with p.open() as f:
  h=f.readline().strip().split(',');v=''
  for v in f:pass
 return dict(zip(h,v.strip().split(','))) if v else None
for tag,a in TAGS:
 R=Path('/content/luw_z0_'+tag)
 R.mkdir(exist_ok=False)
 def log(s):
  with (R/'progress.log').open('a',buffering=1) as f:f.write(str(s)+'\n')
  print(tag,s,flush=True)
 try:
  with tarfile.open('/content/'+tag+'_inputs.tar.gz') as t:t.extractall(R,filter='data')
  defs=R/'FluidX3D/src/defines.hpp';s=defs.read_text();assert s.count('//#define CITY_STABILITY_MONITOR')==1;defs.write_text(s.replace('//#define CITY_STABILITY_MONITOR','#define CITY_STABILITY_MONITOR'))
  with (R/'build.log').open('w') as f:ret=subprocess.run(['make','Linux','-j4'],cwd=R/'FluidX3D',stdout=f,stderr=subprocess.STDOUT,timeout=900)
  log('BUILD '+str(ret.returncode));assert ret.returncode==0,(R/'build.log').read_text()[-4000:]
  case=R/'case';trace=case/'RESULTS/city_stability.csv';start=time.monotonic();seen=-1;reason=None
  env=os.environ.copy();env['LUW_GROUND_MIX_A']=a;env['LUW_GROUND_Z0_SI']='0.0001403048803922269'
  with (R/'solver.log').open('w',buffering=1) as f:
   p=subprocess.Popen([str(R/'FluidX3D/bin/FluidX3D'),str(case/'conf.luwpf')],cwd=case,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,env=env)
   while p.poll() is None:
    time.sleep(10);q=lastrow(trace)
    if q and int(q['step'])!=seen:
     seen=int(q['step']);lo=float(q['min_rho']);hi=float(q['max_rho']);u=float(q['max_u_lattice'])
     if seen%1000==0:log(f'STEP {seen} rho=[{lo},{hi}] umax={u}')
     if q['first_nonfinite_xyz_component'] or u>0.3 or (seen>=3000 and (lo<0.9 or hi>1.1)):
      reason=f'v3 exceeded at {seen}: {q}';log(reason);p.terminate();break
    if time.monotonic()-start>2000:
     reason='solver walltime limit 2000s';log(reason);p.terminate();break
   code=p.wait(timeout=60)
  (R/'solver.exit').write_text(f'{code} {reason}\n');log(f'EXIT {code} reason={reason} secs={int(time.monotonic()-start)}')
  if code==0 and reason is None:
   (R/'solver_a.exit').write_text('exit=0\n');(R/'case_a').symlink_to(case,target_is_directory=True)
   shutil.copy2('/content/points_w_r7.json',R/'points_w_r7.json')
   script=Path('/content/extract_full.py').read_text().replace('/content/luw_split_E1',str(R))
   (R/'extract.py').write_text(script)
   with (R/'extract.log').open('w') as f:ret=subprocess.run(['python3',str(R/'extract.py')],cwd=R,stdout=f,stderr=subprocess.STDOUT,timeout=800)
   log('EXTRACT '+str(ret.returncode))
   if ret.returncode:log((R/'extract.log').read_text()[-4000:])
   if ret.returncode==0:
    by={x:[] for x in (5,42,120,200)}
    with (case/'RESULTS/wall_tau_actual.csv').open() as f:
     for q in csv.DictReader(f):
      x=int(q['x']);y=int(q['y'])
      if x in by and y in range(100,401,30):by[x].append(float(q['ustar_mps']))
    (R/'ustar.json').write_text(json.dumps({x:{'mean':statistics.mean(v),'n':len(v)} for x,v in by.items() if v},indent=2))
 except Exception:
  (R/'error.txt').write_text(traceback.format_exc());log(traceback.format_exc()[-4000:])
 finally:
  if trace.exists():shutil.copy2(trace,R/'trace.csv')
  (R/'all.done').write_text('done\n')
Path('/content/luw_z0_all.done').write_text('done\n')
