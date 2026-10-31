#!/usr/bin/env python3
"""Run frozen four-domain B2u once; terminate on a failed early trace gate."""
import csv,hashlib,json,math,os,pathlib,subprocess,sys,time
r=pathlib.Path(sys.argv[1]); case=r/'case_4gpu';base=r/'FluidX3D'
def digest(p):
 with open(p,'rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def compare(path):
 with (r/'B2u_trace.csv').open(newline='') as f:
  reader=csv.DictReader(f); keys=reader.fieldnames
  assert keys and 'step' in keys
  reference={int(q['step']):q for q in reader}
 with path.open(newline='') as f:
  reader=csv.DictReader(f)
  assert reader.fieldnames==keys, ('schema',reader.fieldnames,keys)
  rows=list(reader)
 if not rows or int(rows[-1]['step'])<2000:return None
 rows=[q for q in rows if int(q['step'])<=2000]
 assert [int(q['step']) for q in rows]==list(range(50,2001,50))
 diffs={}; nums=0
 for q in rows:
  step=int(q['step']);assert step in reference
  for key in keys:
   if key=='step':continue
   value=q[key]; value0=reference[step][key]
   if value=='' and value0=='':continue
   assert value and value0, ('missing field',step,key)
   try:v=float(value);v0=float(value0)
   except ValueError:
    assert value==value0,('non-numeric field mismatch',step,key)
    continue
   assert math.isfinite(v) and math.isfinite(v0), ('nonfinite',step,key)
   d=abs(v-v0)/max(abs(v0),1e-12)
   diffs[key]=max(d,diffs.get(key,0.0));nums+=1
 assert nums>300
 maximum=max(diffs.values(),default=0.0)
 return {'rows':len(rows),'numeric_compared':nums,'max_relative_by_field':diffs,'max_relative':maximum,'passed':maximum<=1e-4,'reference_sha256':digest(r/'B2u_trace.csv'),'trace_prefix_last':rows[-1]['step']}
print('START',time.strftime('%Y-%m-%dT%H:%M:%S%z'),flush=True)
build_start=time.monotonic()
with (r/'build.log').open('w') as out:
 p=subprocess.run(['make','Linux','-j8'],cwd=base,stdout=out,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,timeout=600)
assert p.returncode==0,('build',p.returncode)
print('BUILD_SECONDS',time.monotonic()-build_start,flush=True)
solver_start=time.monotonic()
env={**os.environ,'LD_LIBRARY_PATH':str(base/'src/OpenCL/lib')+':'+os.environ.get('LD_LIBRARY_PATH','')}
with (r/'solver.log').open('w') as out:
 p=subprocess.Popen([str(base/'bin/FluidX3D'),str(case/'conf.luwpf')],cwd=case,stdout=out,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,env=env)
 trace=case/'RESULTS/city_stability.csv'; verdict=None
 while p.poll() is None:
  if trace.is_file():
   try: verdict=compare(trace)
   except Exception as e:
    print('TRACE_GATE_ERROR',repr(e),flush=True);p.terminate();p.wait(timeout=30);raise
   if verdict is not None:
    (r/'trace_gate.json').write_text(json.dumps(verdict,indent=2)+'\n')
    print('TRACE_GATE',json.dumps(verdict),flush=True)
    if not verdict['passed']:
     p.terminate();p.wait(timeout=30);(r/'solver.exitcode').write_text('71\n');sys.exit(71)
    break
  time.sleep(2)
 rc=p.wait()
(r/'solver.exitcode').write_text(str(rc)+'\n')
print('SOLVER_SECONDS',time.monotonic()-solver_start,'EXIT',rc,flush=True)
if verdict is None and trace.is_file():
 verdict=compare(trace)
 if verdict is not None:(r/'trace_gate.json').write_text(json.dumps(verdict,indent=2)+'\n')
assert rc==0 and verdict and verdict['passed'],('run/trace',rc,verdict)
print('TRACE_TOTAL',sum(1 for _ in trace.open())-1,'SHA256',digest(trace),flush=True)
with (r/'extract.log').open('w') as out:
 e=subprocess.run([sys.executable,str(r/'extract_t1c.py'),str(r)],stdout=out,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,timeout=600)
print('EXTRACT_EXIT',e.returncode,flush=True);assert e.returncode==0
result=json.loads((r/'points_80_t1c.json').read_text())
assert result['gate_b'],('80-point gate b failed',result['mae_delta_abs'],result['point_delta_median'])
print('FINISH',time.strftime('%Y-%m-%dT%H:%M:%S%z'),flush=True)
