#!/usr/bin/env python3
"""Run frozen four-domain B2u once; terminate on a failed early trace gate."""
import csv,hashlib,json,math,os,pathlib,subprocess,sys,time
r=pathlib.Path(sys.argv[1]); case=r/'case_4gpu';base=r/'FluidX3D'
def digest(p):
 with open(p,'rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def compare(path):
 with (r/'B2u_trace.csv').open(newline='') as f: reference={int(q['step']):q for q in csv.DictReader(f)}
 with path.open(newline='') as f: rows=list(csv.DictReader(f))
 if not rows or int(rows[-1]['step'])<2000:return None
 rows=[q for q in rows if int(q['step'])<=2000];assert [int(q['step']) for q in rows]==list(range(50,2001,50))
 diffs={}; nums=0
 for q in rows:
  for key,value in q.items():
   if key=='step' or not value or not reference[int(q['step'])].get(key):continue
   try: v=float(value); v0=float(reference[int(q['step'])][key])
   except ValueError:continue
   assert math.isfinite(v) and math.isfinite(v0)
   d=abs(v-v0)/max(abs(v0),1e-12)
   if d>diffs.get(key,0):diffs[key]=d
   nums+=1
 assert nums>300
 return {'rows':len(rows),'numeric_compared':nums,'max_relative_by_field':diffs,'max_relative':max(diffs.values()),'passed':max(diffs.values())<=1e-4,'reference_sha256':digest(r/'B2u_trace.csv'),'trace_prefix_last':rows[-1]['step']}
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
print('FINISH',time.strftime('%Y-%m-%dT%H:%M:%S%z'),flush=True)
