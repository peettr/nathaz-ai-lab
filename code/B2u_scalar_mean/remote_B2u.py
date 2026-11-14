from pathlib import Path
import tarfile,subprocess,time,traceback,shutil,json,hashlib,os,math,mmap,struct
R=Path('/content/b2u_case');R.mkdir(exist_ok=False)
def log(s):
 with (R/'progress.log').open('a',buffering=1) as f:f.write(str(s)+'\n')
 print(s,flush=True)
def trace_last(path):
 if not path.exists():return None
 with path.open() as f:
  h=f.readline().strip().split(',');last=''
  for line in f:last=line
 return dict(zip(h,last.strip().split(','))) if last else None
def run(case,limit):
 trace=case/'RESULTS/city_stability.csv';start=time.monotonic();reason=None
 with (R/(case.name+'_solver.log')).open('w',buffering=1) as f:
  proc=subprocess.Popen([str(R/'FluidX3D/bin/FluidX3D'),str(case/'conf.luwpf')],cwd=case,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT)
  seen=-1
  while proc.poll() is None:
   time.sleep(5);q=trace_last(trace)
   if q and int(q['step'])!=seen:
    seen=int(q['step'])
    if seen%1000==0:log(f'{case.name} STEP {seen}')
    if q['first_nonfinite_xyz_component'] or float(q['max_u_lattice'])>.3 or (seen>=3000 and (float(q['min_rho'])<.9 or float(q['max_rho'])>1.1)):
     reason='v3 exceeded '+str(q);proc.terminate();break
   if time.monotonic()-start>limit:reason='walltime';proc.terminate();break
  code=proc.wait(timeout=90)
 (R/(case.name+'.exit')).write_text(f'{code} {reason}\n');log(f'{case.name} EXIT {code} {reason} {int(time.monotonic()-start)}s')
 assert code==0 and reason is None
 return trace
try:
 with tarfile.open('/content/B2u_inputs.tar.gz') as t:t.extractall(R,filter='data')
 defs=R/'FluidX3D/src/defines.hpp';s=defs.read_text();assert s.count('//#define CITY_STABILITY_MONITOR')==1
 defs.write_text(s.replace('//#define CITY_STABILITY_MONITOR','#define CITY_STABILITY_MONITOR'))
 with (R/'build.log').open('w') as f:p=subprocess.run(['make','Linux','-j4'],cwd=R/'FluidX3D',stdout=f,stderr=subprocess.STDOUT,timeout=900)
 log('BUILD '+str(p.returncode));assert p.returncode==0,(R/'build.log').read_text()[-3000:]
 case=R/'case';short=R/'short';shutil.copytree(case,short)
 c=short/'conf.luwpf';s=c.read_text();assert 'run_nstep = 31000' in s and 'purge_avg = 20000' in s
 c.write_text(s.replace('run_nstep = 31000','run_nstep = 80').replace('purge_avg = 20000','purge_avg = 80'))
 run(short,600)
 vtk=list((short/'RESULTS/vtk').glob('*_avg*.vtk'));assert len(vtk)==1,vtk
 v=vtk[0]
 with v.open('rb') as f:
  while not f.readline().startswith(b'LOOKUP_TABLE'):pass
  off=f.tell()
  # Four fields: vector u, rho, fluid, tke; then speed_mean and speed2_mean.
  count=500*500*270
  def advance(p,n,name):
   f.seek(p+n*4);header=f.readline()+f.readline();assert header.startswith(('SCALARS '+name).encode()),header[:100];return f.tell()
  rho=advance(off,count*3,'rho_avg');fluid=advance(rho,count,'fluid');tke=advance(fluid,count,'tke');su=advance(tke,count,'speed_mean');su2=advance(su,count,'speed2_mean')
  f.seek(off+((23*500+220)*500+220)*12);u=struct.unpack('>fff',f.read(12))
  idx=(23*500+220)*500+220
  f.seek(su+idx*4);mean=struct.unpack('>f',f.read(4))[0]
  f.seek(su2+idx*4);rms2=struct.unpack('>f',f.read(4))[0]
  lhs=math.sqrt(sum(x*x for x in u));rhs=math.sqrt(max(rms2,0.))
  assert mean>0 and lhs<=mean+2e-5 and mean<=rhs+2e-5,(lhs,mean,rhs)
 (R/'short_gate.json').write_text(json.dumps({'cell':[220,220,23],'mean_vector_mag':lhs,'scalar_mean':mean,'rms':rhs,'tolerance':2e-5,'vtk':str(v),'short_trace':hashlib.sha256((short/'RESULTS/city_stability.csv').read_bytes()).hexdigest()})+'\n')
 log('SHORT GATE OK '+(R/'short_gate.json').read_text())
 # Avoid retaining large short VTK before the full member.
 shutil.rmtree(short/'RESULTS/vtk')
 run(case,2700)
 (R/'solver_a.exit').write_text('exit=0\n');(R/'case_a').symlink_to(case,target_is_directory=True)
 shutil.copy2('/content/points_w_r7.json',R/'points_w_r7.json')
 with (R/'extract.log').open('w') as f:p=subprocess.run(['python3','/content/extract_B2u.py'],cwd=R,stdout=f,stderr=subprocess.STDOUT,timeout=650)
 log('EXTRACT '+str(p.returncode));assert p.returncode==0,(R/'extract.log').read_text()[-4000:]
 result=R/'offset_samples_a_r10.json';data=json.loads(result.read_text());assert len(data['rows'])==80
 assert {q['id'] for q in data['rows']}==set(range(1,81))
 for q in data['rows']:
  z=q['sample']['plus_dx'];assert z['Su_ratio']>0 and z['Srms_ratio']>0
 (R/'result.sha256').write_text(hashlib.sha256(result.read_bytes()).hexdigest()+'  offset_samples_a_r10.json\n')
 (R/'trace.sha256').write_text(hashlib.sha256((case/'RESULTS/city_stability.csv').read_bytes()).hexdigest()+'  city_stability.csv\n')
 log('RESULT VERIFIED '+str(result.stat().st_size)+' '+(R/'result.sha256').read_text().strip())
except Exception:
 (R/'error.txt').write_text(traceback.format_exc());log(traceback.format_exc()[-5000:])
finally:(R/'all.done').write_text('done\n')
