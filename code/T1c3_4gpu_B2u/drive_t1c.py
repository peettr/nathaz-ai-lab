#!/usr/bin/env python3
"""Build and run all 31000 steps before any comparison; preserve solver exit."""
import os,pathlib,subprocess,sys,time
r=pathlib.Path(sys.argv[1]);case=r/'case_4gpu';base=r/'FluidX3D'
print('START',time.strftime('%Y-%m-%dT%H:%M:%S%z'),flush=True)
start=time.monotonic()
with (r/'build.log').open('w') as out:
    p=subprocess.run(['make','Linux','-j8'],cwd=base,stdout=out,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,timeout=600)
assert p.returncode==0,('build',p.returncode)
print('BUILD_SECONDS',time.monotonic()-start,flush=True)
env={**os.environ,'LD_LIBRARY_PATH':str(base/'src/OpenCL/lib')+':'+os.environ.get('LD_LIBRARY_PATH','')}
start=time.monotonic()
with (r/'solver.log').open('w') as out:
    p=subprocess.run([str(base/'bin/FluidX3D'),str(case/'conf.luwpf')],cwd=case,stdout=out,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,env=env)
(r/'solver.exitcode').write_text(str(p.returncode)+'\n')
print('SOLVER_SECONDS',time.monotonic()-start,'SOLVER_EXIT',p.returncode,flush=True)
if p.returncode:sys.exit(p.returncode)
trace=case/'RESULTS/city_stability.csv'
assert trace.is_file() and sum(1 for _ in trace.open())>=41,'incomplete trace'
print('SOLVER_DONE_POSTPROCESS_START',flush=True)
